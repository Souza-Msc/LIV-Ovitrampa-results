import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import branca.colormap as cm
import numpy as np

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(layout="wide", page_title="Relatório de dados Ovitrampas", page_icon="🦟")

# 2. CSS PERSONALIZADO (TEMA CLARO COM SESSÕES MARCADAS)
st.markdown("""
    <style>
    .main { background-color: #F0F2F5; }
    
    /* Força a moldura em Gráficos, Tabelas e no Container do Mapa */
    .stPlotlyChart, .stDataFrame, .stFoliumContainer, [data-testid="stVerticalBlock"] > .element-container:has(.stFoliumContainer) {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 12px !important;
        padding: 10px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
        margin-bottom: 20px !important;
    }

    /* Ajuste para o mapa não "vazar" para fora da borda arredondada */
    .stFoliumContainer iframe {
        border-radius: 8px !important;
    }

    [data-testid="stMetricValue"] { color: #1E40AF; font-weight: 800; }
    h1, h2, h3 { color: #111827; font-family: 'Inter', sans-serif; }
    
    .small-info {
        font-size: 0.8rem;
        padding: 8px;
        background-color: #EFF6FF;
        border-left: 4px solid #3B82F6;
        border-radius: 4px;
        color: #1E40AF;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. CARREGAMENTO E TRATAMENTO DE DADOS
@st.cache_data(ttl=600)
def load_and_process_data():
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    try:
        df = pd.read_csv(url)
        # Conversão de data
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        # Limpeza de strings e conversão numérica (lat, lon, ovos)
        for col in ['ovos', 'lat', 'lon']:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=['lat', 'lon', 'ovos', 'data', 'municipio'])
    except Exception as e:
        return pd.DataFrame()

df_raw = load_and_process_data()

if df_raw.empty:
    st.error("Não foi possível carregar os dados. Verifique a planilha ou a conexão.")
    st.stop()

# 4. SIDEBAR (Login e Filtros)
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=60)
st.sidebar.title("Acesso Restrito")
user_municipio = st.sidebar.selectbox("Município", df_raw['municipio'].unique())
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# Validação simples de senha via planilha
try:
    senha_correta = str(df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0]).strip()
except:
    senha_correta = None

if user_password == senha_correta:
    # Preparação dos dados do município
    df_mun = df_raw[df_raw['municipio'] == user_municipio].copy()
    df_mun['mes_ano'] = df_mun['data'].dt.strftime('%m/%Y')
    meses_lista = sorted(df_mun['mes_ano'].unique())
    
    filtro_data = st.sidebar.multiselect("Período de Coleta", options=meses_lista, default=meses_lista[-1:] if meses_lista else [])
    
    df_filtered = df_mun[df_mun['mes_ano'].isin(filtro_data)] if filtro_data else df_mun

    # 5. HEADER DASHBOARD
    st.markdown(f"<h1 style='text-align: center; color: #1E40AF;'>Laboratório de Identificação de Vetores</h1>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center; color: #1E40AF;'>Dados Ovitrampas - {user_municipio.upper()}</h2>", unsafe_allow_html=True)

    st.markdown("---")
    
    # KPIs rápidos
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total de Ovos", f"{int(df_filtered['ovos'].sum()):,}")
    k2.metric("Média/Amostra", f"{df_filtered['ovos'].mean():.1f}")
    k3.metric("Amostras Coletadas", len(df_filtered))
    k4.metric("Média Local", f"{df_filtered['ovos'].mean():.1f}")

    st.markdown("---")

    # 6. LAYOUT PRINCIPAL (Reajustado para 1.5 | 2.4 | 1.5)
    col_esq, col_meio, col_dir = st.columns([1.5, 2.4, 1.5])

    # Agrupamento essencial para médias por local (evita sobreposição e resolve erro de regiao)
    df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco', 'regiao']).agg({'ovos': 'mean'}).reset_index()

    with col_esq:
        # Gráfico 1: Média por Região
        resumo_reg = df_filtered.groupby('regiao')['ovos'].mean().reset_index()
        fig_bar = px.bar(resumo_reg, x='ovos', y='regiao', orientation='h', 
                         title="MÉDIA POR REGIÃO", template="plotly_white",
                         color_discrete_sequence=['#3B82F6'])
        fig_bar.update_layout(height=400, margin=dict(l=10, r=30, t=40, b=40), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Tendência Temporal
        resumo_time = df_filtered.groupby(df_filtered['data'].dt.date)['ovos'].sum().reset_index()
        fig_line = px.line(resumo_time, x='data', y='ovos', title="TENDÊNCIA (SOMA)", template="plotly_white")
        fig_line.update_traces(line_color='#EF4444', line_width=2)
        fig_line.update_layout(height=280, margin=dict(l=10, r=30, t=40, b=40), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_line, use_container_width=True)

    with col_meio:
        st.markdown("<h3 style='text-align: center;'>MAPA DE INFESTAÇÃO</h3>", unsafe_allow_html=True)
        
        # O Mapa agora reside dentro de um container que herdará o estilo de borda
        centro_mapa = [df_mapa['lat'].mean(), df_mapa['lon'].mean()]
        m = folium.Map(location=centro_mapa, zoom_start=14, tiles="CartoDB positron")
        
        # Escala de cores (Azul -> Vermelho)
        v_min, v_max = df_mapa['ovos'].min(), df_mapa['ovos'].max()
        if v_min == v_max: v_max += 1
        colormap = cm.LinearColormap(colors=['blue', 'lime', 'yellow', 'red'], vmin=v_min, vmax=v_max)
        
        for _, row in df_mapa.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=10,
                color=colormap(row['ovos']),
                fill=True,
                fill_color=colormap(row['ovos']),
                fill_opacity=0.4,
                weight=1.5,
                popup=f"<b>Endereço:</b> {row['endereco']}<br><b>Média:</b> {row['ovos']:.1f}",
                tooltip=f"{row['ovos']:.1f} ovos"
            ).add_to(m)
            
        m.add_child(colormap)
        
        # Renderização
        st_folium(m, width="100%", height=550, returned_objects=[])
    with col_dir:
        # Gráfico 3: Distribuição de Intensidade
        resumo_pie = df_mapa.groupby('regiao')['ovos'].mean().reset_index()
        fig_pie = px.pie(resumo_pie, values='ovos', names='regiao', hole=0.5, 
                         title="DISTRIBUIÇÃO %", template="plotly_white")
        fig_pie.update_layout(height=300, showlegend=False, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

        # Gráfico 4: Tabela de Alertas
        st.markdown("### 🚨 PONTOS CRÍTICOS")
        top_5 = df_mapa.nlargest(5, 'ovos')[['endereco', 'ovos', 'regiao']]
        top_5['ovos'] = top_5['ovos'].round(1)
        
        st.dataframe(
            top_5, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "endereco": "Local",
                "ovos": "Média",
                "regiao": "Região"
            }
        )
        
        # Dica Compacta que ocupa pouco espaço
        st.markdown('<div class="small-info"><b>Dica:</b> O tamanho da caixa do mapa foi reduzido para priorizar a leitura dos dados laterais.</div>', unsafe_allow_html=True)

else:
    if user_password:
        st.sidebar.error("CHAVE DE ACESSO INVÁLIDA")
    st.warning("⚠️ Aguardando autenticação para carregar os dados governamentais.")
