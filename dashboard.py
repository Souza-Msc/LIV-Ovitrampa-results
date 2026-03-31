import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import numpy as np

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
    div[data-testid="stToolbar"] {visibility: hidden;} /* Esconde a barra do Streamlit */
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE DADOS E PRÉ-PROCESSAMENTO ---
@st.cache_data(ttl=600) # Atualiza a cada 10 minutos
def load_and_process_data():
    # ID DA PLANILHA (Verifique se é o correto)
    SHEET_ID = "1g8sAi6kUJnHHxCl97s6JwGDnRF8asTPmmCfWp2qFbEI"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
    
    try:
        df = pd.read_csv(url)
        
        # --- LIMPEZA E FORMATAÇÃO ---
        # 1. Converter data
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.dropna(subset=['data']) # Remove datas inválidas

        # 2. Corrigir Colunas Numéricas (Ovos, Lat, Lon)
        # Se os dados vierem como texto "1.200" ou "22,5", precisamos limpar.
        cols_numericas = ['ovos', 'lat', 'lon']
        for col in cols_numericas:
            if df[col].dtype == 'object': # Se for texto
                # Remove pontos de milhar, troca vírgula por ponto decimal
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            
            # Converte para float, tratando erros como NaN (Not a Number)
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 3. Remover linhas onde as coordenadas ou ovos falharam na conversão
        df = df.dropna(subset=['lat', 'lon', 'ovos'])
        
        # 4. Garantir que ovos seja inteiro (opcional, mas bom para a soma)
        df['ovos'] = df['ovos'].astype(int)

        return df
    
    except Exception as e:
        st.error(f"Erro na conexão ou processamento: {e}")
        return pd.DataFrame() # Retorna DF vazio em caso de erro

# Tenta carregar os dados processados
df_raw = load_and_process_data()

# Verifica se os dados foram carregados
if df_raw.empty:
    st.error("Não foi possível carregar os dados. Verifique a planilha ou a conexão.")
    st.stop()

# --- LOGIN NA SIDEBAR ---
# Tenta carregar a imagem, se falhar, usa texto
try:
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2641/2641409.png", width=80)
except:
    st.sidebar.markdown("# 🦟")
    
st.sidebar.title("ACESSO RESTRITO")

# Lista de municípios únicos (para o selectbox)
municipios_disponiveis = df_raw['municipio'].unique()
user_municipio = st.sidebar.selectbox("Município", municipios_disponiveis)
user_password = st.sidebar.text_input("Chave de Acesso", type="password")

# --- VALIDAÇÃO DE SENHA ---
# Pega a senha real correspondente ao município selecionado
# Usamos try/except para o caso de não encontrar a senha
try:
    senha_correta = str(df_raw[df_raw['municipio'] == user_municipio]['senha'].iloc[0]).strip()
except IndexError:
    senha_correta = None

