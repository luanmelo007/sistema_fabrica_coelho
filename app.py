"""
Dashboard de Acompanhamento de Manutenção e OEE
Fonte de dados: 2 planilhas Google Sheets alimentadas por Google Forms
  - "Producao": 1 registro por turno/máquina
  - "Paradas" : 1 registro por evento de parada

Rode com: streamlit run app.py
"""

import datetime as dt

import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="OEE - Acompanhamento de Manutenção", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ---------------------------------------------------------------------------
# Conexão com o Google Sheets
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    """Cria o client autenticado usando a service account em st.secrets."""
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def has_google_credentials() -> bool:
    try:
        return "gcp_service_account" in st.secrets and "sheets" in st.secrets
    except Exception:
        return False


@st.cache_data(ttl=300, show_spinner="Lendo planilhas do Google Sheets...")
def load_real_data():
    client = get_gspread_client()
    producao_id = st.secrets["sheets"]["producao_sheet_id"]
    paradas_id = st.secrets["sheets"]["paradas_sheet_id"]

    producao_ws = client.open_by_key(producao_id).sheet1
    paradas_ws = client.open_by_key(paradas_id).sheet1

    df_producao = pd.DataFrame(producao_ws.get_all_records())
    df_paradas = pd.DataFrame(paradas_ws.get_all_records())
    return normalize_columns(df_producao), normalize_columns(df_paradas)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de coluna vindos do Forms (acentos, espaços, maiúsculas)."""
    rename_map = {
        "Carimbo de data/hora": "carimbo",
        "Data": "data",
        "Turno": "turno",
        "Máquina": "maquina",
        "Maquina": "maquina",
        "Operador responsável": "operador",
        "Tempo Planejado de Produção (min)": "tempo_planejado_min",
        "Tempo de Ciclo Ideal (segundos/peça)": "tempo_ciclo_ideal_seg",
        "Quantidade Produzida (peças)": "qtd_produzida",
        "Quantidade Refugada (peças)": "qtd_refugada",
        "Observações": "obs",
        "Tipo de Parada": "tipo_parada",
        "Motivo da Parada": "motivo",
        "Duração da Parada (min)": "duracao_min",
        "Técnico responsável": "tecnico",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Dados de demonstração (usados quando não há credenciais configuradas)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_demo_data():
    rng = np.random.default_rng(42)
    maquinas = ["Torno CNC 01", "Fresadora 02", "Prensa Hidráulica 03", "Injetora 04"]
    turnos = ["Manhã", "Tarde", "Noite"]
    motivos = [
        "Falha elétrica",
        "Falha mecânica",
        "Troca de ferramenta",
        "Falta de material",
        "Ajuste de setup",
        "Manutenção preventiva",
        "Outro",
    ]
    dias = pd.date_range(end=dt.date.today(), periods=21).date

    producao_rows = []
    paradas_rows = []
    for dia in dias:
        for maquina in maquinas:
            for turno in turnos:
                tempo_planejado = 440  # min, turno de ~7h20 já sem paradas programadas
                ciclo_ideal = rng.uniform(8, 25)  # segundos/peça
                qtd_produzida = int(rng.uniform(700, 1600))
                qtd_refugada = int(qtd_produzida * rng.uniform(0.0, 0.06))
                producao_rows.append(
                    {
                        "data": dia,
                        "turno": turno,
                        "maquina": maquina,
                        "tempo_planejado_min": tempo_planejado,
                        "tempo_ciclo_ideal_seg": ciclo_ideal,
                        "qtd_produzida": qtd_produzida,
                        "qtd_refugada": qtd_refugada,
                    }
                )
                n_paradas = rng.poisson(1.1)
                for _ in range(n_paradas):
                    paradas_rows.append(
                        {
                            "data": dia,
                            "turno": turno,
                            "maquina": maquina,
                            "tipo_parada": rng.choice(
                                ["Planejada", "Não Planejada"], p=[0.25, 0.75]
                            ),
                            "motivo": rng.choice(motivos),
                            "duracao_min": float(rng.uniform(5, 60)),
                        }
                    )

    df_producao = pd.DataFrame(producao_rows)
    df_producao["data"] = pd.to_datetime(df_producao["data"])
    df_paradas = pd.DataFrame(paradas_rows)
    df_paradas["data"] = pd.to_datetime(df_paradas["data"])
    return df_producao, df_paradas


# ---------------------------------------------------------------------------
# Cálculo do OEE
# ---------------------------------------------------------------------------


def calcular_oee(df_producao: pd.DataFrame, df_paradas: pd.DataFrame) -> pd.DataFrame:
    chave = ["data", "turno", "maquina"]

    paradas_np = (
        df_paradas[df_paradas["tipo_parada"] == "Não Planejada"]
        .groupby(chave)["duracao_min"]
        .sum()
        .rename("parada_nao_planejada_min")
    )
    paradas_p = (
        df_paradas[df_paradas["tipo_parada"] == "Planejada"]
        .groupby(chave)["duracao_min"]
        .sum()
        .rename("parada_planejada_min")
    )

    df = df_producao.merge(paradas_np, on=chave, how="left").merge(
        paradas_p, on=chave, how="left"
    )
    df["parada_nao_planejada_min"] = df["parada_nao_planejada_min"].fillna(0)
    df["parada_planejada_min"] = df["parada_planejada_min"].fillna(0)

    df["tempo_operacional_min"] = (
        df["tempo_planejado_min"] - df["parada_nao_planejada_min"]
    ).clip(lower=0.01)

    df["disponibilidade"] = (
        df["tempo_operacional_min"] / df["tempo_planejado_min"]
    ).clip(0, 1)

    tempo_producao_ideal_min = (
        df["qtd_produzida"] * df["tempo_ciclo_ideal_seg"] / 60
    )
    df["performance"] = (tempo_producao_ideal_min / df["tempo_operacional_min"]).clip(
        0, 1.5
    )  # tolera pequena folga acima de 1 por variação de medição

    df["qualidade"] = np.where(
        df["qtd_produzida"] > 0,
        (df["qtd_produzida"] - df["qtd_refugada"]) / df["qtd_produzida"],
        np.nan,
    ).clip(0, 1)

    df["oee"] = df["disponibilidade"] * df["performance"] * df["qualidade"]
    return df


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🏭 Acompanhamento de Manutenção e OEE")

modo_demo = not has_google_credentials()
if modo_demo:
    st.info(
        "Rodando em **modo demonstração** com dados sintéticos — configure as "
        "credenciais em `.streamlit/secrets.toml` (veja o README) para conectar "
        "às suas planilhas reais.",
        icon="ℹ️",
    )
    df_producao, df_paradas = load_demo_data()
else:
    try:
        df_producao, df_paradas = load_real_data()
    except Exception as e:
        st.error(f"Erro ao ler as planilhas do Google Sheets: {e}")
        st.stop()

if df_producao.empty:
    st.warning("Nenhum registro de produção encontrado ainda.")
    st.stop()

df = calcular_oee(df_producao, df_paradas)

# --- Filtros --------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    maquinas_sel = st.multiselect(
        "Máquina", sorted(df["maquina"].unique()), default=sorted(df["maquina"].unique())
    )
    turnos_sel = st.multiselect(
        "Turno", sorted(df["turno"].unique()), default=sorted(df["turno"].unique())
    )
    data_min, data_max = df["data"].min().date(), df["data"].max().date()
    periodo = st.date_input(
        "Período", value=(data_min, data_max), min_value=data_min, max_value=data_max
    )

if len(periodo) == 2:
    ini, fim = periodo
else:
    ini, fim = data_min, data_max

mask = (
    df["maquina"].isin(maquinas_sel)
    & df["turno"].isin(turnos_sel)
    & (df["data"].dt.date >= ini)
    & (df["data"].dt.date <= fim)
)
df_f = df[mask]
paradas_mask = (
    df_paradas["maquina"].isin(maquinas_sel)
    & df_paradas["turno"].isin(turnos_sel)
    & (df_paradas["data"].dt.date >= ini)
    & (df_paradas["data"].dt.date <= fim)
)
df_paradas_f = df_paradas[paradas_mask]

if df_f.empty:
    st.warning("Nenhum dado para os filtros selecionados.")
    st.stop()

# --- KPIs -------------------------------------------------------------------
oee_medio = df_f["oee"].mean()
disp_media = df_f["disponibilidade"].mean()
perf_media = df_f["performance"].mean()
qual_media = df_f["qualidade"].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("OEE Médio", f"{oee_medio * 100:.1f}%")
c2.metric("Disponibilidade", f"{disp_media * 100:.1f}%")
c3.metric("Performance", f"{perf_media * 100:.1f}%")
c4.metric("Qualidade", f"{qual_media * 100:.1f}%")

st.divider()

# --- OEE por máquina ---------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("OEE médio por máquina")
    por_maquina = (
        df_f.groupby("maquina")[["disponibilidade", "performance", "qualidade", "oee"]]
        .mean()
        .reset_index()
        .sort_values("oee", ascending=False)
    )
    fig = px.bar(
        por_maquina,
        x="maquina",
        y="oee",
        text=por_maquina["oee"].apply(lambda v: f"{v*100:.1f}%"),
        labels={"maquina": "Máquina", "oee": "OEE"},
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(yaxis_range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("Evolução do OEE ao longo do tempo")
    por_dia = df_f.groupby("data")["oee"].mean().reset_index()
    fig2 = px.line(por_dia, x="data", y="oee", markers=True, labels={"oee": "OEE"})
    fig2.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(fig2, use_container_width=True)

# --- Componentes do OEE por máquina -----------------------------------------
st.subheader("Disponibilidade x Performance x Qualidade por máquina")
componentes = por_maquina.melt(
    id_vars="maquina",
    value_vars=["disponibilidade", "performance", "qualidade"],
    var_name="componente",
    value_name="valor",
)
fig3 = px.bar(
    componentes, x="maquina", y="valor", color="componente", barmode="group"
)
fig3.update_yaxes(tickformat=".0%")
st.plotly_chart(fig3, use_container_width=True)

# --- Pareto de paradas --------------------------------------------------------
st.subheader("Pareto de motivos de parada (tempo total, minutos)")
if not df_paradas_f.empty:
    pareto = (
        df_paradas_f.groupby("motivo")["duracao_min"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    pareto["acumulado_%"] = 100 * pareto["duracao_min"].cumsum() / pareto["duracao_min"].sum()

    fig4 = px.bar(pareto, x="motivo", y="duracao_min", labels={"duracao_min": "Minutos"})
    fig4.add_scatter(
        x=pareto["motivo"],
        y=pareto["acumulado_%"] * pareto["duracao_min"].max() / 100,
        mode="lines+markers",
        name="% acumulado",
        yaxis="y2",
    )
    fig4.update_layout(
        yaxis2=dict(overlaying="y", side="right", title="% acumulado", range=[0, 105]),
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.caption("Sem paradas registradas no período filtrado.")

# --- Tabelas detalhadas -------------------------------------------------------
with st.expander("Ver dados detalhados de produção/OEE"):
    st.dataframe(
        df_f[
            [
                "data",
                "turno",
                "maquina",
                "tempo_planejado_min",
                "tempo_operacional_min",
                "parada_planejada_min",
                "parada_nao_planejada_min",
                "qtd_produzida",
                "qtd_refugada",
                "disponibilidade",
                "performance",
                "qualidade",
                "oee",
            ]
        ].sort_values("data", ascending=False),
        use_container_width=True,
    )

with st.expander("Ver registros de paradas"):
    st.dataframe(df_paradas_f.sort_values("data", ascending=False), use_container_width=True)
