import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import numpy as np
import time

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(layout="wide", page_title="Relatório de Vetores", page_icon="🦟")

# 2. CARREGAMENTO E TRATAMENTO DE DADOS
@st.cache_data(ttl=10)
def load_and_process_data(timestamp):
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&cache_bust={timestamp}"
    
    try:
        df = pd.read_csv(url)
        df.columns = [c.strip().lower() for c in df.columns]
        
        if 'ovos' in df.columns:
            df = df.rename(columns={'ovos': 'contagem'})
            
        # AJUSTE 1: Conversão de data respeitando o formato ISO (YYYY-MM-DD)
        # Isso evita que o Python inverta dia com mês
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        
        # Limpeza de números
        for col in ['contagem', 'lat', 'lon']:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # AJUSTE 2: Preenchimento de nulos para não deletar a linha no dropna
        df['tipo'] = df['tipo'].fillna('Não Informado').astype(str)
        df['contagem'] = df['contagem'].fillna(0)
        
        # Mantemos apenas o que tem localização e município
        df_clean = df.dropna(subset=['lat', 'lon', 'municipio'])
        
        return df_clean
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return pd.DataFrame()

df_raw = load_and_process_data(int(time.time()))

# 3. SIDEBAR E FILTROS
st.sidebar.title("Painel de Controle")

if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

lista_municipios = sorted(df_raw['municipio'].unique())
user_municipio = st.sidebar.selectbox("Município", lista_municipios)
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# Validação de senha
try:
    df_mun_base = df_raw[df_raw['municipio'] == user_municipio].copy()
    senha_correta = str(df_mun_base['senha'].iloc[0]).strip()
except:
    senha_correta = None

if user_password == senha_correta:
    # AJUSTE 3: Filtro de Tipo (Garante que pegue todos os dados do município)
    lista_tipos = sorted(df_mun_base['tipo'].unique())
    filtro_tipo = st.sidebar.selectbox("Tipo de Amostra", lista_tipos)
    
    df_tipo_mun = df_mun_base[df_mun_base['tipo'] == filtro_tipo].copy()
    
    # AJUSTE 4: Criação segura da lista de meses
    # Filtramos datas nulas antes de gerar a lista do menu
    df_tipo_mun = df_tipo_mun.dropna(subset=['data'])
    df_tipo_mun['mes_ano'] = df_tipo_mun['data'].dt.strftime('%m/%Y')
    
    meses_unicos = df_tipo_mun['mes_ano'].unique()
    meses_lista = sorted([str(m) for m in meses_unicos])
    
    filtro_data = st.sidebar.multiselect(
        "Período de Coleta", 
        options=meses_lista, 
        default=meses_lista # Agora ele seleciona TUDO por padrão para não sumir dados
    )
    
    # Aplicação do filtro final
    if filtro_data:
        df_filtered = df_tipo_mun[df_tipo_mun['mes_ano'].isin(filtro_data)]
    else:
        df_filtered = df_tipo_mun

    # --- EXIBIÇÃO DO DASHBOARD ---
    st.markdown(f"<h1 style='text-align: center;'>Laboratório de Vetores</h1>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center;'>{filtro_tipo} - {user_municipio.upper()}</h2>", unsafe_allow_html=True)

    # Métricas para conferência
    c1, c2, c3 = st.columns(3)
    c1.metric("Amostras no Município", len(df_mun_base))
    c2.metric("Amostras do Tipo", len(df_tipo_mun))
    c3.metric("Amostras Exibidas (Filtro)", len(df_filtered))

    st.markdown("---")

    # Gráficos e Mapa
    col_esq, col_meio, col_dir = st.columns([1.5, 2.4, 1.5])

    # Agrupamento para o Mapa
    df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco', 'regiao']).agg({'contagem': 'mean'}).reset_index()

    with col_esq:
        resumo_reg = df_filtered.groupby('regiao')['contagem'].mean().reset_index()
        st.plotly_chart(px.bar(resumo_reg, x='contagem', y='regiao', orientation='h', title="MÉDIA/REGIÃO"), use_container_width=True)
        
        resumo_time = df_filtered.groupby(df_filtered['data'].dt.date)['contagem'].sum().reset_index()
        st.plotly_chart(px.line(resumo_time, x='data', y='contagem', title="SOMA TEMPORAL"), use_container_width=True)

    with col_meio:
        if not df_mapa.empty:
            m = folium.Map(location=[df_mapa['lat'].mean(), df_mapa['lon'].mean()], zoom_start=13, tiles="CartoDB positron")
            v_max = df_mapa['contagem'].max() if df_mapa['contagem'].max() > 0 else 1
            colormap = cm.LinearColormap(colors=['blue', 'lime', 'yellow', 'red'], vmin=0, vmax=v_max)
            for _, row in df_mapa.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=10, color=colormap(row['contagem']), fill=True,
                    fill_color=colormap(row['contagem']), fill_opacity=0.6,
                    popup=f"{row['endereco']}: {row['contagem']:.1f}"
                ).add_to(m)
            st_folium(m, width="100%", height=600, returned_objects=[])

    with col_dir:
        resumo_pie = df_mapa.groupby('regiao')['contagem'].mean().reset_index()
        st.plotly_chart(px.pie(resumo_pie, values='contagem', names='regiao', hole=0.5, title="% DISTRIBUIÇÃO"), use_container_width=True)
        st.markdown("### 🚨 PONTOS CRÍTICOS")
        st.dataframe(df_mapa.nlargest(5, 'contagem')[['endereco', 'contagem']], hide_index=True)

else:
    if user_password: st.sidebar.error("SENHA INCORRETA")
    st.warning("Insira a chave de acesso.")
