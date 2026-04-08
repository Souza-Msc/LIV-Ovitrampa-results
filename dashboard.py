import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import numpy as np

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(layout="wide", page_title="Relatório de Vetores", page_icon="🦟")

# 2. CSS PERSONALIZADO
st.markdown("""
    <style>
    .main { background-color: #F0F2F5; }
    .stPlotlyChart, .stDataFrame, .stFoliumContainer, [data-testid="stVerticalBlock"] > .element-container:has(.stFoliumContainer) {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 12px !important;
        padding: 10px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
        margin-bottom: 20px !important;
    }
    .stFoliumContainer iframe { border-radius: 8px !important; }
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
        # Renomeando ovos para contagem (caso a planilha ainda use o nome antigo)
        if 'ovos' in df.columns:
            df = df.rename(columns={'ovos': 'contagem'})
        
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        
        # Limpeza e conversão numérica
        for col in ['contagem', 'lat', 'lon']:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df.dropna(subset=['lat', 'lon', 'contagem', 'data', 'municipio', 'tipo'])
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        return pd.DataFrame()

df_raw = load_and_process_data()

if df_raw.empty:
    st.error("Não foi possível carregar os dados. Verifique a planilha ou a conexão.")
    st.stop()

# 4. SIDEBAR (Login e Filtros)
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=60)
st.sidebar.title("Painel de Controle")

user_municipio = st.sidebar.selectbox("Selecione o Município", sorted(df_raw['municipio'].unique()))
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# Validação de senha
try:
    senha_correta = str(df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0]).strip()
except:
    senha_correta = None

if user_password == senha_correta:
    # Filtros Adicionais
    df_mun = df_raw[df_raw['municipio'] == user_municipio].copy()
    
    # --- NOVO FILTRO: TIPO DE AMOSTRA ---
    tipos_disponiveis = sorted(df_mun['tipo'].unique())
    filtro_tipo = st.sidebar.selectbox("Tipo de Amostra", tipos_disponiveis)
    
    # Filtro de Data
    df_mun['mes_ano'] = df_mun['data'].dt.strftime('%m/%Y')
    meses_lista = sorted(df_mun['mes_ano'].unique())
    filtro_data = st.sidebar.multiselect("Período de Coleta", options=meses_lista, default=meses_lista[-1:] if meses_lista else [])
    
    # Aplicação dos Filtros
    df_filtered = df_mun[df_mun['tipo'] == filtro_tipo]
    if filtro_data:
        df_filtered = df_filtered[df_filtered['mes_ano'].isin(filtro_data)]

    # 5. HEADER DASHBOARD DINÂMICO
    st.markdown(f"<h1 style='text-align: center; color: #1E40AF;'>Laboratório de Identificação de Vetores</h1>", unsafe_allow_html=True)
    # Subtítulo alterado conforme sua solicitação
    st.markdown(f"<h2 style='text-align: center; color: #4B5563;'>Dados {filtro_tipo} - {user_municipio.upper()}</h2>", unsafe_allow_html=True)

    st.markdown("---")
    
    # KPIs rápidos (Atualizados para 'contagem')
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Contagem", f"{int(df_filtered['contagem'].sum()):,}")
    k2.metric("Média/Amostra", f"{df_filtered['contagem'].mean():.1f}")
    k3.metric("Amostras Coletadas", len(df_filtered))
    k4.metric("Máximo Registrado", f"{df_filtered['contagem'].max():.0f}")

    st.markdown("---")

    # 6. LAYOUT PRINCIPAL
    col_esq, col_meio, col_dir = st.columns([1.5, 2.4, 1.5])

    # Agrupamento para o Mapa
    df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco', 'regiao']).agg({'contagem': 'mean'}).reset_index()

    with col_esq:
        # Gráfico 1: Média por Região
        resumo_reg = df_filtered.groupby('regiao')['contagem'].mean().reset_index()
        fig_bar = px.bar(resumo_reg, x='contagem', y='regiao', orientation='h', 
                         title="MÉDIA POR REGIÃO", template="plotly_white",
                         color_discrete_sequence=['#3B82F6'])
        fig_bar.update_layout(height=350, margin=dict(l=10, r=30, t=40, b=40), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Tendência Temporal
        resumo_time = df_filtered.groupby(df_filtered['data'].dt.date)['contagem'].sum().reset_index()
        fig_line = px.line(resumo_time, x='data', y='contagem', title="TENDÊNCIA (SOMA)", template="plotly_white")
        fig_line.update_traces(line_color='#EF4444', line_width=2)
        fig_line.update_layout(height=350, margin=dict(l=10, r=30, t=40, b=40), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_line, use_container_width=True)

    with col_meio:
        st.markdown("<h4 style='text-align: center;'>MAPA DE INFESTAÇÃO</h4>", unsafe_allow_html=True)
        
        if not df_mapa.empty:
            centro_mapa = [df_mapa['lat'].mean(), df_mapa['lon'].mean()]
            m = folium.Map(location=centro_mapa, zoom_start=14, tiles="CartoDB positron")
            
            v_min, v_max = df_mapa['contagem'].min(), df_mapa['contagem'].max()
            if v_min == v_max: v_max += 1
            colormap = cm.LinearColormap(colors=['blue', 'lime', 'yellow', 'red'], vmin=v_min, vmax=v_max)
            
            for _, row in df_mapa.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=10,
                    color=colormap(row['contagem']),
                    fill=True,
                    fill_color=colormap(row['contagem']),
                    fill_opacity=0.4,
                    weight=1.5,
                    popup=f"<b>Endereço:</b> {row['endereco']}<br><b>Média:</b> {row['contagem']:.1f}",
                    tooltip=f"{row['contagem']:.1f} unidades"
                ).add_to(m)
            
            m.add_child(colormap)
            st_folium(m, width="100%", height=650, returned_objects=[])
        else:
            st.info("Sem dados geográficos para os filtros selecionados.")
        
    with col_dir:
        # Gráfico 3: Distribuição
        resumo_pie = df_mapa.groupby('regiao')['contagem'].mean().reset_index()
        fig_pie = px.pie(resumo_pie, values='contagem', names='regiao', hole=0.5, 
                         title="DISTRIBUIÇÃO %", template="plotly_white")
        fig_pie.update_layout(height=350, showlegend=False, margin=dict(l=10, r=10, t=30, b=20), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

        # Gráfico 4: Tabela de Alertas
        st.markdown("### 🚨 PONTOS CRÍTICOS")
        top_5 = df_mapa.nlargest(5, 'contagem')[['endereco', 'contagem', 'regiao']]
        top_5['contagem'] = top_5['contagem'].round(1)
        
        st.dataframe(
            top_5, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "endereco": "Local",
                "contagem": "Média",
                "regiao": "Região"
            }
        )
        
        st.markdown(f'<div class="small-info">Exibindo resultados para: <b>{filtro_tipo}</b></div>', unsafe_allow_html=True)

else:
    if user_password:
        st.sidebar.error("CHAVE DE ACESSO INVÁLIDA")
    st.warning("⚠️ Aguardando autenticação para carregar os dados governamentais.")