# Se a senha estiver correta, carrega o dashboard
if user_password and user_password.strip() == senha_correta:
    
    # --- FILTRAGEM ---
    df_mun = df_raw[df_raw['municipio'] == user_municipio]
    
    # Barra de Filtro de Data Estilizada na Sidebar
    st.sidebar.markdown("### FILTROS TEMPORAIS")
    
    # Cria a coluna de Mês/Ano para o filtro
    df_mun['mes_ano'] = df_mun['data'].dt.strftime('%m/%Y')
    meses = df_mun['mes_ano'].unique()
    
    # Define o padrão como o mês mais recente
    default_mes = [meses[0]] if len(meses) > 0 else []
    
    filtro_data = st.sidebar.multiselect("Período de Coleta", options=meses, default=default_mes)
    
    # Aplica o filtro de data
    if filtro_data:
        df_filtered = df_mun[df_mun['mes_ano'].isin(filtro_data)]
    else:
        df_filtered = df_mun # Se nada selecionado, mostra tudo do município

    # --- HEADER DASHBOARD ---
    st.markdown(f"<h1 style='text-align: center; color: #00FFCC;'>CENTRAL DE INTELIGÊNCIA EPIDEMIOLÓGICA - {user_municipio.upper()}</h1>", unsafe_allow_html=True)
    
    # Verifica se há dados após o filtro para evitar erros
    if df_filtered.empty:
        st.warning("Nenhum dado encontrado para o período selecionado.")
        st.stop()

    # --- KPIs RÁPIDOS NO TOPO ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    # KPI 1: Total de Ovos
    total_ovos = df_filtered['ovos'].sum()
    kpi1.metric("Total de Ovos (Período)", f"{int(total_ovos):,}")
    
    # KPI 2: Média de Ovos por Amostra
    media_ovos = df_filtered['ovos'].mean()
    kpi2.metric("Média/Amostra", f"{media_ovos:.1f}")
    
    # KPI 3: Total de Amostras
    total_amostras = len(df_filtered)
    kpi3.metric("Amostras Coletadas", f"{total_amostras}")
    
    # KPI 4: Média de Ovos por Ponto (Agrupado)
    # Primeiro agrupamos para ter o total de ovos por localidade única
    df_pontos_unicos = df_filtered.groupby(['lat', 'lon']).agg({'ovos': 'mean'}).reset_index()
    media_por_ponto = df_pontos_unicos['ovos'].mean()
    kpi4.metric("Média/Ponto Único", f"{media_por_ponto:.1f}")

    st.markdown("---")

    # --- LAYOUT PRINCIPAL (20% | 60% | 20%) ---
    col_esq, col_meio, col_dir = st.columns([1.2, 3, 1.2])

    # --- COLUNA ESQUERDA (Gráficos) ---
    with col_esq:
        # Gráfico 1: Média por Região
        resumo_regiao = df_filtered.groupby('regiao')['ovos'].mean().reset_index()
        fig_bar = px.bar(resumo_regiao, x='ovos', y='regiao', orientation='h', 
                         title="MÉDIA OVOS POR REGIÃO", template="plotly_dark",
                         labels={'ovos': 'Média Ovos'},
                         color_discrete_sequence=['#00FFCC'])
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Evolução Temporal (Diária/Semanal)
        # Resumimos por data
        resumo_tempo = df_filtered.groupby(df_filtered['data'].dt.date)['ovos'].sum().reset_index()
        resumo_tempo.columns = ['data', 'total_ovos']
        
        fig_line = px.line(resumo_tempo, x='data', y='total_ovos', title="TENDÊNCIA TEMPORAL (TOTAL)",
                           template="plotly_dark", labels={'total_ovos': 'Total Ovos'})
        fig_line.update_traces(line_color='#FF00FF', line_width=3)
        fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_line, use_container_width=True)

    # --- COLUNA MEIO (Mapa Corrigido) ---
    with col_meio:
        st.markdown("<h3 style='text-align: center;'>MAPA DINÂMICO DE INFESTAÇÃO</h3>", unsafe_allow_html=True)
        
        # 1. Agrupar os dados por Coordenadas e Endereço para tirar a MÉDIA
        # Isso resolve o problema de ter múltiplas amostras no mesmo local em datas diferentes.
        df_mapa = df_filtered.groupby(['lat', 'lon', 'endereco']).agg({
            'ovos': 'mean' # Tira a média de ovos para aquele ponto
        }).reset_index()

        # Define o centro do mapa com base na média das coordenadas filtradas
        centro_lat = df_mapa['lat'].mean()
        centro_lon = df_mapa['lon'].mean()
        
        # Cria o mapa com estilo Dark
        m = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB dark_matter")
        
        # 2. Camada de Calor (HeatMap) - Opcional, mas mantida
        heat_data = [[row['lat'], row['lon'], row['ovos']] for index, row in df_mapa.iterrows()]
        HeatMap(heat_data, radius=15, blur=12, name="Mapa de Calor").add_to(m)
        
        # 3. Pontos Individuais com Tamanho Variável (SEU PEDIDO)
        for _, row in df_mapa.iterrows():
            # Define o tamanho do raio do ponto em pixels.
            # Usamos raiz quadrada da média para escalonar melhor, multiplicado por um fator.
            # O max(..., 4) garante que o ponto tenha pelo menos 4 pixels para ser visível.
            radius_size = max(np.sqrt(row['ovos']) * 1.5, 4)
            
            # Popup com informações detalhadas
            popup_text = f"""
                <div style='font-family: sans-serif; font-size: 12px; color: #333;'>
                    <b>Endereço:</b> {row['endereco']}<br>
                    <b>Coordenadas:</b> {row['lat']:.5f}, {row['lon']:.5f}<br>
                    <b style='color: red; font-size: 14px;'>Média de Ovos: {row['ovos']:.1f}</b>
                </div>
            """
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=radius_size,
                color="#00FFCC", # Cor da borda (Cyan)
                fill=True,
                fill_color="#00FFCC",
                fill_opacity=0.6,
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=f"{row['ovos']:.1f} ovos (média)" # Dica rápida ao passar o mouse
            ).add_to(m)
            
        # Adiciona controle de camadas (para ligar/desligar o heatmap se quiser)
        folium.LayerControl().add_to(m)

        # Renderiza o mapa no Streamlit
        st_folium(m, width="100%", height=620, returned_objects=[])

    # --- COLUNA DIREITA (Outras Análises) ---
    with col_dir:
        # Gráfico 3: Distribuição % por Região
        # Usamos o total de ovos aqui
        resumo_pie = df_filtered.groupby('regiao')['ovos'].sum().reset_index()
        fig_pie = px.pie(resumo_pie, values='ovos', names='regiao', hole=0.6,
                         title="DISTRIBUIÇÃO TOTAL %", template="plotly_dark",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=20, r=20, t=50, b=20))
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

        # Gráfico 4: Top Focos (Maiores Médias por Ponto)
        st.markdown("### TOP 5 FOCOS (Média)")
        top_5 = df_pontos_unicos.nlargest(5, 'ovos').reset_index(drop=True)
        
        # Arredonda a média para 1 casa decimal
        top_5['ovos'] = top_5['ovos'].round(1)
        st.dataframe(top_5, hide_index=True, use_container_width=True, columns={'lat': 'Lat', 'lon': 'Lon', 'ovos': 'Média Ovos'})
        
        st.info(f"💡 Dica: No mapa, o tamanho do ponto Cyan representa a média de ovos naquele endereço.")

else:
    # Se o usuário tentou digitar algo e errou
    if user_password:
        st.sidebar.error("CHAVE INVÁLIDA")
    st.warning("⚠️ Aguardando autenticação para carregar dados.")
    
    # Adiciona um placeholder ou instruções
    st.markdown("""
        ## Bem-vindo ao Aedes Control Panel
        Este painel exibe dados epidemiológicos de infestação de *Aedes aegypti*.
        
        **Para acessar:**
        1. Selecione seu Município na barra lateral.
        2. Digite a Chave de Acesso autorizada.
    """)
