import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Aedes Surveillance Dashboard", page_icon="🦟")

# --- FUNÇÃO PARA CARREGAR DADOS ---
@st.cache_data
def load_data():
    # SUBSTITUA 'SEU_ID_DA_PLANILHA' pelo ID real da sua planilha do Google
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    df['data'] = pd.to_datetime(df['data'])
    return df

# --- INTERFACE DA SIDEBAR (LOGIN E TEMA) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=70)
st.sidebar.title("Configurações")

# Seletor de Tema
tema_escolhido = st.sidebar.radio("Modo de Visualização", ["Escuro (Operacional)", "Claro (Relatório)"])

# Definição Dinâmica de Cores e Estilos
if tema_escolhido == "Escuro (Operacional)":
    bg_color = "#0E1117"
    card_bg = "#1A1C24"
    text_main = "#00FFCC" # Ciano Neon
    plotly_template = "plotly_dark"
    mapbox_style = "carto-darkmatter"
    accent = "#00FFCC"
else:
    bg_color = "#F0F2F6"
    card_bg = "#FFFFFF"
    text_main = "#1F2833" # Cinza Escuro
    plotly_template = "plotly_white"
    mapbox_style = "open-street-map"
    accent = "#007BFF" # Azul Real

# Injeção de CSS para Customização Visual Total
st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_main}; }}
    [data-testid="stSidebar"] {{ background-color: {card_bg}; }}
    h1, h2, h3 {{ color: {text_main} !important; text-align: center; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    .stMetric {{ background-color: {card_bg}; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }}
    </style>
    """, unsafe_allow_html=True)

try:
    df_raw = load_data()
except Exception as e:
    st.error("Erro ao conectar com a planilha. Verifique se o link está público.")
    st.stop()

# --- SISTEMA DE LOGIN ---
municipios = df_raw['municipio'].unique()
user_mun = st.sidebar.selectbox("Selecione o Município", municipios)
user_pass = st.sidebar.text_input("Senha do Município", type="password")

# Validação de Senha baseada na planilha
senha_correta = str(df_raw[df_raw['municipio'] == user_mun]['senha'].iloc[0])

if user_pass == senha_correta:
    # Filtragem Inicial por Município
    df_mun = df_raw[df_raw['municipio'] == user_mun]
    
    # Filtros de Data na Sidebar
    st.sidebar.markdown("---")
    meses_disponiveis = df_mun['data'].dt.strftime('%m/%Y').unique()
    filtro_data = st.sidebar.multiselect("Período de Análise", options=meses_disponiveis, default=meses_disponiveis)
    
    df_final = df_mun[df_mun['data'].dt.strftime('%m/%Y').isin(filtro_data)] if filtro_data else df_mun

    # --- TÍTULO PRINCIPAL ---
    st.markdown(f"<h1>SISTEMA DE MONITORAMENTO: {user_mun.upper()}</h1>", unsafe_allow_html=True)

    # --- LINHA DE MÉTRICAS (KPIs) ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total de Ovos", f"{int(df_final['ovos'].sum()):,}")
    m2.metric("Média de Ovos", f"{df_final['ovos'].mean():.1f}")
    m3.metric("Focos Críticos", len(df_final[df_final['ovos'] > df_final['ovos'].mean()]))
    m4.metric("Amostras", len(df_final))

    st.markdown("<br>", unsafe_allow_html=True)

    # --- DISPOSIÇÃO DO DASHBOARD (20% | 60% | 20%) ---
    col_esq, col_meio, col_dir = st.columns([1, 3, 1])

    with col_esq:
        # Gráfico 1: Barras por Região
        fig_bar = px.bar(df_final.groupby('regiao')['ovos'].mean().reset_index(),
                         x='ovos', y='regiao', orientation='h', template=plotly_template,
                         title="MÉDIA POR REGIÃO", color_discrete_sequence=[accent])
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Linha do Tempo
        fig_line = px.line(df_final.groupby('data')['ovos'].sum().reset_index(),
                          x='data', y='ovos', template=plotly_template, title="EVOLUÇÃO")
        fig_line.update_traces(line_color=accent, line_width=3)
        fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig_line, use_container_width=True)

    with col_meio:
        # --- MAPA DETALHADO (OPENSTREETMAP / CARTO) ---
        fig_map = px.density_mapbox(df_final, lat='lat', lon='lon', z='ovos', radius=20,
                                   center=dict(lat=df_final['lat'].mean(), lon=df_final['lon'].mean()), 
                                   zoom=13, mapbox_style=mapbox_style,
                                   title="MAPA DE CALOR E LOCALIZAÇÃO DE FOCOS")
        
        # Adiciona os pontos (Scatter) por cima do calor para interatividade
        fig_map.add_trace(go.Scattermapbox(
            lat=df_final['lat'], lon=df_final['lon'],
            mode='markers', marker=dict(size=10, color=accent, opacity=0.6),
            text=df_final['endereco'], hoverinfo='text'
        ))

        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600)
        st.plotly_chart(fig_map, use_container_width=True)

    with col_dir:
        # Gráfico 3: Distribuição Pizza
        fig_pie = px.pie(df_final, values='ovos', names='regiao', hole=.4, 
                         template=plotly_template, title="DISTRIBUIÇÃO %")
        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        # Gráfico 4: Tabela de Endereços Críticos
        st.markdown(f"### TOP 5 FOCOS")
        top_5 = df_final.nlargest(5, 'ovos')[['endereco', 'ovos']]
        st.table(top_5)

else:
    if user_pass:
        st.sidebar.error("SENHA INCORRETA")
    st.info("Aguardando login para liberar acesso aos dados georreferenciados.")
