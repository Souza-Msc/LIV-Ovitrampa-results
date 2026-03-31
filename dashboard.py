import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import branca.colormap as cm
import numpy as np

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(layout="wide", page_title="Aedes Control Panel", page_icon="🦟")

# 2. CSS PERSONALIZADO (TEMA CLARO E CAIXAS MARCADAS)
st.markdown("""
    <style>
    /* Fundo da página cinza claro */
    .main { background-color: #F0F2F5; }
    
    /* Estilo de "Card" para as sessões */
    .stPlotlyChart, .stFoliumContainer, .stDataFrame, .info-card {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 12px !important;
        padding: 10px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        margin-bottom: 15px;
    }

    /* KPIs */
    [data-testid="stMetricValue"] { color: #1E40AF; font-weight: 800; font-size: 1.8rem; }
    
    /* Títulos */
    h1, h2, h3 { color: #111827; font-family: 'Inter', sans-serif; margin-bottom: 10px; }

    /* Sidebar clara */
    section[data-testid="stSidebar"] { 
        background-color: #FFFFFF; 
        border-right: 1px solid #D1D5DB; 
    }

    /* Dica Compacta */
    .small-info {
        font-size: 0.8rem;
        padding: 8px;
        background-color: #EFF6FF;
        border-left: 4px solid #3B82F6;
        border-radius: 4px;
        color: #1E40AF;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÃO DE DADOS E LIMPEZA
@st.cache_data(ttl=600)
def load_and_process_data():
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    try:
        df = pd.read_csv(url)
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        # Limpeza de números (trata vírgula e ponto)
        for col in ['ovos', 'lat', 'lon']:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=['lat', 'lon', 'ovos', 'data', 'municipio'])
    except:
        return pd.DataFrame()

df_raw = load_and_process_data()

if df_raw.empty:
    st.error("Erro ao carregar dados. Verifique a conexão e o ID da planilha.")
    st.stop()

# 4. SIDEBAR - LOGIN E FILTROS
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=60)
st.sidebar.title("Aedes Control")
user_municipio = st.sidebar.selectbox("Município", df_raw['municipio'].unique())
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# Validação Simples
try:
    senha_correta = str(df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0]).strip()
except:
    senha_correta = None

if user_password == senha_correta:
    # Filtros
    df_mun = df_raw[df_raw['municipio'] == user_municipio].copy()
    df_mun['mes_ano'] = df_mun['data'].dt.strftime('%m/%Y')
    meses = sorted(df_mun['mes_ano'].unique())
    filtro_data = st.sidebar.multiselect("Período", options=meses, default=meses[-1] if meses else [])
    
    df_filtered = df_mun[df_mun['mes_ano'].isin(filtro_data)] if filtro_data else df_mun

    # 5. HEADER E KPIs
    st.markdown(f"<h1 style='text-align: center; color: #1E40AF;'>PAINEL EPIDEMIOLÓGICO - {user_municipio.upper()}</h1>", unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Ovos", f"{int(df_filtered['ovos'].sum()):,}")
    k2.metric("Média/Amostra", f"{df_filtered['ovos'].mean():.1f}")
    k3.metric("Amostras", len(df_filtered))
    k4.metric("Pontos Críticos", len(df_filtered[df_filtered['ovos'] > df_filtered['ovos'].mean()]))

    st.markdown("---")

    # 6. LAYOUT PRINCIPAL (1.5 | 2.4 | 1.5)
    col_esq, col_meio, col_dir = st.columns([1.5, 2.4, 1.5])

    # AGRUPAMENTO PARA MAPA E GRÁFICOS (Média por local)
    df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco', 'regiao']).agg({'ovos': 'mean'}).reset_index()

    with col_esq:
        # Barras por Região
        resumo_reg = df_filtered.groupby('regiao')['ovos'].mean().reset_index()
        fig_bar = px.bar(resumo_reg, x='ovos', y='regiao', orientation='h', title="MÉDIA POR REGIÃO", 
                         template="plotly_white", color_discrete_sequence=['#3B82F6'])
        fig_bar.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

        # Evolução Temporal
        resumo_time = df_filtered.groupby(df_filtered['data'].dt.date)['ovos'].sum().reset_index()
        fig_line = px.line(resumo_time, x='data', y='ovos', title="TENDÊNCIA TEMPORAL", template="plotly_white")
        fig_line.update_traces(line_color='#EF4444', line_width=2)
        fig_line.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_line, use_container_width=True)

    with col_meio:
        st.markdown("<h3 style='text-align: center;'>MAPA DE CALOR E PONTOS</h3>", unsafe_allow_html=True)
        centro = [df_mapa['lat'].mean(), df_mapa['lon'].mean()]
        m = folium.Map(location=centro, zoom_start=14, tiles="CartoDB positron")
        
        # Escala de cor Azul -> Vermelho
        v_min, v_max = df_mapa['ovos'].min(), df_mapa['ovos'].max()
        if v_min == v_max: v_max += 1
        colormap = cm.LinearColormap(colors=['blue', 'lime', 'yellow', 'red'], vmin=v_min, vmax=v_max)
        
        # Marcadores individuais com TRANSPARÊNCIA
        for _, row in df_mapa.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=10,
                color=colormap(row['ovos']),
                fill=True,
                fill_color=colormap(row['ovos']),
                fill_opacity=0.4, # Transparência solicitada
                popup=f"<b>{row['endereco']}</b><br>Média: {row['ovos']:.1f}",
                tooltip=f"{row['ovos']:.1f} ovos"
            ).add_to(m)
            
        m.add_child(colormap)
        st_folium(m, width="100%", height=600, returned_objects=[])

    with col_dir:
        # Pizza de Distribuição
        resumo_pie = df_mapa.groupby('regiao')['ovos'].mean().reset_index()
        fig_pie = px.pie(resumo_pie, values='ovos', names='regiao', hole=0.5, 
                         title="DISTRIBUIÇÃO INTENSIDADE %", template="plotly_white")
        fig_pie.update_layout(height=280, showlegend=False, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

        # Tabela Top Focos
        st.markdown("### 🚨 TOP FOCOS (Média)")
        top_5 = df_mapa.nlargest(5, 'ovos')[['endereco', 'ovos', 'regiao']]
        st.dataframe(top_5, hide_index=True, use_container_width=True, 
                     column_config={"endereco": "Local", "ovos": "Média", "regiao": "Região"})
        
        # Dica Compacta
        st.markdown('<div class="small-info"><b>Dica:</b> Cores variam do Azul (Baixo) ao Vermelho (Crítico).</div>', unsafe_allow_html=True)

else:
    if user_password: st.sidebar.error("CHAVE INCORRETA")
    st.warning("🔒 Digite a chave de acesso para carregar os dados do município.")
