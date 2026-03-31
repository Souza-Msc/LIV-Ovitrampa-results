import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Aedes Surveillance MG", page_icon="🦟")

# --- CARREGAMENTO DE DADOS GEOGRÁFICOS ---
@st.cache_data
def load_geodata():
    path_mg = os.path.join("Geo", "municipios_mg.json")
    path_jf = os.path.join("Geo", "regioes_jf.json")
    
    with open(path_mg, "r", encoding="utf-8") as f:
        mg_geojson = json.load(f)
    with open(path_jf, "r", encoding="utf-8") as f:
        jf_geojson = json.load(f)
        
    return mg_geojson, jf_geojson

# --- CARREGAMENTO DA PLANILHA ---
@st.cache_data
def load_sheet_data():
    # SUBSTITUA PELO SEU ID REAL DO GOOGLE SHEETS
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    df['data'] = pd.to_datetime(df['data'])
    # Garantir que os nomes das regiões estejam em maiúsculas para bater com o GeoJSON
    df['regiao'] = df['regiao'].str.upper()
    return df

try:
    geojson_mg, geojson_jf = load_geodata()
    df_raw = load_sheet_data()
except Exception as e:
    st.error(f"Erro ao carregar arquivos: {e}")
    st.stop()

# --- SIDEBAR: TEMA E LOGIN ---
st.sidebar.title("Configurações")
tema = st.sidebar.radio("Esquema de Cores", ["Escuro", "Claro"])

if tema == "Escuro":
    bg_color, text_color = "#0E1117", "#00FFCC"
    map_style = "carto-darkmatter"
    plotly_temp = "plotly_dark"
    colorscale = "Viridis"
else:
    bg_color, text_color = "#F0F2F6", "#1F2833"
    map_style = "open-street-map"
    plotly_temp = "plotly_white"
    colorscale = "Reds"

st.markdown(f"<style>.stApp {{ background-color: {bg_color}; color: {text_color}; }}</style>", unsafe_allow_html=True)

# Login
user_mun = st.sidebar.selectbox("Município", df_raw['municipio'].unique())
user_pass = st.sidebar.text_input("Senha", type="password")
senha_correta = str(df_raw[df_raw['municipio'] == user_mun]['senha'].iloc[0])

if user_pass == senha_correta:
    df_filtered = df_raw[df_raw['municipio'] == user_mun]
    
    st.markdown(f"<h1>MONITORAMENTO: {user_mun.upper()}</h1>", unsafe_allow_html=True)

    # --- LAYOUT (20/60/20) ---
    col_esq, col_meio, col_dir = st.columns([1, 3, 1])

    with col_meio:
        # Agregando dados por região para pintar o polígono
        df_regioes = df_filtered.groupby('regiao')['ovos'].sum().reset_index()

        fig_map = go.Figure()

        # 1. CAMADA DE POLÍGONOS (CHOROPLETH) - PINTA AS REGIÕES
        if user_mun.upper() == "JUIZ DE FORA":
            fig_map.add_trace(go.Choroplethmapbox(
                geojson=geojson_jf,
                locations=df_regioes['regiao'], # Coluna da Planilha
                featureidkey="properties.REGIAO", # Coluna dentro do GeoJSON
                z=df_regioes['ovos'], # Valor para definir a cor
                colorscale=colorscale,
                marker_opacity=0.5,
                marker_line_width=1,
                marker_line_color=text_color,
                colorbar_title="Total Ovos",
                name="Setores"
            ))

        # 2. CAMADA DE DENSIDADE (HEATMAP) - FOCOS PONTUAIS
        fig_map.add_trace(go.Densitymapbox(
            lat=df_filtered['lat'], lon=df_filtered['lon'], z=df_filtered['ovos'],
            radius=15, colorscale="Hot", showscale=False
        ))

        # 3. PONTOS INDIVIDUAIS (SCATTER)
        fig_map.add_trace(go.Scattermapbox(
            lat=df_filtered['lat'], lon=df_filtered['lon'],
            mode='markers', marker=dict(size=8, color=text_color),
            text=df_filtered['endereco'], hoverinfo='text'
        ))

        fig_map.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=df_filtered['lat'].mean(), lon=df_filtered['lon'].mean()),
                zoom=11.5
            ),
            margin={"r":0,"t":0,"l":0,"b":0}, height=650, paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with col_esq:
        st.subheader("Média por Região")
        fig_bar = px.bar(df_filtered.groupby('regiao')['ovos'].mean().reset_index(), 
                         x='ovos', y='regiao', orientation='h', template=plotly_temp)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_dir:
        st.subheader("Top 5 Endereços")
        st.table(df_filtered.nlargest(5, 'ovos')[['endereco', 'ovos']])

else:
    st.warning("⚠️ Insira a chave de acesso do município.")
