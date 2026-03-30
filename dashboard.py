import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime

# Configuração da Página
st.set_page_config(layout="wide", page_title="Monitoramento Aedes Aegypti")

# --- FUNÇÃO PARA CARREGAR DADOS DO GOOGLE SHEETS ---
def load_data():
    # Substitua pelo ID da sua planilha
    SHEET_ID = "SEU_ID_DA_PLANILHA_AQUI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    df['data'] = pd.to_datetime(df['data'])
    return df

try:
    df_raw = load_data()
except:
    st.error("Erro ao conectar com a planilha. Verifique o ID e as permissões.")
    st.stop()

# --- SISTEMA DE LOGIN SIMPLES ---
st.sidebar.title("Login do Município")
user_municipio = st.sidebar.selectbox("Selecione seu Município", df_raw['municipio'].unique())
user_password = st.sidebar.text_input("Senha", type="password")

# Validação (A senha deve estar na coluna 'senha' da sua planilha para aquele município)
senha_correta = df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0]

if user_password == str(senha_correta):
    st.title(f"Painel Epidemiológico: {user_municipio}")
    
    # --- FILTROS ---
    df_mun = df_raw[df_raw['municipio'] == user_municipio]
    
    st.sidebar.markdown("---")
    meses = df_mun['data'].dt.strftime('%m/%Y').unique()
    filtro_data = st.sidebar.multiselect("Filtrar por Mês/Ano", options=meses, default=meses)
    
    if filtro_data:
        df_filtered = df_mun[df_mun['data'].dt.strftime('%m/%Y').isin(filtro_data)]
    else:
        df_filtered = df_mun

    # --- LAYOUT (20% | 60% | 20%) ---
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        st.subheader("Médias")
        # Gráfico 1: Média por Região
        fig1 = px.bar(df_filtered.groupby('regiao')['ovos'].mean().reset_index(), 
                     x='ovos', y='regiao', orientation='h', title="Média de Ovos/Região")
        st.plotly_chart(fig1, use_container_width=True)

        # Gráfico 2: Evolução Temporal
        fig2 = px.line(df_filtered.groupby('data')['ovos'].sum().reset_index(), 
                      x='data', y='ovos', title="Série Temporal")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Mapa de Calor de Infestação")
        # Centraliza o mapa na média das coordenadas
        centro_lat = df_filtered['lat'].mean()
        centro_lon = df_filtered['lon'].mean()
        
        m = folium.Map(location=[centro_lat, centro_lon], zoom_start=13)
        
        # Adiciona círculos proporcionais à contagem de ovos
        for _, row in df_filtered.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=row['ovos'] / 10, # Ajuste a escala conforme necessário
                popup=f"{row['endereco']}: {row['ovos']} ovos",
                color="red",
                fill=True,
                fill_opacity=0.6
            ).add_to(m)
        
        st_folium(m, width=800, height=500)

    with col3:
        st.subheader("Análise")
        # Gráfico 3: Distribuição por Região (Pizza)
        fig3 = px.pie(df_filtered, values='ovos', names='regiao', title="Distribuição Total")
        st.plotly_chart(fig3, use_container_width=True)

        # Gráfico 4: Ranking de Endereços Críticos
        top_enderecos = df_filtered.nlargest(5, 'ovos')[['endereco', 'ovos']]
        st.write("**Top 5 Focos Críticos:**")
        st.table(top_enderecos)

else:
    if user_password:
        st.sidebar.error("Senha incorreta!")
    st.info("Insira a senha do município na barra lateral para acessar os dados.")