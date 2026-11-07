from pathlib import Path
import unicodedata

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
.stApp { background: #F4F7FB; }
section[data-testid="stSidebar"] { background: #102D59; }
section[data-testid="stSidebar"] * { color: white !important; }
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
    st.markdown("## 🫁 TB-VIGIA")
    st.caption("Vigilância Epidemiológica da Tuberculose")
    st.caption("Amazonas • Brasil")
    page = st.radio(
        "NAVEGAÇÃO",
        [
            "Visão geral",
            "Indicadores",
            "Fatores associados",
            "Classificação de risco",
            "Relatórios",
            "Sobre o sistema",
        ],
    )
    st.markdown("---")
    st.caption("Projeto acadêmico em desenvolvimento")
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
# FILTROS
# =====================================================
anos_disponiveis = sorted(dados["Ano"].dropna().astype(int).unique().tolist())
municipios_disponiveis = sorted(dados["Município"].dropna().unique().tolist())

if not anos_disponiveis:
    st.error("Não existem anos disponíveis nas bases.")
    st.stop()

if page == "Classificação de risco":
    ano = anos_disponiveis[-1]
    municipio = "Todos os municípios"
else:
    st.markdown("### Filtros epidemiológicos")
    f1, f2 = st.columns([1, 2])
    with f1:
        ano = st.selectbox(
            "Ano do diagnóstico",
            anos_disponiveis,
            index=len(anos_disponiveis) - 1,
            key=f"ano_{page}"
        )
    with f2:
        municipio = st.selectbox(
            "Município",
            ["Todos os municípios"] + municipios_disponiveis,
            key=f"municipio_{page}"
        )

filtrado = dados[dados["Ano"].astype(int) == int(ano)].copy()
if municipio != "Todos os municípios":
    filtrado = filtrado[filtrado["Município"] == municipio].copy()

base_ano = dados[dados["Ano"].astype(int) == int(ano)].copy()
if municipio != "Todos os municípios":
    base_ano = base_ano[base_ano["Município"] == municipio].copy()


# =====================================================
# GRÁFICOS E RESUMOS
# =====================================================
def criar_grafico_municipios(df, titulo, coluna="Casos confirmados"):
    grafico = (
        df.groupby("Município", as_index=False)[coluna]
        .sum()
        .sort_values(coluna, ascending=True)
    )
    grafico["Rótulo"] = grafico[coluna].apply(formatar_numero)
    fig = px.bar(
        grafico,
        x=coluna,
        y="Município",
        orientation="h",
        text="Rótulo",
        title=titulo,
        color_discrete_sequence=["#1769AA"],
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        height=max(420, len(grafico) * 30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=70, t=65, b=45),
        font=dict(family="Arial", color="#20344D"),
        showlegend=False,
    )
    return fig


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
    "hiv_negativo": "hiv negativo .csv",
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
    candidatos = [PASTA_DADOS / nome, BASE_DIR / nome]
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    raise FileNotFoundError(
        f"Não encontrei o arquivo {nome}. Coloque-o na pasta 'dados'."
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
    df = pd.DataFrame({"Categoria": list(valores.keys()), "Registros": list(valores.values())})
    df = df[df["Registros"] > 0].copy()
    if df.empty:
        st.info("Não há registros disponíveis para este gráfico.")
        return
    total = df["Registros"].sum()
    df["Percentual"] = df["Registros"] / total * 100
    fig = px.bar(
        df.sort_values("Registros"), x="Registros", y="Categoria",
        orientation="h", text="Percentual", title=titulo,
        color_discrete_sequence=["#397DBB"]
    )
    fig.update_traces(
        texttemplate="%{text:.1f}%", textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Registros: %{x:,.0f}<br>Percentual: %{text:.1f}%<extra></extra>"
    )
    fig.update_layout(
        height=330, paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Arial", size=11, color="#20344D"),
        xaxis_title="Número de registros", yaxis_title="",
        margin=dict(l=12, r=55, t=55, b=30), showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)


def grafico_fator_rosca(titulo, valores):
    df = pd.DataFrame({"Categoria": list(valores.keys()), "Registros": list(valores.values())})
    df = df[df["Registros"] > 0].copy()
    if df.empty:
        st.info("Não há registros disponíveis para este gráfico.")
        return
    fig = px.pie(
        df, names="Categoria", values="Registros", hole=0.58, title=titulo,
        color_discrete_sequence=["#1554B8", "#8EB2E8", "#C9D4E5"]
    )
    fig.update_traces(
        textposition="inside", textinfo="percent",
        hovertemplate="<b>%{label}</b><br>Registros: %{value:,.0f}<br>Percentual: %{percent}<extra></extra>"
    )
    fig.update_layout(
        height=330, paper_bgcolor="white",
        font=dict(family="Arial", size=11, color="#20344D"),
        margin=dict(l=10, r=10, t=55, b=35),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center")
    )
    st.plotly_chart(fig, use_container_width=True)


# =====================================================
# PÁGINA 1 — VISÃO GERAL
# =====================================================
if page == "Visão geral":
    st.markdown("### Panorama epidemiológico")

    total_confirmados = somar(filtrado, "Casos confirmados")
    total_cura = somar(filtrado, "Casos de cura")
    total_abandono = somar(filtrado, "Casos de abandono")
    total_obitos = somar(filtrado, "Óbitos por tuberculose")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Casos confirmados", formatar_numero(total_confirmados))
    c2.metric("Casos de cura", formatar_numero(total_cura))
    c3.metric("Casos de abandono", formatar_numero(total_abandono))
    c4.metric("Óbitos por tuberculose", formatar_numero(total_obitos))

    st.caption(
        "Os valores são contagens absolutas por município de residência e ano "
        "de diagnóstico. Os desfechos apresentados são extrações separadas "
        "do TABNET e não devem ser somados como se fossem todos os resultados "
        "possíveis do tratamento."
    )

    st.divider()
    st.markdown("### Distribuição dos casos no Amazonas")

    col_grafico, col_ranking = st.columns([1.5, 1])
    with col_grafico:
        if municipio == "Todos os municípios":
            grafico = (
                base_ano.sort_values("Casos confirmados", ascending=False)
                .head(15)
            )
            fig = criar_grafico_municipios(
                grafico, "15 municípios com maior número de casos"
            )
        else:
            fig = criar_grafico_municipios(
                filtrado, f"Casos confirmados — {municipio}"
            )
        st.plotly_chart(fig, use_container_width=True)

    with col_ranking:
        st.markdown("#### Municípios em destaque")
        destaque = (
            base_ano.groupby("Município", as_index=False)["Casos confirmados"]
            .sum()
            .sort_values("Casos confirmados", ascending=False)
            .head(10)
        )
        st.dataframe(destaque, use_container_width=True, hide_index=True, height=420)

    st.divider()
    st.markdown("### Desfechos do tratamento")
    desfechos = pd.DataFrame({
        "Desfecho": ["Cura", "Abandono", "Óbito por tuberculose"],
        "Quantidade": [total_cura, total_abandono, total_obitos],
    })
    fig_desfechos = px.bar(
        desfechos,
        x="Desfecho",
        y="Quantidade",
        text="Quantidade",
        title="Desfechos selecionados — recorte atual",
        color_discrete_sequence=["#1769AA"],
    )
    fig_desfechos.update_traces(textposition="outside")
    fig_desfechos.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        yaxis_title="Número de registros", xaxis_title=""
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
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    st.info(
        "A taxa de abandono não é calculada nesta versão. Para apresentar "
        "uma taxa válida, é necessário definir o denominador oficial e "
        "considerar todos os desfechos elegíveis da mesma coorte, incluindo "
        "as demais categorias de encerramento e a completude dos registros."
    )


# =====================================================
# PÁGINA 2 — INDICADORES
# =====================================================
elif page == "Indicadores":
    st.subheader("Indicadores epidemiológicos")
    st.caption(f"Período selecionado: {ano} | Município: {municipio}")

    total = somar(filtrado, "Casos confirmados")
    total_cura = somar(filtrado, "Casos de cura")
    total_abandono = somar(filtrado, "Casos de abandono")
    total_obitos = somar(filtrado, "Óbitos por tuberculose")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Casos confirmados", formatar_numero(total))
    c2.metric("Cura", formatar_numero(total_cura))
    c3.metric("Abandono", formatar_numero(total_abandono))
    c4.metric("Óbitos por TB", formatar_numero(total_obitos))

    serie = montar_tabela_serie(
        dados if municipio == "Todos os municípios"
        else dados[dados["Município"] == municipio]
    )

    st.markdown("### Evolução anual dos casos e desfechos")
    serie_longa = serie.melt(
        id_vars="Ano",
        var_name="Indicador",
        value_name="Quantidade"
    )
    fig = px.line(
        serie_longa,
        x="Ano",
        y="Quantidade",
        color="Indicador",
        markers=True,
        title="Série histórica de 2019 a 2025",
    )
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(dtick=1), yaxis_title="Número de registros"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Tabela anual")
    st.dataframe(serie, use_container_width=True, hide_index=True)

    st.warning(
        "As contagens de cura, abandono e óbito são categorias selecionadas "
        "de situação de encerramento. Não representam, isoladamente, todos "
        "os desfechos. A taxa oficial de abandono permanece pendente da "
        "definição e validação do denominador metodológico."
    )


# =====================================================
# PÁGINA 3 — FATORES ASSOCIADOS
# =====================================================
elif page == "Fatores associados":
    st.subheader("Perfil sociodemográfico e epidemiológico dos casos de tuberculose")
    st.caption("Amazonas | 2019 a 2025 | Dados agregados do SINAN/DATASUS")
    st.markdown(
        "A página apresenta a distribuição dos registros segundo características "
        "sociodemográficas e epidemiológicas. Os percentuais de cada gráfico são "
        "calculados somente entre as categorias com informação conhecida."
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

        # Painéis em duas colunas, seguindo a referência visual.
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                grafico_fator_rosca("Distribuição por sexo (2019–2025)", sexo)
                st.caption(f"Ignorado/em branco: {formatar_numero(sexo_ignorado)} registros.")
        with c2:
            with st.container(border=True):
                grafico_fator_barras("Faixa etária (2019–2025)", idade)

        c3, c4 = st.columns(2)
        with c3:
            with st.container(border=True):
                grafico_fator_barras("Escolaridade (2019–2025)", escolaridade)
                st.caption(f"Ignorado/em branco: {formatar_numero(escolaridade_ignorada)} registros.")
        with c4:
            with st.container(border=True):
                grafico_fator_rosca("Coinfecção/situação HIV (2019–2025)", hiv)
                st.caption(f"Ignorado/em branco: {formatar_numero(hiv_ignorado)} registros.")

        c5, c6 = st.columns(2)
        with c5:
            with st.container(border=True):
                grafico_fator_rosca("Registro de uso de álcool (2019–2025)", alcool)
                st.caption(f"Ignorado/em branco: {formatar_numero(alcool_ignorado)} registros.")
        with c6:
            with st.container(border=True):
                grafico_fator_barras("Raça/cor (2019–2025)", raca)
                st.caption(f"Ignorado/em branco: {formatar_numero(raca_ignorada)} registros.")

        c7, c8 = st.columns(2)
        with c7:
            with st.container(border=True):
                grafico_fator_rosca("Registro de uso de outras drogas (2019–2025)", drogas)
                st.caption(f"Ignorado/em branco: {formatar_numero(drogas_ignorado)} registros.")
        with c8:
            with st.container(border=True):
                st.markdown("#### Completude do registro de uso de drogas")
                total_drogas = sum(drogas.values()) + drogas_ignorado
                quadro_drogas = pd.DataFrame([
                    {"Situação do registro": "Sim", "Registros": drogas["Sim"]},
                    {"Situação do registro": "Não", "Registros": drogas["Não"]},
                    {"Situação do registro": "Ignorado/em branco", "Registros": drogas_ignorado},
                ])
                if total_drogas > 0:
                    quadro_drogas["Percentual do total"] = (
                        quadro_drogas["Registros"] / total_drogas * 100
                    ).map(lambda x: f"{x:.1f}%".replace(".", ","))
                st.dataframe(quadro_drogas, use_container_width=True, hide_index=True)

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

        st.warning(
            "Nota metodológica: para afirmar que uma característica está associada "
            "ao abandono do tratamento, é necessário comparar os desfechos "
            "(abandono e não abandono) entre as categorias da variável. Os gráficos "
            "desta página são descritivos e não estabelecem causalidade."
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
elif page == "Classificação de risco":
    st.subheader("Estratificação demonstrativa da necessidade de acompanhamento")
    st.write(
        "Questionário demonstrativo para discussão de fatores que podem "
        "dificultar a continuidade do tratamento da tuberculose."
    )
    st.info(
        "Protótipo acadêmico: pesos e faixas ilustrativos, não validados "
        "clinicamente. Não representam probabilidade individual de abandono."
    )

    with st.form("formulario_risco_abandono"):
        st.markdown("### 1. Características")
        idade = st.selectbox(
            "Faixa etária",
            ["Selecione", "Menor de 20 anos", "20 a 59 anos", "60 anos ou mais"]
        )
        sexo = st.selectbox(
            "Sexo", ["Selecione", "Masculino", "Feminino", "Não informado"]
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
                st.success(classificacao)
                orientacao = (
                    "Manter acompanhamento regular na unidade de saúde, "
                    "consultas e retirada dos medicamentos conforme orientação."
                )
            elif pontuacao <= 5:
                classificacao = "ATENÇÃO AMPLIADA"
                st.warning(classificacao)
                orientacao = (
                    "Avaliar barreiras de acesso, necessidade de contato mais "
                    "próximo com a equipe e apoio social."
                )
            else:
                classificacao = "ATENÇÃO PRIORITÁRIA"
                st.error(classificacao)
                orientacao = (
                    "Recomenda-se avaliação individual pela equipe responsável "
                    "e planejamento de apoio multiprofissional."
                )

            c1, c2 = st.columns(2)
            c1.metric("Pontuação ilustrativa", f"{pontuacao} / 11")
            c2.metric("Classificação", classificacao)

            grafico_fatores = pd.DataFrame(
                [{"Fator": k, "Pontuação": v} for k, v in fatores.items()]
            )
            fig = px.bar(
                grafico_fatores.sort_values("Pontuação"),
                x="Pontuação", y="Fator", orientation="h",
                text="Pontuação", title="Pontuação atribuída aos fatores",
                color_discrete_sequence=["#1769AA"]
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                paper_bgcolor="white", plot_bgcolor="white",
                xaxis_title="Pontos", yaxis_title=""
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("### Orientações")
            st.write(orientacao)
            st.info(
                "Este resultado é exclusivamente demonstrativo. Não substitui "
                "avaliação clínica, decisão da equipe ou instrumento validado."
            )

    st.divider()
    st.markdown("### Distribuição municipal dos casos no ano mais recente")
    ranking_risco = (
        base_ano.groupby("Município", as_index=False)["Casos confirmados"]
        .sum().sort_values("Casos confirmados", ascending=False)
    )
    st.dataframe(ranking_risco.head(10), use_container_width=True, hide_index=True)


# =====================================================
# PÁGINA 5 — RELATÓRIOS
# =====================================================
elif page == "Relatórios":
    st.subheader("Relatórios e exportações")
    exportar = base_ano[
        [
            "Código IBGE", "Município", "Ano",
            "Casos confirmados", "Casos de cura",
            "Casos de abandono", "Óbitos por tuberculose",
        ]
    ].sort_values("Casos confirmados", ascending=False)

    st.dataframe(exportar, use_container_width=True, hide_index=True)
    st.download_button(
        "Baixar tabela municipal em CSV",
        data=exportar.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"tb_vigia_amazonas_{ano}.csv",
        mime="text/csv",
    )

    serie = montar_tabela_serie(
        dados if municipio == "Todos os municípios"
        else dados[dados["Município"] == municipio]
    )
    st.markdown("### Exportar série histórica")
    st.download_button(
        "Baixar série histórica 2019–2025",
        data=serie.to_csv(index=False).encode("utf-8-sig"),
        file_name="tb_vigia_serie_historica_2019_2025.csv",
        mime="text/csv",
    )


# =====================================================
# PÁGINA 6 — SOBRE O SISTEMA
# =====================================================
elif page == "Sobre o sistema":
    st.subheader("Sobre o TB-VIGIA")
    st.markdown("""
    ### Vigilância Epidemiológica da Tuberculose

    O **TB-VIGIA** é um protótipo acadêmico desenvolvido para organizar,
    visualizar e analisar indicadores epidemiológicos da tuberculose
    no estado do Amazonas.

    ### Objetivos
    - Apresentar a distribuição dos casos por município.
    - Visualizar a evolução anual de 2019 a 2025.
    - Acompanhar contagens selecionadas de cura, abandono e óbito por TB.
    - Apoiar a interpretação de dados públicos de vigilância.

    ### Fonte
    Sistema de Informação de Agravos de Notificação (SINAN), disponibilizado
    pelo DATASUS.

    ### Metodologia e limitações
    Os dados são agregados por município de residência e ano de diagnóstico.
    As contagens absolutas não são taxas de incidência. As categorias de
    desfecho apresentadas são seleções específicas e não abrangem todos os
    resultados possíveis do tratamento. A taxa de abandono somente deverá
    ser incluída após definição do denominador conforme a metodologia oficial.

    O protótipo não substitui os sistemas oficiais de vigilância, não realiza
    diagnóstico e não prevê risco individual.
    """)
    st.caption("TB-VIGIA | Amazonas | Série histórica 2019–2025")
