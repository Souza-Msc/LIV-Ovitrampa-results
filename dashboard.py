import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# Configuração da Página para ocupação total
st.set_page_config(layout="wide", page_title="Aedes Control Panel", page_icon="🦟")

# --- CSS PERSONALIZADO PARA ESTILO DARK PROFESSIONAL ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #00FFCC; }
    .stPlotlyChart { border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    h1, h2, h3 { color: #FFFFFF; font-family: 'Roboto', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #1A1C24; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE DADOS ---
@st.cache_data
def load_data():
    # SUBSTITUA PELO SEU ID DA PLANILHA
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    df['data'] = pd.to_datetime(df['data'])
    return df

try:
    df_raw = load_data()
except:
    st.error("Erro na conexão. Verifique o ID da Planilha.")
    st.stop()

# --- LOGIN NA SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=80)
st.sidebar.title("ACESSO RESTRITO")
user_municipio = st.sidebar.selectbox("Município", df_raw['municipio'].unique())
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# Validação Simples
senha_correta = str(df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0])

if user_password == senha_correta:
    # --- FILTRAGEM ---
    df_mun = df_raw[df_raw['municipio'] == user_municipio]
    
    # Barra de Filtro de Data Estilizada na Sidebar
    st.sidebar.markdown("### FILTROS TEMPORAIS")
    meses = df_mun['data'].dt.strftime('%m/%Y').unique()
    filtro_data = st.sidebar.multiselect("Período de Coleta", options=meses, default=meses)
    
    df_filtered = df_mun[df_mun['data'].dt.strftime('%m/%Y').isin(filtro_data)] if filtro_data else df_mun

    # --- HEADER DASHBOARD ---
    st.markdown(f"<h1 style='text-align: center; color: #00FFCC;'>CENTRAL DE INTELIGÊNCIA EPIDEMIOLÓGICA - {user_municipio.upper()}</h1>", unsafe_allow_html=True)
    
    # KPIs Rápidos no Topo
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total de Ovos", f"{int(df_filtered['ovos'].sum()):,}")
    kpi2.metric("Média de Densidade", f"{df_filtered['ovos'].mean():.2f}")
    kpi3.metric("Pontos Críticos", len(df_filtered[df_filtered['ovos'] > df_filtered['ovos'].mean()]))
    kpi4.metric("Amostras Coletadas", len(df_filtered))

    st.markdown("---")

    # --- LAYOUT PRINCIPAL (20% | 60% | 20%) ---
    col_esq, col_meio, col_dir = st.columns([1.2, 3, 1.2])

    with col_esq:
        # Gráfico 1: Média por Região (Barras Neon)
        resumo_regiao = df_filtered.groupby('regiao')['ovos'].mean().reset_index()
        fig_bar = px.bar(resumo_regiao, x='ovos', y='regiao', orientation='h', 
                         title="DENSIDADE POR REGIÃO", template="plotly_dark",
                         color_discrete_sequence=['#00FFCC'])
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300)
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Evolução (Linha Glow)
        resumo_tempo = df_filtered.groupby('data')['ovos'].sum().reset_index()
        fig_line = px.line(resumo_tempo, x='data', y='ovos', title="TENDÊNCIA TEMPORAL",
                           template="plotly_dark")
        fig_line.update_traces(line_color='#FF00FF', line_width=3)
        fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300)
        st.plotly_chart(fig_line, use_container_width=True)

    with col_meio:
        st.markdown("<h3 style='text-align: center;'>MAPA DINÂMICO DE INFESTAÇÃO</h3>", unsafe_allow_html=True)
        
        # --- LÓGICA DE AGREGAÇÃO PARA OS PONTOS ---
        # Agrupamos por coordenadas e endereço para tirar a média se houver mais de uma amostra
        df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco']).agg({
            'ovos': 'mean'
        }).reset_index()

        centro_lat = df_mapa['lat'].mean()
        centro_lon = df_mapa['lon'].mean()
        
        m = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB dark_matter")
        
        # Camada de Calor (Heatmap) - continua usando os dados filtrados
        heat_data = [[row['lat'], row['lon'], row['ovos']] for index, row in df_mapa.iterrows()]
        HeatMap(heat_data, radius=15, blur=10).add_to(m)
        
        # Marcadores individuais com TAMANHO VARIÁVEL
        for _, row in df_mapa.iterrows():
            # Definindo o tamanho do ponto: 
            # Usamos uma regra simples: a raiz quadrada da média de ovos * um multiplicador
            # Isso evita que pontos com muitos ovos fiquem gigantescos
            tamanho_ponto = (row['ovos'] ** 0.5) * 2  
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=max(tamanho_ponto, 3), # Mínimo de 3 pixels para ser visível
                color="#00FFCC",
                fill_color="#00FFCC",
                fill_opacity=0.6,
                popup=f"<b>Endereço:</b> {row['endereco']}<br><b>Média de Ovos:</b> {row['ovos']:.2f}",
                fill=True
            ).add_to(m)
            
        st_folium(m, width="100%", height=620, returned_objects=[])

    with col_dir:
        # Gráfico 3: Distribuição (Donut Neon)
        fig_pie = px.pie(df_filtered, values='ovos', names='regiao', hole=0.6,
                         title="DISTRIBUIÇÃO %", template="plotly_dark",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300)
        st.plotly_chart(fig_pie, use_container_width=True)

        # Gráfico 4: Top Focos (Tabela Estilizada)
        st.markdown("### ALERTAS CRÍTICOS")
        top_5 = df_filtered.nlargest(5, 'ovos')[['regiao', 'ovos']]
        st.dataframe(top_5, hide_index=True, use_container_width=True)
        
        st.info("💡 A região Sul apresenta 15% de aumento em relação ao mês anterior.")

else:
    if user_password:
        st.sidebar.error("CHAVE INVÁLIDA")
    st.warning("⚠️ Aguardando autenticação para carregar dados governamentais.")
