from pathlib import Path
import unicodedata
import json

import pandas as pd
import plotly.express as px
import streamlit as st

# =====================================================
# CONFIGURAÇÕES
# =====================================================
st.set_page_config(
    page_title="TB-VIGIA | Amazonas",
    page_icon="🫁",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
PASTA_DADOS = BASE_DIR / "dados"

# Os arquivos podem ficar na pasta "dados" ou junto do app.py.
ARQUIVOS = {
    "confirmados": "casos_confirmados.csv",
    "cura": "cura.csv",
    "abandono": "abandono.csv",
    "obitos": "obitos.csv",
}

ANOS_ESPERADOS = list(range(2019, 2026))


# =====================================================
# IDENTIDADE VISUAL
# =====================================================
st.markdown("""
<style>

/* Texto dos botões de download */
div[data-testid="stDownloadButton"] button,
div[data-testid="stDownloadButton"] button p,
div[data-testid="stDownloadButton"] button span {
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

/* Fundo dos botões */
div[data-testid="stDownloadButton"] button {
    background-color: #174A8B !important;
    border: 1px solid #174A8B !important;
    border-radius: 8px !important;
}

/* Efeito ao passar o mouse */
div[data-testid="stDownloadButton"] button:hover {
    background-color: #0D3265 !important;
    border-color: #0D3265 !important;
}

div.stDownloadButton > button {
    background-color: #174A8B !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 15px !important;
}

div.stDownloadButton > button:hover {
    background-color: #0D3265 !important;
    color: #FFFFFF !important;
    border: none !important;
}

.stApp {
    background: #F4F7FB;
}
/* BARRA LATERAL */
section[data-testid="stSidebar"] {
    background-color: #102D59 !important;
}

section[data-testid="stSidebar"] > div {
    background-color: #102D59 !important;
}

section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    background-color: transparent !important;
}

section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

/* ÁREA PRINCIPAL */
section[data-testid="stMain"] {
    min-width: 0 !important;
}

div[data-testid="stMainBlockContainer"] {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

.hero {
    background: linear-gradient(110deg, #102D59, #1769AA);
    padding: 26px 30px; border-radius: 15px; color: white;
    margin-bottom: 18px;
}

.hero h1, .hero p { color: #FFFFFF !important; }
.hero h1 { font-size: 2.25rem !important; font-weight: 800 !important; margin: 0; }
.hero p { font-size: 1.02rem !important; margin: 8px 0 0; }

div[data-testid="stMetric"] {
    background: #FFFFFF !important; border: 1px solid #DCE6F1 !important;
    border-radius: 12px; padding: 15px !important;
}

div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p {
    color: #52677F !important; opacity: 1 !important;
}

div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div,
div[data-testid="stMetricValue"] span {
    color: #102D59 !important; opacity: 1 !important;
    font-size: 1.75rem !important; font-weight: 800 !important;
}

[data-testid="stMain"] h1, [data-testid="stMain"] h2,
[data-testid="stMain"] h3, [data-testid="stMain"] p,
[data-testid="stMain"] label { color: #20344D; }
[data-testid="stWidgetLabel"] p { color: #20344D !important; }

.panel {
    background: white; border: 1px solid #E1E9F2;
    border-radius: 12px; padding: 16px; margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def normalizar_texto(valor):
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")
    return " ".join(texto.upper().split())


def formatar_numero(valor):
    if pd.isna(valor):
        return "—"
    return f"{int(valor):,}".replace(",", ".")


def localizar_arquivo(nome):
    candidatos = [PASTA_DADOS / nome, BASE_DIR / nome]
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    raise FileNotFoundError(
        f"Não encontrei {nome}. Coloque o arquivo na pasta 'dados' "
        "ou na mesma pasta do app.py."
    )


# =====================================================
# LEITURA DOS CSVs TABNET
# =====================================================
@st.cache_data
def carregar_tabnet(nome_arquivo, nome_indicador):
    caminho = localizar_arquivo(nome_arquivo)

    # TABNET exporta linhas de título antes do cabeçalho.
    linhas = caminho.read_text(encoding="latin1").splitlines()
    indice_cabecalho = None

    for i, linha in enumerate(linhas):
        linha_limpa = linha.strip().lstrip("\ufeff")
        if "Município de residência" in linha_limpa and "2019" in linha_limpa:
            indice_cabecalho = i
            break

    if indice_cabecalho is None:
        raise ValueError(
            f"Não localizei o cabeçalho de município/ano em {nome_arquivo}."
        )

    df = pd.read_csv(
        caminho,
        sep=";",
        skiprows=indice_cabecalho,
        encoding="latin1",
        dtype=str,
        na_values=["-", ""],
        engine="python"
    )

    df.columns = [
        str(c).replace('"', "").replace("\ufeff", "").strip()
        for c in df.columns
    ]

    coluna_municipio = "Município de residência"
    if coluna_municipio not in df.columns:
        raise ValueError(
            f"A coluna '{coluna_municipio}' não foi encontrada em {nome_arquivo}. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    # Exclui linhas Total/ignorado e mantém códigos municipais de seis dígitos.
    df[coluna_municipio] = df[coluna_municipio].astype(str).str.strip()
    df = df[
        df[coluna_municipio].str.match(r"^\d{6}\s+", na=False)
    ].copy()

    df["Código IBGE"] = df[coluna_municipio].str.extract(r"^(\d{6})")
    df["Município"] = (
        df[coluna_municipio]
        .str.replace(r"^\d{6}\s*", "", regex=True)
        .str.strip()
        .str.title()
    )

    colunas_anos = [
        str(ano) for ano in ANOS_ESPERADOS
        if str(ano) in df.columns
    ]
    if not colunas_anos:
        raise ValueError(
            f"Não encontrei colunas de 2019 a 2025 em {nome_arquivo}. "
            f"Colunas: {list(df.columns)}"
        )

    longo = df.melt(
        id_vars=["Código IBGE", "Município"],
        value_vars=colunas_anos,
        var_name="Ano",
        value_name=nome_indicador
    )

    longo["Ano"] = pd.to_numeric(longo["Ano"], errors="coerce").astype(int)
    longo[nome_indicador] = pd.to_numeric(
        longo[nome_indicador], errors="coerce"
    )
    return longo


@st.cache_data
def carregar_dados_integrados():
    confirmados = carregar_tabnet(
        ARQUIVOS["confirmados"], "Casos confirmados"
    )
    cura = carregar_tabnet(ARQUIVOS["cura"], "Casos de cura")
    abandono = carregar_tabnet(
        ARQUIVOS["abandono"], "Casos de abandono"
    )
    obitos = carregar_tabnet(
        ARQUIVOS["obitos"], "Óbitos por tuberculose"
    )

    # Confirma que a base principal tem uma linha por município/ano.
    dados = confirmados.copy()

    for base, coluna in [
        (cura, "Casos de cura"),
        (abandono, "Casos de abandono"),
        (obitos, "Óbitos por tuberculose"),
    ]:
        dados = dados.merge(
            base[["Código IBGE", "Ano", coluna]],
            on=["Código IBGE", "Ano"],
            how="left",
            validate="one_to_one"
        )

    # Ausência de linha nas extrações de desfecho é exibida como zero
    # para contagem municipal, mas a cobertura deve ser interpretada
    # conforme a extração e sua completude.
    colunas_desfecho = [
        "Casos de cura",
        "Casos de abandono",
        "Óbitos por tuberculose",
    ]
    for coluna in colunas_desfecho:
        dados[coluna] = dados[coluna].fillna(0).astype(int)

    dados["Casos confirmados"] = (
        dados["Casos confirmados"].fillna(0).astype(int)
    )
    dados["Código IBGE"] = dados["Código IBGE"].astype(str).str.zfill(6)
    dados["Município_normalizado"] = dados["Município"].map(normalizar_texto)

    return dados.sort_values(
        ["Ano", "Município"]
    ).reset_index(drop=True)


try:
    dados = carregar_dados_integrados()
except Exception as erro:
    st.error(f"Não foi possível integrar as bases do SINAN: {erro}")
    st.info(
        "Confira se os quatro arquivos estão na pasta 'dados' e se os nomes "
        "são casos_confirmados.csv, cura.csv, abandono.csv e obitos.csv."
    )
    st.stop()


# =====================================================
# MENU E CABEÇALHO
# =====================================================
with st.sidebar:
    st.markdown("""
    <div style="
        padding: 18px 5px 22px 5px;
        text-align: center;
    ">
        <div style="font-size: 55px; margin-bottom: 5px;">
            🫁
        </div>
        <h1 style="
            color: white;
            font-size: 36px;
            font-weight: 900;
            margin: 0;
            letter-spacing: 1px;
        ">
            TB-VIGIA
        </h1>
        <p style="
            color: white;
            font-size: 16px;
            font-weight: 600;
            margin-top: 12px;
        ">
            Plataforma de vigilância Epidemiológica da Tuberculose
        </p>
        <p style="
            color: #E0E8FF;
            font-size: 15px;
            margin-top: 8px;
        ">
            Amazonas • Brasil
        </p>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Escolha uma página:",
        [
            "Visão geral",
            "Fatores associados",
            "Classificação de risco de abandono",
            "Relatórios",
            "Sobre o sistema",
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("Em desenvolvimento")
    st.caption("Fonte: SINAN / DATASUS")
    st.caption("Série selecionada: 2019–2025")

st.markdown("""
<div class="hero">
    <h1>TB-VIGIA</h1>
    <p>Plataforma de monitoramento e análise dos indicadores
    epidemiológicos da tuberculose no estado do Amazonas.</p>
</div>
""", unsafe_allow_html=True)


# =====================================================
# FILTROS COMPACTOS
# =====================================================
anos_disponiveis = sorted(dados["Ano"].dropna().astype(int).unique().tolist())
municipios_disponiveis = sorted(dados["Município"].dropna().unique().tolist())

if not anos_disponiveis:
    st.error("Não existem anos disponíveis nas bases.")
    st.stop()
if page in ("Classificação de risco de abandono", "Fatores associados"):
    # Os CSVs de fatores são totais agregados de 2019 a 2025.
    ano = "Todos"
    municipio = "Todos"
    filtrado = dados.copy()
    base_ano = dados.copy()

else:
    if page != "Sobre o sistema":
        if page != "Relatórios":
            st.markdown("### Filtros epidemiológicos")

            espaco, area_filtros = st.columns([3, 2])

            with area_filtros:
                f1, f2 = st.columns([1, 1.7])

                with f1:
                    ano = st.selectbox(
                        "Ano",
                        ["Todos"] + anos_disponiveis,
                        index=0,
                        key="ano_global"
                    )

                with f2:
                    municipio = st.selectbox(
                        "Município",
                        ["Todos"] + municipios_disponiveis,
                        index=0,
                        key="municipio_global"
                    )
        else:
            ano = "Todos"
            municipio = "Todos"

        # Mantenha abaixo o restante do código de filtragem
        filtrado = dados.copy()
        if ano != "Todos":
            filtrado = filtrado[filtrado["Ano"].astype(int) == int(ano)].copy()
        if municipio != "Todos":
            filtrado = filtrado[filtrado["Município"] == municipio].copy()
        # base_ano passa a representar exatamente o recorte escolhido nos filtros.
        base_ano = filtrado.copy()
    else:
        ano = "Todos"
        municipio = "Todos"
        filtrado = dados.copy()
        base_ano = filtrado.copy()


# =====================================================
# GRÁFICOS E RESUMOS
# =====================================================
def criar_grafico_municipios(df, titulo, coluna="Casos confirmados"):
    grafico = (
        df.groupby("Município", as_index=False)[coluna]
        .sum()
        .sort_values(coluna, ascending=True)
    )
    grafico = grafico[grafico[coluna] > 0].copy()
    if grafico.empty:
        return px.bar(title="Não há registros para o filtro selecionado.")

    grafico["Rótulo"] = grafico[coluna].apply(formatar_numero)
    fig = px.bar(
        grafico, x=coluna, y="Município", orientation="h",
        text="Rótulo", title=titulo,
        color_discrete_sequence=["#1769AA"]
    )
    fig.update_traces(
        textposition="outside", textfont=dict(size=11, color="#20344D"),
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Casos: %{x:,.0f}<extra></extra>"
    )
    fig.update_layout(
        height=max(520, len(grafico) * 34),
        paper_bgcolor="white", plot_bgcolor="white",
        # Reserva espaço à esquerda para os nomes completos dos municípios.
        margin=dict(l=155, r=90, t=70, b=55),
        font=dict(family="Arial", size=12, color="#20344D"),
        xaxis_title="Número de casos", yaxis_title="Município",
        showlegend=False,
        yaxis=dict(
            showticklabels=True,
            automargin=True,
            tickfont=dict(size=11, color="#20344D"),
            categoryorder="total ascending",
        ),
        xaxis=dict(
            showticklabels=True,
            automargin=True,
            tickformat=",.0f",
        ),
    )
    return fig


@st.cache_data(show_spinner="Carregando mapa dos municípios do Amazonas...")
def carregar_mapa_amazonas():
    import geobr
    mapa = geobr.read_municipality(code_muni="AM", year=2020)
    # O geobr utiliza código IBGE de 7 dígitos; a extração TABNET
    # utilizada neste projeto contém os 6 primeiros dígitos.
    mapa["Código IBGE"] = mapa["code_muni"].astype(str).str.zfill(7).str[:6]
    # Chave simples para evitar problemas com acentos/espaços no GeoJSON.
    mapa["id_municipio"] = mapa["Código IBGE"]
    return mapa


def mostrar_mapa_amazonas(df_mapa, titulo):
    """Mapa municipal da proporção de abandono entre os desfechos extraídos."""
    try:
        import plotly.graph_objects as go

        mapa = carregar_mapa_amazonas().copy()

        # Soma primeiro os desfechos por município (e período selecionado).
        resumo = (
            df_mapa.groupby("Código IBGE", as_index=False)[
                ["Casos de cura", "Casos de abandono", "Óbitos por tuberculose"]
            ].sum()
        )
        resumo["Código IBGE"] = resumo["Código IBGE"].astype(str).str.zfill(6)
        mapa = mapa.merge(resumo, on="Código IBGE", how="left")

        colunas = ["Casos de cura", "Casos de abandono", "Óbitos por tuberculose"]
        for coluna in colunas:
            mapa[coluna] = pd.to_numeric(mapa[coluna], errors="coerce").fillna(0)

        # Denominador limitado aos três desfechos disponíveis nos CSVs.
        # Assim, o indicador é apresentado como proporção entre desfechos
        # extraídos, e não como taxa populacional de incidência.
        mapa["Total de desfechos extraídos"] = mapa[colunas].sum(axis=1)
        mapa["Proporção de abandono (%)"] = 0.0
        validos = mapa["Total de desfechos extraídos"] > 0
        mapa.loc[validos, "Proporção de abandono (%)"] = (
            mapa.loc[validos, "Casos de abandono"] /
            mapa.loc[validos, "Total de desfechos extraídos"] * 100
        )
        mapa["id_municipio"] = mapa["Código IBGE"]
        geojson = json.loads(mapa.to_json())

        escala_laranja = [
            [0.0, "#FFF3E0"],
            [0.20, "#FFE0B2"],
            [0.40, "#FFB74D"],
            [0.60, "#FB8C00"],
            [0.80, "#E65100"],
            [1.0, "#8C2D04"],
        ]
        maximo = float(mapa["Proporção de abandono (%)"].max())
        if maximo <= 0:
            maximo = 1.0

        fig = px.choropleth(
            mapa,
            geojson=geojson,
            locations="id_municipio",
            featureidkey="properties.id_municipio",
            color="Proporção de abandono (%)",
            range_color=(0, maximo),
            hover_name="name_muni",
            hover_data={
                "Casos de abandono": ":,.0f",
                "Casos de cura": ":,.0f",
                "Óbitos por tuberculose": ":,.0f",
                "Total de desfechos extraídos": ":,.0f",
                "Proporção de abandono (%)": ":.1f",
                "id_municipio": False,
                "Código IBGE": False,
            },
            color_continuous_scale=escala_laranja,
            title=titulo,
        )

        # Rótulos municipais dentro dos polígonos; tamanho pequeno para
        # preservar a leitura nos municípios menores e na região metropolitana.
        mapa_rotulos = mapa.to_crs(epsg=4326)
        pontos = mapa_rotulos.geometry.representative_point()
        fig.add_trace(
            go.Scattergeo(
                lon=pontos.x,
                lat=pontos.y,
                text=mapa_rotulos["name_muni"],
                mode="text",
                textfont=dict(size=8, color="#54210A", family="Arial"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        fig.update_geos(
            fitbounds="locations", visible=False,
            showcountries=False, showcoastlines=False,
            showland=True, landcolor="#FFFAF4",
        )
        fig.update_layout(
            height=780,
            paper_bgcolor="white",
            margin=dict(l=5, r=25, t=65, b=10),
            coloraxis=dict(
                cmin=0,
                cmax=maximo,
                colorbar=dict(
                    title="Abandono (%)",
                    tickmode="array",
                    tickvals=[0, maximo / 2, maximo],
                    ticktext=[
                        f"0% · Sem/baixo", 
                        f"{maximo / 2:.1f}% · Intermediário",
                        f"{maximo:.1f}% · Alto",
                    ],
                    thickness=22,
                    len=0.84,
                    outlinewidth=0,
                ),
            ),
            font=dict(color="#54210A"),
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption(
            "Indicador calculado como: casos de abandono ÷ (cura + abandono + óbito) × 100. "
            "Como a base contém apenas esses três desfechos extraídos, interprete o resultado "
            "como proporção de abandono entre os desfechos disponíveis, não como incidência "
            "populacional nem como taxa oficial completa do SINAN. Municípios sem desfechos "
            "registrados aparecem na faixa mais clara."
        )
    except Exception as erro:
        st.warning(
            "Não foi possível carregar o mapa municipal. Verifique a instalação "
            "do geobr e a conexão com a internet. Detalhe: " + str(erro)
        )


def somar(df, coluna):
    if df.empty:
        return 0
    return int(df[coluna].fillna(0).sum())


def montar_tabela_serie(df):
    serie = (
        df.groupby("Ano", as_index=False)[
            [
                "Casos confirmados",
                "Casos de cura",
                "Casos de abandono",
                "Óbitos por tuberculose",
            ]
        ].sum()
        .sort_values("Ano")
    )
    return serie




# =====================================================
# BASES DOS FATORES SOCIODEMOGRÁFICOS E EPIDEMIOLÓGICOS
# =====================================================
ARQUIVOS_FATORES = {
    "masculino": "masculino.csv",
    "feminino": "feminino.csv",
    "sexo_ignorado": "sexo ignorado.csv",
    "menor20": "menor que 20 anos.csv",
    "20a59": "20 a 59.csv",
    "60mais": "60 ou mais.csv",
    "escolaridade": "escolaridade.csv",
    "hiv_positivo": "hiv positivo.csv",
    "hiv_negativo": "hiv negativo.csv",
    "hiv_ignorado": "hiv ignorado.csv",
    "alcool_sim": "alcool sim.csv",
    "alcool_nao": "alcool não.csv",
    "alcool_ignorado": "alcool ignorado.csv",
    "raca_branca": "raça branca.csv",
    "raca_preta": "raca preta.csv",
    "raca_parda": "parda.csv",
    "raca_amarela": "raca amarela.csv",
    "raca_indigena": "indigena.csv",
    "raca_ignorada": "nulo raca.csv",
    "drogas_sim": "drogas sim.csv",
    "drogas_nao": "drogas não.csv",
    "drogas_ignorado": "drogas ignorado.csv",
}
def localizar_arquivo_fator(nome):
    # Primeiro procura nas pastas principais
    candidatos = [
        PASTA_DADOS / nome,
        BASE_DIR / nome
    ]

    for caminho in candidatos:
        if caminho.exists():
            return caminho

    # Se não encontrar, procura nas subpastas do projeto
    encontrados = [
        caminho
        for caminho in BASE_DIR.rglob(nome)
        if ".venv" not in caminho.parts
        and "__pycache__" not in caminho.parts
    ]

    if encontrados:
        return encontrados[0]

    raise FileNotFoundError(
        f"Não encontrei o arquivo {nome}. "
        "Confira se ele está dentro da pasta do projeto."
    )


@st.cache_data
def carregar_tabela_fator(nome):
    caminho = localizar_arquivo_fator(nome)
    linhas = caminho.read_text(encoding="latin1").splitlines()
    indice = None
    for i, linha in enumerate(linhas):
        if linha.strip().startswith('"Reg.Saúde/Município de residên";') or linha.strip().startswith("Reg.Saúde/Município de residên;"):
            indice = i
            break
    if indice is None:
        raise ValueError(f"Cabeçalho TabNet não encontrado em {nome}.")

    tabela = pd.read_csv(
        caminho, sep=";", skiprows=indice, encoding="latin1",
        dtype=str, engine="python", on_bad_lines="skip"
    )
    tabela.columns = [str(c).replace('"', '').strip() for c in tabela.columns]
    coluna_local = tabela.columns[0]
    # As linhas municipais do TabNet começam com pontos.
    # Linhas de região de saúde são subtotais e não entram na soma.
    tabela[coluna_local] = tabela[coluna_local].astype(str).str.strip()
    tabela = tabela[tabela[coluna_local].str.startswith(".....", na=False)].copy()

    for coluna in tabela.columns[1:]:
        tabela[coluna] = (
            tabela[coluna].astype(str).str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .replace(["-", "…", "...", "nan", "None", ""], "0")
        )
        tabela[coluna] = pd.to_numeric(tabela[coluna], errors="coerce").fillna(0)
    return tabela


def total_fator(chave, coluna="Total"):
    tabela = carregar_tabela_fator(ARQUIVOS_FATORES[chave])
    if coluna not in tabela.columns:
        raise ValueError(
            f"A coluna '{coluna}' não existe em {ARQUIVOS_FATORES[chave]}."
        )
    return int(tabela[coluna].sum())


def dados_escolaridade_fator():
    tabela = carregar_tabela_fator(ARQUIVOS_FATORES["escolaridade"])
    agrupamentos = {
        "Analfabeto": ["Analfabeto"],
        "Fundamental incompleto": [
            "1ª a 4ª série incompleta do EF",
            "4ª série completa do EF",
            "5ª a 8ª série incompleta do EF"
        ],
        "Fundamental completo": ["Ensino fundamental completo"],
        "Médio incompleto": ["Ensino médio incompleto"],
        "Médio completo": ["Ensino médio completo"],
        "Superior": [
            "Educação superior incompleta",
            "Educação superior completa"
        ],
        "Não se aplica": ["Não se aplica"]
    }
    resultado = {}
    for categoria, colunas in agrupamentos.items():
        resultado[categoria] = int(
            sum(tabela[col].sum() for col in colunas if col in tabela.columns)
        )
    ignorados = int(tabela["Ign/Branco"].sum()) if "Ign/Branco" in tabela.columns else 0
    return resultado, ignorados

def grafico_fator_barras(titulo, valores):
    df = pd.DataFrame({
        "Categoria": list(valores.keys()),
        "Registros": list(valores.values())
    })

    df = df[df["Registros"] > 0].copy()

    if df.empty:
        st.info("Não há registros disponíveis para este gráfico.")
        return

    total = df["Registros"].sum()
    df["Percentual"] = df["Registros"] / total * 100

    df = df.sort_values("Registros", ascending=True)

    fig = px.bar(
        df,
        x="Registros",
        y="Categoria",
        orientation="h",
        text="Percentual",
        title=titulo,
        color_discrete_sequence=["#397DBB"]
    )

    fig.update_traces(
        texttemplate="%{x:,.0f} (%{text:.1f}%)",
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=11, color="#20344D"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Registros: %{x:,.0f}<br>"
            "Percentual: %{text:.1f}%"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=300,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Arial", size=11, color="#20344D"),
        xaxis_title="",
        yaxis_title="",
        showlegend=False,
        margin=dict(l=10, r=65, t=65, b=25),
        title=dict(
            font=dict(size=15, color="#102D59"),
            x=0.02
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#EDF1F6",
            zeroline=False
        ),
        yaxis=dict(
            showgrid=False,
            automargin=True
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )


def grafico_fator_rosca(titulo, valores):
    df = pd.DataFrame({
        "Categoria": list(valores.keys()),
        "Registros": list(valores.values())
    })

    df = df[df["Registros"] > 0].copy()

    if df.empty:
        st.info("Não há registros disponíveis para este gráfico.")
        return

    fig = px.pie(
        df,
        names="Categoria",
        values="Registros",
        hole=0.58,
        title=titulo,
        color_discrete_sequence=[
            "#397DBB",
            "#9DBCE5",
            "#D6E2F2",
            "#E5A12B"
        ]
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        textfont=dict(size=12, color="white"),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Registros: %{value:,.0f}<br>"
            "Percentual: %{percent}"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=300,
        paper_bgcolor="white",
        font=dict(family="Arial", size=11, color="#20344D"),
        margin=dict(l=10, r=10, t=65, b=20),
        title=dict(
            font=dict(size=15, color="#102D59"),
            x=0.02
        ),
        legend=dict(
            orientation="h",
            y=-0.08,
            x=0.5,
            xanchor="center",
            font=dict(size=10)
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )


# =====================================================
# PÁGINA 1 — VISÃO GERAL
# =====================================================
if page == "Visão geral":
  if page == "Visão geral":
    st.markdown("### Panorama epidemiológico")

    # Calcular os totais
    total_confirmados = somar(filtrado, "Casos confirmados")
    total_cura = somar(filtrado, "Casos de cura")
    total_abandono = somar(filtrado, "Casos de abandono")
    total_obitos = somar(filtrado, "Óbitos por tuberculose")

    # Criar as colunas
    c1, c2, c3, c4 = st.columns(4)

    # Função dos indicadores
    def mostrar_indicador(coluna, icone, cor, titulo, valor):
        coluna.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:9px;">
                <span style="font-size:29px; color:{cor};">{icone}</span>
                <span style="font-size:14px; color:#777;">{titulo}</span>
            </div>
            <div style="font-size:29px; font-weight:700; color:{cor};">
                {formatar_numero(valor)}
            </div>
            """,
            unsafe_allow_html=True
        )

    mostrar_indicador(c1, "🫁", "#5369B5", "Casos confirmados", total_confirmados)
    mostrar_indicador(c2, "✚", "#20A45A", "Casos de cura", total_cura)
    mostrar_indicador(c3, "⚠️", "#E5A12B", "Casos de abandono", total_abandono)
    mostrar_indicador(c4, "●", "#C94F4F", "Óbitos por tuberculose", total_obitos)
    st.caption(
        "Os valores são contagens absolutas por município de residência e ano "
        "de diagnóstico. Os desfechos apresentados são extrações separadas "
        "do TABNET e não devem ser somados como se fossem todos os resultados "
        "possíveis do tratamento."
    )

    st.divider()
    st.markdown("### Distribuição dos casos no Amazonas")

    titulo_recorte = "2019–2025" if ano == "Todos" else str(ano)
    if municipio == "Todos":
        titulo_grafico = f"Casos confirmados por município — {titulo_recorte}"
    else:
        titulo_grafico = f"Casos confirmados — {municipio} ({titulo_recorte})"

    # O gráfico ocupa toda a largura para que os nomes dos municípios
    # não sejam cortados nem desapareçam em telas menores.
    fig = criar_grafico_municipios(filtrado, titulo_grafico)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver ranking dos municípios",
        expanded=False):
        destaque = (
            filtrado.groupby("Município", as_index=False)["Casos confirmados"]
            .sum()
            .sort_values("Casos confirmados", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        # Criar a posição no ranking
        destaque.insert(
            0,
            "Posição",
            [f"{i}º" for i in range(1, len(destaque) + 1)]
        )

        # Formatar os números
        destaque["Casos confirmados"] = destaque["Casos confirmados"].apply(
            formatar_numero
        )

        st.dataframe(
            destaque,
            use_container_width=True,
            hide_index=True
        )

    st.markdown("### Mapa de incidência de abandono de tuberculose no Amazonas")
    # O mapa mantém todos os municípios visíveis mesmo quando um município
    # específico é escolhido no filtro. O filtro de ano continua sendo aplicado.
    dados_mapa = dados.copy()
    if ano != "Todos":
        dados_mapa = dados_mapa[
            dados_mapa["Ano"].astype(int) == int(ano)
        ].copy()
    rotulo_ano = "2019–2025" if ano == "Todos" else str(ano)
    mostrar_mapa_amazonas(
        dados_mapa,
        f"Proporção de abandono do tratamento da tuberculose por município — Amazonas ({rotulo_ano})"
    )

    st.divider()
    st.markdown("### Desfechos do tratamento")
    desfechos = pd.DataFrame({
        "Desfecho": ["Cura", "Abandono", "Óbito por tuberculose"],
        "Quantidade": [total_cura, total_abandono, total_obitos],
    })
    cores_desfechos = {
        "Cura": "#5878D8",
        "Abandono": "#E5A52D",
        "Óbito por tuberculose": "#D96B5F",
    }
    fig_desfechos = px.bar(
        desfechos,
        x="Desfecho",
        y="Quantidade",
        text="Quantidade",
        title="Desfechos selecionados — recorte atual",
        color="Desfecho",
        color_discrete_map=cores_desfechos,
    )
    fig_desfechos.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=12, color="#20344D"),
        hovertemplate="<b>%{x}</b><br>Registros: %{y:,.0f}<extra></extra>",
    )
    fig_desfechos.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        yaxis_title="Número de registros", xaxis_title="",
        showlegend=False,
        margin=dict(l=20, r=25, t=60, b=45),
    )
    st.plotly_chart(fig_desfechos, use_container_width=True)

    tabela = base_ano[
        [
            "Código IBGE", "Município", "Ano",
            "Casos confirmados", "Casos de cura",
            "Casos de abandono", "Óbitos por tuberculose",
        ]
    ].sort_values("Casos confirmados", ascending=False)
    st.markdown("### Resumo municipal")

    # A coluna Ano é convertida em texto apenas para exibição,
    # evitando que o Streamlit mostre 2,025 em vez de 2025.
    tabela_exibicao = tabela.copy()
    tabela_exibicao["Ano"] = pd.to_numeric(
        tabela_exibicao["Ano"], errors="coerce"
    ).map(lambda valor: str(int(valor)) if pd.notna(valor) else "")

    st.dataframe(
        tabela_exibicao,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "A taxa de abandono não é calculada nesta versão. Para apresentar "
        "uma taxa válida, é necessário definir o denominador oficial e "
        "considerar todos os desfechos elegíveis da mesma coorte, incluindo "
        "as demais categorias de encerramento e a completude dos registros."
    )


# =====================================================
# PÁGINA 2 — FATORES ASSOCIADOS
# =====================================================
elif page == "Fatores associados":
    st.subheader("Perfil sociodemográfico e epidemiológico dos casos de tuberculose")
    st.caption("Amazonas | 2019 a 2025 | Dados agregados do SINAN/DATASUS")
    st.markdown(
        "A página apresenta a distribuição dos registros segundo características "
        "sociodemográficas e epidemiológicas. Os percentuais de cada gráfico são "
        "calculados somente entre as categorias com informação conhecida. "
        "Como os arquivos de fatores foram extraídos em totais para 2019–2025, "
        "eles não mudam ao selecionar um ano na Visão geral."
    )

    try:
        # Sexo
        sexo = {
            "Masculino": total_fator("masculino"),
            "Feminino": total_fator("feminino")
        }
        sexo_ignorado = total_fator("sexo_ignorado")

        # Faixa etária: o arquivo 20 a 59 agrega as faixas 20-39 e 40-59.
        idade = {
            "Menor de 20 anos": total_fator("menor20"),
            "20 a 59 anos": total_fator("20a59"),
            "60 anos ou mais": total_fator("60mais")
        }

        # Escolaridade: categorias agrupadas sem misturar ignorados.
        escolaridade, escolaridade_ignorada = dados_escolaridade_fator()

        # HIV e álcool: ignorados são mostrados separadamente.
        hiv = {
            "HIV positivo": total_fator("hiv_positivo"),
            "HIV negativo": total_fator("hiv_negativo")
        }
        hiv_ignorado = total_fator("hiv_ignorado")

        alcool = {
            "Sim": total_fator("alcool_sim"),
            "Não": total_fator("alcool_nao")
        }
        alcool_ignorado = total_fator("alcool_ignorado")

        # Uso de outras drogas: categorias extraídas separadamente do SINAN.
        # Os registros ignorados/em branco permanecem como categoria própria.
        drogas = {
            "Sim": total_fator("drogas_sim"),
            "Não": total_fator("drogas_nao")
        }
        drogas_ignorado = total_fator("drogas_ignorado")

        raca = {
            "Branca": total_fator("raca_branca"),
            "Preta": total_fator("raca_preta"),
            "Parda": total_fator("raca_parda"),
            "Amarela": total_fator("raca_amarela"),
            "Indígena": total_fator("raca_indigena")
        }
        raca_ignorada = total_fator("raca_ignorada")

        # =================================================
        # PAINÉIS DE GRÁFICOS — DUAS COLUNAS
        # =================================================

        st.markdown("""
        <style>
        section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border: 1px solid #DCE5F0 !important;
            border-radius: 14px !important;
            padding: 12px !important;
            margin-bottom: 15px !important;
            box-shadow: 0 2px 7px rgba(16,45,89,0.06);
        }
        </style>
        """, unsafe_allow_html=True)

        # PRIMEIRA LINHA
        c1, c2 = st.columns(2, gap="large")

        with c1:
            with st.container(border=True):
                grafico_fator_rosca(
                    "Distribuição por sexo (2019–2025)", sexo
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(sexo_ignorado)} registros."
                )

        with c2:
            with st.container(border=True):
                grafico_fator_barras(
                    "Faixa etária (2019–2025)", idade
                )

        # SEGUNDA LINHA
        c3, c4 = st.columns(2, gap="large")

        with c3:
            with st.container(border=True):
                grafico_fator_barras(
                    "Escolaridade (2019–2025)", escolaridade
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(escolaridade_ignorada)} registros."
                )

        with c4:
            with st.container(border=True):
                grafico_fator_rosca(
                    "Coinfecção/situação HIV (2019–2025)", hiv
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(hiv_ignorado)} registros."
                )

        # TERCEIRA LINHA
        c5, c6 = st.columns(2, gap="large")

        with c5:
            with st.container(border=True):
                grafico_fator_rosca(
                    "Registro de uso de álcool (2019–2025)", alcool
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(alcool_ignorado)} registros."
                )

        with c6:
            with st.container(border=True):
                grafico_fator_rosca(
                    "Registro de uso de outras drogas (2019–2025)", drogas
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(drogas_ignorado)} registros."
                )

        # QUARTA LINHA
        c7, c8 = st.columns(2, gap="large")

        with c7:
            with st.container(border=True):
                grafico_fator_barras(
                    "Distribuição por raça/cor (2019–2025)", raca
                )
                st.caption(
                    f"Ignorado/em branco: {formatar_numero(raca_ignorada)} registros."
                )

        with c8:
            with st.container(border=True):
                st.markdown("#### Completude do registro de drogas")

                total_drogas = sum(drogas.values()) + drogas_ignorado

                quadro_drogas = pd.DataFrame([
                    {"Situação": "Sim", "Registros": drogas["Sim"]},
                    {"Situação": "Não", "Registros": drogas["Não"]},
                    {
                        "Situação": "Ignorado/em branco",
                        "Registros": drogas_ignorado
                    },
                ])

                if total_drogas > 0:
                    quadro_drogas["Percentual"] = (
                        quadro_drogas["Registros"] / total_drogas * 100
                    ).map(lambda x: f"{x:.1f}%".replace(".", ","))

                st.dataframe(
                    quadro_drogas,
                    use_container_width=True,
                    hide_index=True
                )
                

        st.info(
            "Os registros ignorados ou em branco são apresentados separadamente. "
            "Por isso, os percentuais dos gráficos consideram apenas as categorias "
            "com informação conhecida; a ausência de preenchimento não é tratada "
            "como resposta 'não'."
        )

        st.markdown("### Leitura dos resultados")
        st.markdown(
            "Os gráficos permitem descrever o perfil dos casos notificados, "
            "identificando como os registros se distribuem por sexo, idade, "
            "escolaridade, situação para HIV, uso de álcool, uso de outras drogas "
            "e raça/cor. "
            "Essas distribuições ajudam a orientar a vigilância e a discussão "
            "epidemiológica, mas não demonstram, isoladamente, que essas "
            "características causaram a doença ou o abandono do tratamento."
        )

    

        st.markdown("### Qualidade e completude das informações")
        quadro_qualidade = pd.DataFrame([
            {"Variável": "Sexo", "Registros ignorados/em branco": sexo_ignorado},
            {"Variável": "Escolaridade", "Registros ignorados/em branco": escolaridade_ignorada},
            {"Variável": "HIV", "Registros ignorados/em branco": hiv_ignorado},
            {"Variável": "Uso de álcool", "Registros ignorados/em branco": alcool_ignorado},
            {"Variável": "Uso de outras drogas", "Registros ignorados/em branco": drogas_ignorado},
            {"Variável": "Raça/cor", "Registros ignorados/em branco": raca_ignorada},
        ])
        st.dataframe(quadro_qualidade, use_container_width=True, hide_index=True)

        st.caption(
            "Fonte: SINAN/DATASUS. Período de diagnóstico: 2019–2025. "
            "Dados agregados por município de residência. Os totais são somados "
            "a partir das linhas municipais, sem somar novamente subtotais "
            "das regiões de saúde."
        )

    except Exception as erro:
        st.error(f"Não foi possível carregar o perfil sociodemográfico: {erro}")
        st.info(
            "Confira se todos os CSVs dos fatores associados estão na pasta 'dados' "
            "com os nomes indicados no código, inclusive drogas sim.csv, "
            "drogas não.csv e drogas ignorado.csv."
        )

# =====================================================
# PÁGINA 4 — CLASSIFICAÇÃO DE RISCO
# =====================================================
elif page == "Classificação de risco de abandono":
    st.write(
        "Questionário demonstrativo de fatores que podem "
        "dificultar a continuidade do tratamento da tuberculose."
    )
    

    with st.form("formulario_risco_abandono"):
        st.markdown("### 1. Características")
        idade = st.selectbox(
            "Faixa etária",
            ["Selecione", "Menor de 20 anos", "20 a 59 anos", "60 anos ou mais"]
        )
        sexo = st.selectbox(
            "Sexo", ["Selecione", "Masculino", "Feminino"]
        )
        escolaridade = st.selectbox(
            "Escolaridade",
            ["Selecione", "Sem escolaridade", "Ensino fundamental",
             "Ensino médio", "Ensino superior"]
        )

        st.markdown("### 2. Fatores associados")
        alcool = st.radio("Uso de álcool", ["Não", "Sim"], horizontal=True)
        drogas = st.radio("Uso de outras drogas", ["Não", "Sim"], horizontal=True)
        hiv = st.radio(
            "Coinfecção TB/HIV", ["Não", "Sim", "Não informado"],
            horizontal=True
        )
        distancia = st.selectbox(
            "Distância até a unidade de saúde",
            ["Selecione", "Até 5 km", "Entre 5 e 20 km", "Mais de 20 km"]
        )
        historico_abandono = st.radio(
            "Histórico de abandono de tratamento",
            ["Não", "Sim"], horizontal=True
        )
        st.markdown("""
<style>
/* Cartões dos gráficos de fatores associados */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DCE6F1 !important;
    border-radius: 14px !important;
    padding: 12px !important;
    box-shadow: 0 2px 7px rgba(16, 45, 89, 0.06);
}

/* Espaçamento interno dos gráficos */
div[data-testid="stPlotlyChart"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
div.stButton > button,
div[data-testid="stFormSubmitButton"] > button {
    background-color: #5369B5 !important;
    color: white !important;
    font-weight: bold !important;
    border: none !important;
    border-radius: 10px !important;
    min-height: 45px !important;
    opacity: 1 !important;
}

div[data-testid="stFormSubmitButton"] > button p {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)
        enviar = st.form_submit_button(
            "Calcular classificação demonstrativa",
            use_container_width=True
        )
    if enviar:
        if "Selecione" in [idade, sexo, escolaridade, distancia]:
            st.error("Preencha os campos obrigatórios.")
        else:
            fatores = {
                "Faixa etária": 1 if idade in [
                    "Menor de 20 anos", "60 anos ou mais"
                ] else 0,
                "Escolaridade": 1 if escolaridade in [
                    "Sem escolaridade", "Ensino fundamental"
                ] else 0,
                "Uso de álcool": 1 if alcool == "Sim" else 0,
                "Uso de outras drogas": 2 if drogas == "Sim" else 0,
                "Coinfecção TB/HIV": 2 if hiv == "Sim" else 0,
                "Distância da unidade": (
                    1 if distancia == "Entre 5 e 20 km"
                    else 2 if distancia == "Mais de 20 km"
                    else 0
                ),
                "Histórico de abandono": 3 if historico_abandono == "Sim" else 0,
            }

            pontuacao = sum(fatores.values())

            if pontuacao <= 2:
                classificacao = "ATENÇÃO HABITUAL"
                cor = "#20A45A"
                orientacao = (
                    "Manter acompanhamento regular na unidade de saúde, "
                    "consultas e retirada dos medicamentos conforme orientação."
                )

            elif pontuacao <= 5:
                classificacao = "ATENÇÃO AMPLIADA"
                cor = "#F39C12"
                orientacao = (
                    "Avaliar barreiras de acesso, necessidade de contato mais "
                    "próximo com a equipe e apoio social."
                )

            else:
                classificacao = "ATENÇÃO PRIORITÁRIA"
                cor = "#D62828"
                orientacao = (
                    "Recomenda-se avaliação individual pela equipe responsável "
                    "e planejamento de apoio multiprofissional."
                )

            # RESULTADO
            st.markdown(
                f"""
                <div style="
                    background:{cor}18;
                    border-left:6px solid {cor};
                    padding:15px;
                    border-radius:10px;
                    margin:15px 0;
                ">
                    <h3 style="color:{cor}; margin:0;">
                        {classificacao}
                    </h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            c1, c2 = st.columns(2)

            c1.metric("Pontuação ilustrativa", f"{pontuacao} / 11")

            c2.markdown(
                f"""
                <div style="padding-top:8px;">
                    <p style="color:#666; margin-bottom:4px;">Classificação</p>
                    <h3 style="color:{cor}; margin-top:0;">
                        {classificacao}
                    </h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            # GRÁFICO DOS FATORES
            st.markdown("### Pontuação atribuída aos fatores")

            grafico_fatores = pd.DataFrame([
                {"Fator": chave, "Pontuação": valor}
                for chave, valor in fatores.items()
            ])

            grafico_fatores = grafico_fatores[
                grafico_fatores["Pontuação"] > 0
            ].sort_values("Pontuação", ascending=True)

            if not grafico_fatores.empty:
                fig = px.bar(
                    grafico_fatores,
                    x="Pontuação",
                    y="Fator",
                    orientation="h",
                    text="Pontuação",
                    color_discrete_sequence=[cor]
                )

                fig.update_traces(
                    textposition="outside",
                    cliponaxis=False,
                    texttemplate="%{text} ponto(s)",
                    textfont=dict(size=12, color="#20344D")
                )

                fig.update_layout(
                    height=420,
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    xaxis_title="Pontuação",
                    yaxis_title="",
                    showlegend=False,
                    margin=dict(l=20, r=90, t=30, b=40),
                    xaxis=dict(
                        dtick=1,
                        rangemode="tozero"
                    )
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )
            else:
                st.info("Nenhum fator recebeu pontuação.")

# =====================================================
# ORIENTAÇÕES CONFORME A CLASSIFICAÇÃO DE RISCO
# =====================================================
# A classificação e as orientações são calculadas dentro do formulário
# e exibidas logo em seguida, sem duplicar blocos condicionais.
    if "pontuacao" in locals() and pontuacao <= 2:
        titulo_orientacao = "Acompanhamento de rotina"
        orientacao = """
        Seu resultado indica necessidade de acompanhamento habitual.

        Continue comparecendo às consultas, utilizando os medicamentos
        conforme a orientação da equipe de saúde e realizando o tratamento
        até o final.

        Caso encontre alguma dificuldade, converse com o profissional
        responsável pelo seu acompanhamento.
        """
    elif "pontuacao" in locals() and pontuacao <= 5:
        titulo_orientacao = "Acompanhamento reforçado"
        orientacao = """
        Seu resultado indica a necessidade de maior atenção durante
        o tratamento.

        É importante manter contato frequente com a equipe de saúde,
        comparecer às consultas e comunicar qualquer dificuldade para
        tomar os medicamentos ou seguir o tratamento.

        O apoio dos profissionais pode ajudar a evitar interrupções.
        """
    elif "pontuacao" in locals():
        titulo_orientacao = "Acompanhamento prioritário"
        orientacao = """
        Seu resultado indica necessidade de acompanhamento prioritário.

        Procure a equipe de saúde para conversar sobre possíveis
        dificuldades durante o tratamento e receber o apoio necessário.

        A equipe poderá organizar um acompanhamento mais próximo,
        identificar situações que dificultem a continuidade do tratamento
        e ajudar a evitar o abandono.
        """


    # Exibição das orientações
    titulo_orientacao = "Orientação"
    st.markdown(f"#### {titulo_orientacao}")
    st.markdown("### Orientações ao usuário")
    st.markdown(f"#### {titulo_orientacao}")

    st.markdown(
        f"""
        <div style="
            background-color: #F3F5FA;
            border-left: 5px solid #1769AA;
            padding: 18px;
            border-radius: 9px;
            margin-top: 10px;
            margin-bottom: 18px;
            color: #20344D;
            line-height: 1.7;
        ">
            {orientacao.replace(chr(10), '<br>')}
        </div>
        """,
        unsafe_allow_html=True
    )


    # Onde buscar ajuda
    st.markdown("""
    <div style="
        background-color: #EAF2FB;
        border-left: 5px solid #1769AA;
        padding: 16px;
        border-radius: 9px;
        margin-bottom: 15px;
        color: #20344D;
    ">
        <h4 style="color:#102D59; margin-top:0;">
            Onde buscar ajuda?
        </h4>
        <p>
            Procure a Unidade Básica de Saúde (UBS) mais próxima
            para receber orientações, acompanhamento e apoio durante
            o tratamento da tuberculose. 
        </p>
    </div>
    """, unsafe_allow_html=True)


    # Aviso importante
    st.warning(
        "Importante: a classificação apresentada pelo TB-VIGIA possui "
        "finalidade exclusivamente educativa e demonstrativa. A pontuação "
        "não representa diagnóstico nem previsão clínica validada de abandono "
        "do tratamento. O resultado não substitui a avaliação individual "
        "do paciente nem a decisão dos profissionais de saúde."
    )

    # =====================================================
# PÁGINA 5 — RELATÓRIOS
# =====================================================
elif page == "Relatórios":
    st.subheader("Relatórios e exportações")

    # Tabela municipal
    relatorio = base_ano[
        [
            "Código IBGE",
            "Município",
            "Ano",
            "Casos confirmados",
            "Casos de cura",
            "Casos de abandono",
            "Óbitos por tuberculose",
        ]
    ].sort_values(
        "Casos confirmados",
        ascending=False
    ).copy()

    # Corrigir o ano para não aparecer como 2,019
    relatorio["Ano"] = (
        pd.to_numeric(relatorio["Ano"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .replace("<NA>", "")
    )

    # Exibir somente uma tabela
    st.dataframe(
        relatorio,
        use_container_width=True,
        hide_index=True
    )

    # Preparar arquivo para download
    exportar = relatorio.copy()

    # Criar série histórica
    serie_base = dados.copy()

    if ano != "Todos":
        serie_base = serie_base[
            serie_base["Ano"].astype(int) == int(ano)
        ]

    if municipio != "Todos":
        serie_base = serie_base[
            serie_base["Município"] == municipio
        ]

    serie = montar_tabela_serie(serie_base)

    if "Ano" in serie.columns:
        serie["Ano"] = (
            pd.to_numeric(serie["Ano"], errors="coerce")
            .astype("Int64")
            .astype(str)
            .replace("<NA>", "")
        )

    # Botões de exportação lado a lado
    st.markdown("### Exportar relatórios")

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.download_button(
            label="Baixar tabela municipal em CSV",
            data=exportar.to_csv(index=False).encode("utf-8-sig"),
            file_name=(
                "tb_vigia_amazonas_2019_2025.csv"
                if ano == "Todos"
                else f"tb_vigia_amazonas_{ano}.csv"
            ),
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="Baixar série histórica 2019–2025",
            data=serie.to_csv(index=False).encode("utf-8-sig"),
            file_name="tb_vigia_serie_historica_filtrada.csv",
            mime="text/csv",
            use_container_width=True
        )

    # =====================================================
# PÁGINA 6 — SOBRE O SISTEMA
# =====================================================
elif page == "Sobre o sistema":

    st.markdown("## Sobre o TB-VIGIA")

    st.markdown("### 1. Apresentação")

    st.write("""
    O TB-VIGIA é uma plataforma desenvolvida com a finalidade
    de reunir, organizar e apresentar informações epidemiológicas sobre
    a tuberculose no estado do Amazonas.

    A ferramenta permite visualizar indicadores relacionados aos casos
    confirmados, desfechos do tratamento e características
    sociodemográficas, contribuindo para a compreensão do cenário
    epidemiológico da doença.
    """)
    st.markdown("### 3. Funcionalidades")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="background:#EAF2FB; padding:17px; border-radius:10px;
        margin-bottom:12px; color:#20344D;">
            <h4 style="color:#174A8B;">Monitoramento epidemiológico</h4>
            Visualização de casos confirmados e desfechos do tratamento.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#EAF2FB; padding:17px; border-radius:10px;
        color:#20344D;">
            <h4 style="color:#174A8B;">Fatores associados</h4>
            Análise de informações sociodemográficas e características
            relacionadas aos registros.
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background:#EAF2FB; padding:17px; border-radius:10px;
        margin-bottom:12px; color:#20344D;">
            <h4 style="color:#174A8B;">Distribuição municipal</h4>
            Apresentação de informações por município e mapas temáticos.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#EAF2FB; padding:17px; border-radius:10px;
        color:#20344D;">
            <h4 style="color:#174A8B;">Classificação demonstrativa</h4>
            Questionário de estratificação de fatores que podem dificultar
            a continuidade do tratamento.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 4. Fonte e período dos dados")

    st.write("""
    O sistema utiliza dados epidemiológicos provenientes de arquivos
    extraídos do Sistema de Informação de Agravos de Notificação (SINAN),
    disponibilizados por meio do DATASUS.

    O período de análise contemplado nesta versão corresponde aos anos
    de 2019 a 2025, considerando os registros disponíveis nas bases
    utilizadas para o desenvolvimento do protótipo.
    """)

    st.markdown("### 5. Metodologia e limitações")

    st.write("""
    Os dados foram organizados em tabelas e indicadores para permitir
    consultas, comparações e visualizações epidemiológicas.

    A classificação de risco de abandono do tratamento possui caráter
    exclusivamente demonstrativo e educativo. A pontuação foi elaborada
    para ilustrar a análise de fatores que podem dificultar a continuidade
    do tratamento, não constituindo instrumento clínico validado ou
    preditor individual de abandono.

    """)

    st.markdown("### 6. Finalidade")

    st.info("""
    O TB-VIGIA busca contribuir para a organização e interpretação
    das informações epidemiológicas da tuberculose no Amazonas,
    oferecendo um ambiente de consulta e visualização de dados que
    possa apoiar atividades acadêmicas, educativas e discussões
    relacionadas à vigilância em saúde.
    """)

    st.caption("TB-VIGIA | Protótipo acadêmico | Dados epidemiológicos de 2019 a 2025")
