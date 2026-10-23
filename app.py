"""Painel da Carteira de Pedidos (Streamlit).  Execute: streamlit run app.py"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
import carteira as cw

st.set_page_config(page_title="Painel da Carteira de Pedidos", layout="wide")
COR_REG = {"Região 1": "#2a78d6", "Região 2": "#eb6834", "Região 3": "#1baf7a"}
AZUL = "#2a78d6"
REF = pd.Timestamp("2026-10-22")
PADRAO = Path(__file__).parent / "geral_itens.xlsx"


@st.cache_data(show_spinner="Lendo a planilha…")
def ler(origem):
    # origem: bytes do arquivo enviado ou caminho do arquivo padrão
    import io
    return cw.carregar(io.BytesIO(origem) if isinstance(origem, bytes) else origem)


st.title("Painel da Carteira de Pedidos")
st.caption("Valor = VLRLIQ (líquido de desconto), da aba BASE. Pedidos = NRO_UNICO distintos.")

with st.sidebar:
    st.header("Dados")
    up = st.file_uploader("Planilha (.xlsx com a aba BASE)", type=["xlsx"])
    if up is None and not PADRAO.exists():
        st.info("Envie a planilha geral_itens.xlsx para começar.")
        st.stop()
    try:
        base = ler(up.getvalue() if up is not None else str(PADRAO))
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler a planilha: {e}")
        st.stop()
    st.caption("Usando o arquivo enviado." if up is not None else "Usando geral_itens.xlsx (arquivo padrão).")

    st.header("Filtros")
    regioes = st.multiselect("Região", sorted(base["REGIAO"].unique()))
    grupos = st.multiselect("Grupo de produtos", list(base.groupby("GRUPO")["VLRLIQ"].sum().sort_values(ascending=False).index))
    cliente = st.text_input("Cliente (contém)")
    dmin, dmax = base["DTAGEND"].min().date(), base["DTAGEND"].max().date()
    periodo = st.date_input("Agenda (DTAGEND)", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    ocultar = st.checkbox("Ocultar itens com valor zero (provável bonificação)")

d0, d1 = (periodo if isinstance(periodo, tuple) and len(periodo) == 2 else (dmin, dmax))
df = cw.filtrar(base, regioes, grupos, cliente, d0, d1, ocultar)
tot_geral = cw.totais(base)
if df.empty:
    st.warning("Nenhum item corresponde aos filtros atuais.")
    st.stop()
t = cw.totais(df)

st.info("Antes de usar os números: a aba RESUMO da planilha original soma R$ 880.629, abaixo da BASE (R$ 946.466,96). "
        "A planilha tem número e data de nota em todas as linhas e não tem campo de situação; "
        "confirme se é carteira em aberto ou faturado. Sem regra de prazo, nenhum pedido é classificado como atrasado.")

c = st.columns(6)
c[0].metric("Valor líquido", cw.brl(t["valor"]), cw.pct(t["valor"] / tot_geral["valor"]) + " da carteira", delta_color="off")
c[1].metric("Unidades", cw.inteiro(t["unidades"]), cw.pct(t["unidades"] / tot_geral["unidades"]) + " da carteira", delta_color="off")
c[2].metric("Pedidos", cw.inteiro(t["pedidos"]))
c[3].metric("Clientes", cw.inteiro(t["clientes"]))
c[4].metric("Ticket médio", cw.brl(t["ticket"]))
c[5].metric("Valor por unidade", cw.brl(t["valor_un"]), "Desconto de " + cw.pct(t["desconto"]), delta_color="off")


def barras(dados, y, x, titulo, cor=None, mapa=None, fmt="valor"):
    d = dados.copy()
    d["rotulo"] = d[x].map(lambda v: cw.brl(v, 0) if fmt == "valor" else cw.inteiro(v))
    fig = px.bar(d, x=x, y=y, orientation="h", text="rotulo", color=cor, color_discrete_map=mapa,
                 color_discrete_sequence=[AZUL], title=titulo)
    fig.update_layout(yaxis=dict(autorange="reversed", title=None), xaxis=dict(title=None, showticklabels=False),
                      showlegend=False, margin=dict(l=0, r=0, t=40, b=0), height=max(260, 42 * len(d) + 70))
    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


metrica = st.radio("Métrica dos gráficos", ["Valor líquido", "Unidades"], horizontal=True)
col, fmt = ("valor", "valor") if metrica == "Valor líquido" else ("unidades", "un")

a, b = st.columns(2)
with a:
    st.plotly_chart(barras(cw.agrupar(df, "GRUPO").sort_values(col, ascending=False), "GRUPO", col, f"{metrica} por grupo", fmt=fmt), use_container_width=True)
with b:
    st.plotly_chart(barras(cw.agrupar(df, "REGIAO").sort_values(col, ascending=False), "REGIAO", col, f"{metrica} por região", cor="REGIAO", mapa=COR_REG, fmt=fmt), use_container_width=True)

a, b = st.columns([3, 2])
with a:
    st.subheader("Matriz grupo × região")
    mx = cw.matriz(df, "VLRLIQ" if col == "valor" else "QTDNEG")
    mx = mx.loc[[g for g in cw.agrupar(df, "GRUPO")["GRUPO"] if g in mx.index]]
    fig = px.imshow(mx, text_auto=",.0f", aspect="auto", color_continuous_scale="Blues")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
with b:
    st.subheader("10 maiores clientes")
    tc = cw.top_clientes(df)
    st.plotly_chart(barras(tc, "CLIENTE", "valor", "", cor="regiao", mapa=COR_REG), use_container_width=True)

st.subheader("Valor líquido por data de agenda")
ag = cw.agenda(df)
ag["Período"] = ag["DTAGEND"].map(lambda d: "22/10 em diante" if d >= REF else "Antes de 22/10")
ag["Data"] = ag["DTAGEND"].dt.strftime("%d/%m")
fig = px.bar(ag, x="Data", y="valor", color="Período", color_discrete_map={"Antes de 22/10": "#2a78d6", "22/10 em diante": "#eb6834"},
             hover_data={"pedidos": True, "unidades": True})
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title="R$", legend_title=None)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Pedidos")
p = cw.pedidos(df)
st.dataframe(p, use_container_width=True, hide_index=True, column_config={
    "NRO_UNICO": "Pedido", "CLIENTE": "Cliente", "REGIAO": "Região",
    "EMISSAO": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"),
    "AGENDA": st.column_config.DateColumn("Agenda", format="DD/MM/YYYY"),
    "ITENS": "Itens", "UNIDADES": "Unid.",
    "VALOR": st.column_config.NumberColumn("Valor líquido", format="R$ %.2f")})
st.download_button("Baixar itens filtrados (CSV)", df.drop(columns=["SEM_VALOR"]).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                   file_name="carteira_filtrada.csv", mime="text/csv")
st.caption(f"Base: {cw.brl(tot_geral['valor'])} e {cw.inteiro(tot_geral['unidades'])} unidades no total da planilha. "
           "Dados de carteira de pedidos, sem distinção entre faturamento realizado e receita reconhecida.")
