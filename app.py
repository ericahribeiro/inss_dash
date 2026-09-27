import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Painel Previdenciário RS", page_icon="⚖️", layout="wide")

AZUL, LARANJA = "#2a78d6", "#eb6834"
CINZA, CINZA_TXT = "#c9c8c2", "#52514e"
FONTE = "Inter, 'Segoe UI', sans-serif"
MIN_CASOS = 30

FORMULARIO_URL = ""
AVALIACOES_CSV_URL = ""
try:
    FORMULARIO_URL = st.secrets.get("formulario_url", FORMULARIO_URL)
    AVALIACOES_CSV_URL = st.secrets.get("avaliacoes_csv_url", AVALIACOES_CSV_URL)
except Exception:
    pass

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
h1 {font-size: 1.9rem !important; margin-bottom: 0 !important;}
h3 {margin-top: 1.4rem !important;}
[data-testid="stMetricValue"] {font-size: 2.1rem;}
.subtitulo {color: #52514e; font-size: 1rem; margin-bottom: 1rem;}
.aviso-teste {background:#fff4e5; border-left:4px solid #eb6834; padding:.6rem 1rem;
              border-radius:4px; margin:.5rem 0 1rem; color:#0b0b0b;}
.rotulo {font-size:.8rem; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
         color:#52514e; margin:.2rem 0 .4rem;}
</style>
""", unsafe_allow_html=True)


def layout_base(fig, altura=320):
    fig.update_layout(
        height=altura, margin=dict(l=8, r=24, t=8, b=8),
        font=dict(family=FONTE, size=13, color=CINZA_TXT),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=13, font_family=FONTE),
        showlegend=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#e4e3de")
    fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
    return fig


BASE = Path(__file__).parent / "dados"
if not (BASE / "agregado.parquet").exists():
    st.error("Dados não encontrados. Rode primeiro: `python prepara_dados.py`")
    st.stop()


@st.cache_data
def carrega():
    df = pd.read_parquet(BASE / "agregado.parquet")
    meta = json.loads((BASE / "metadados.json").read_text(encoding="utf-8"))
    return df, meta


df, meta = carrega()
SEM_CID = {"Não informado", "Não disponível"}


def contagens(d):
    c = d.groupby("desfecho")["qtd"].sum()
    return (c.get("Concedido administrativo", 0), c.get("Concedido judicial", 0), c.get("Indeferido", 0))


def taxa_aprovacao(d):
    adm, _, ind = contagens(d)
    return (adm / (adm + ind) if adm + ind else None), adm + ind


def pct_judicial(d):
    adm, jud, _ = contagens(d)
    return (jud / (adm + jud) if adm + jud else None), adm + jud


def mediana_meses(d):
    d = d.dropna(subset=["meses_ate_decisao"])
    if d.qtd.sum() == 0:
        return None
    g = d.groupby("meses_ate_decisao")["qtd"].sum().sort_index()
    return float(g.index[np.searchsorted(g.cumsum().values, g.sum() / 2)])


def pct(v):
    return "–" if v is None else f"{v*100:.0f}%"


def num(v):
    return f"{v:,.0f}".replace(",", ".")


def meses_txt(v):
    if v is None:
        return "–"
    return "menos de 1 mês" if v < 1 else ("36+ meses" if v >= 36 else f"{v:.0f} {'mês' if v == 1 else 'meses'}")


t1, t2 = st.columns([5, 1], vertical_alignment="bottom")
t1.title(f"Painel de Referência Previdenciária – {meta['uf_nome']}")
if FORMULARIO_URL:
    t2.link_button("Avaliar este painel", FORMULARIO_URL, width="stretch")
ini = pd.Timestamp(meta["periodo_inicio"]).strftime("%m/%Y")
fim = pd.Timestamp(meta["periodo_fim"]).strftime("%m/%Y")
st.markdown(
    f"<div class='subtitulo'>Como o INSS decidiu pedidos parecidos com o do seu cliente · "
    f"dados abertos do INSS, {ini} a {fim}</div>", unsafe_allow_html=True)
if meta.get("sintetico"):
    st.markdown("<div class='aviso-teste'><b>DADOS DE TESTE.</b> Números sintéticos, só para "
                "testar o painel. Não use para análise.</div>", unsafe_allow_html=True)

st.markdown("### 1. Perfil do cliente")
f1, f2, f3, f4 = st.columns([1.6, 1, 1, 1])
especies = sorted(df.grupo_especie.unique())
padrao = next((i for i, e in enumerate(especies) if e.startswith("Auxílio")), 0)
especie = f1.selectbox("Benefício", especies, index=padrao)
d_esp = df[df.grupo_especie == especie]
faixas = [f for f in ["0–17", "18–29", "30–39", "40–49", "50–59", "60–64", "65+"]
          if f in set(d_esp.faixa_etaria)]
faixa_sel = f2.selectbox("Faixa etária", ["Todas"] + faixas)
sexo_sel = f3.selectbox("Sexo", ["Todos"] + sorted(s for s in d_esp.sexo.unique() if s != "Não informado"))
cli_sel = f4.selectbox("Clientela", ["Todas"] + sorted(d_esp.clientela.unique()))
meses = sorted(df.mes.unique())
per = st.select_slider("Período", options=meses, value=(meses[0], meses[-1]),
                       format_func=lambda m: pd.Timestamp(m).strftime("%m/%Y"))

ref = d_esp[(d_esp.mes >= per[0]) & (d_esp.mes <= per[1])]
sem_idade = ref
if sexo_sel != "Todos":
    sem_idade = sem_idade[sem_idade.sexo == sexo_sel]
if cli_sel != "Todas":
    sem_idade = sem_idade[sem_idade.clientela == cli_sel]
perfil = sem_idade if faixa_sel == "Todas" else sem_idade[sem_idade.faixa_etaria == faixa_sel]
filtrou_perfil = perfil is not ref

st.markdown("### 2. O que aconteceu com casos parecidos")


def delta_pp(a, b, ativo):
    if a is None or b is None or not ativo:
        return None
    return f"{(a-b)*100:+.0f} p.p. vs. média do benefício"


tx, n_dec = taxa_aprovacao(perfil)
tx_ref, _ = taxa_aprovacao(ref)
pj, n_conc = pct_judicial(perfil)
pj_ref, _ = pct_judicial(ref)
t_adm = mediana_meses(perfil[perfil.desfecho == "Concedido administrativo"])
t_jud = mediana_meses(perfil[perfil.desfecho == "Concedido judicial"])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Pedidos decididos pelo INSS", num(n_dec),
          help="Concessões administrativas + indeferimentos do perfil no período.")
k2.metric("Aprovados direto no INSS", pct(tx), delta_pp(tx, tx_ref, filtrou_perfil),
          help="Concessões administrativas ÷ (concessões administrativas + indeferimentos).")
k3.metric("Concessões que vieram da Justiça", pct(pj),
          delta_pp(pj, pj_ref, filtrou_perfil), delta_color="off",
          help="Concessões com despacho 'Concessão decorrente de ação judicial' ÷ total de concessões.")
k4.metric("Tempo típico até concessão judicial", meses_txt(t_jud),
          None if t_adm is None else f"administrativa: {meses_txt(t_adm)}", delta_color="off",
          help="Mediana do tempo entre o início do benefício (DIB) e o despacho (DDB). "
               "Na via judicial, mostra quanto tempo o cliente costuma esperar.")
if n_dec < MIN_CASOS:
    st.warning("Amostra pequena para esse perfil (menos de 30 pedidos). Os percentuais podem "
               "variar muito — tente ampliar a faixa etária ou o período.")
if especie.startswith("Aposentadoria"):
    st.info("**Atenção ao ler a aprovação deste benefício.** A aposentadoria por incapacidade "
            "permanente quase nunca é pedida diretamente: em geral ela nasce da conversão de um "
            "auxílio por incapacidade temporária após a perícia. Por isso há poucos indeferimentos "
            "registrados nesta espécie (as negativas ficam no auxílio), e a taxa de aprovação sai "
            "artificialmente alta. Para avaliar a chance de negativa na via administrativa, consulte "
            "o **auxílio por incapacidade temporária**. O percentual via Justiça e o tempo até a "
            "concessão continuam válidos.")

esq, dir_ = st.columns([1.2, 1])
with esq:
    st.markdown("### 3. Por que o INSS nega esse perfil")
    mot = (perfil[perfil.desfecho == "Indeferido"].groupby("motivo")["qtd"].sum()
           .sort_values(ascending=False))
    nao_class = mot.pop("Não classificado pelo INSS") if "Não classificado pelo INSS" in mot else 0
    if mot.empty:
        st.info("Sem indeferimentos com motivo informado para esse perfil.")
    else:
        top = mot.head(6).copy()
        if len(mot) > 6:
            top["Outros motivos"] = mot.iloc[6:].sum()
        share = (top / mot.sum()).iloc[::-1]
        rotulos = [m if len(m) < 50 else m[:47] + "…" for m in share.index]
        fig = go.Figure(go.Bar(
            x=share.values, y=rotulos, orientation="h", marker=dict(color=AZUL, cornerradius=4),
            text=[pct(v) for v in share.values], textposition="outside",
            customdata=np.stack([top.iloc[::-1].values, share.index], axis=1),
            hovertemplate="<b>%{customdata[1]}</b><br>%{text} das negativas "
                          "(%{customdata[0]:,} pedidos)<extra></extra>",
        ))
        fig.update_xaxes(visible=False, range=[0, share.max() * 1.3])
        st.plotly_chart(layout_base(fig, 60 + 44 * len(share)), width="stretch")
        extra = (f" {pct(nao_class / (mot.sum() + nao_class))} das negativas vêm sem motivo "
                 "classificado e ficaram de fora." if nao_class else "")
        st.caption("Percentual entre as negativas com motivo informado." + extra)

with dir_:
    st.markdown("### 4. A idade muda o resultado?")
    linhas = [(fx, *taxa_aprovacao(sem_idade[sem_idade.faixa_etaria == fx])) for fx in faixas]
    pf = pd.DataFrame(linhas, columns=["faixa", "taxa", "n"]).dropna()
    pf = pf[pf.n >= MIN_CASOS]
    if pf.empty:
        st.info("Poucos casos para comparar por idade.")
    else:
        cores = [AZUL if faixa_sel in ("Todas", f) else CINZA for f in pf.faixa]
        fig = go.Figure(go.Bar(
            x=pf.faixa, y=pf.taxa, marker=dict(color=cores, cornerradius=4),
            text=[pct(v) for v in pf.taxa], textposition="outside", customdata=pf.n,
            hovertemplate="<b>%{x} anos</b><br>Aprovados direto: %{text}"
                          "<br>%{customdata:,} pedidos<extra></extra>",
        ))
        fig.update_yaxes(tickformat=".0%", range=[0, min(1.12, pf.taxa.max() * 1.25)], tickvals=[0, .2, .4, .6, .8, 1])
        st.plotly_chart(layout_base(fig, 330), width="stretch")
        st.caption("Aprovação direta no INSS por faixa etária (mesmo benefício, sexo e clientela)."
                   + ("" if faixa_sel == "Todas" else f" Em destaque: {faixa_sel} anos."))

st.markdown("### 5. Como isso vem mudando mês a mês")
ts = pd.DataFrame({
    "taxa": perfil.groupby("mes").apply(lambda g: taxa_aprovacao(g)[0]),
    "jud": perfil.groupby("mes").apply(lambda g: pct_judicial(g)[0]),
})
ts.index.name = "mes"
ts = ts.reset_index().sort_values("mes")
if len(ts) < 2:
    st.info("Período curto demais para mostrar tendência.")
else:
    nome_jud = "Concessões vindas da Justiça"
    fig = go.Figure()
    for col, nome, cor in [("taxa", "Aprovados direto no INSS", AZUL), ("jud", nome_jud, LARANJA)]:
        s = ts.dropna(subset=[col])
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s.mes, y=s[col], name=nome, mode="lines+markers",
            line=dict(color=cor, width=2), marker=dict(size=8, line=dict(color="white", width=2)),
            hovertemplate=f"{nome}: %{{y:.0%}}<extra></extra>"))
        fig.add_annotation(x=s.mes.iloc[-1], y=s[col].iloc[-1], text=f"<b>{nome}</b>",
                           showarrow=False, xanchor="left", xshift=10,
                           font=dict(color=CINZA_TXT, size=12))
    fig = layout_base(fig, 340)
    fig.update_layout(hovermode="x unified", showlegend=True,
                      legend=dict(orientation="h", y=1.12, x=0), margin=dict(r=240))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig.update_xaxes(tickformat="%m/%Y", dtick="M1",
                     range=[ts.mes.min() - pd.Timedelta(days=12), ts.mes.max() + pd.Timedelta(days=12)])
    st.plotly_chart(fig, width="stretch")
    st.caption("As duas linhas usam o perfil escolhido acima. Passe o mouse para ver os valores.")

st.markdown(f"### 6. Consultar uma doença (CID) – {especie}")
st.caption("O INSS só informa o CID nas concessões administrativas (não nos pedidos negados "
           "nem nas concessões judiciais). Por isso esta parte mostra **o que o INSS costuma "
           "conceder** para cada doença, e não uma taxa de aprovação por doença.")
adm = perfil[(perfil.desfecho == "Concedido administrativo") & ~perfil.cid.isin(SEM_CID)]
tot_adm = adm.qtd.sum()
tab = (adm.groupby(["cid", "cid_descricao", "cid_capitulo"])["qtd"].sum()
       .reset_index().sort_values("qtd", ascending=False).reset_index(drop=True))
tab["posicao"] = tab.index + 1
tem_duracao = adm.duracao_meses.notna().any()

if tab.empty:
    st.info("Sem concessões com CID para esse perfil.")
else:
    opcoes = [f"{r.cid} – {r.cid_descricao}" for r in tab.itertuples()]
    cid_sel = st.selectbox("Doença (CID) — digite para buscar", opcoes)
    cod = cid_sel.split(" – ")[0]
    linha = tab[tab.cid == cod].iloc[0]
    d_cid = adm[adm.cid == cod]
    faixa_top = d_cid.groupby("faixa_etaria")["qtd"].sum().idxmax()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Concessões administrativas", num(linha.qtd))
    c2.metric("Posição entre as doenças", f"{linha.posicao}º de {len(tab)}",
              help="Ranking pelo número de concessões administrativas no perfil e período.")
    c3.metric("Faixa etária mais comum", f"{faixa_top} anos")
    if tem_duracao:
        dur = mediana_meses(d_cid.drop(columns="meses_ate_decisao")
                            .rename(columns={"duracao_meses": "meses_ate_decisao"}))
        dur_ref = mediana_meses(adm.drop(columns="meses_ate_decisao")
                                .rename(columns={"duracao_meses": "meses_ate_decisao"}))
        c4.metric("Duração típica concedida", meses_txt(dur),
                  None if dur_ref is None else f"média do benefício: {meses_txt(dur_ref)}",
                  delta_color="off",
                  help="Mediana entre o início (DIB) e a data de cessação (DCB) do benefício concedido.")

    st.markdown("<div class='rotulo'>Doenças com mais concessões administrativas</div>",
                unsafe_allow_html=True)
    rank = tab[tab.qtd >= MIN_CASOS].copy()
    rank["Participação"] = 100 * rank.qtd / tot_adm
    if tem_duracao:
        h = (adm[adm.cid.isin(rank.cid) & adm.duracao_meses.notna()]
             .groupby(["cid", "duracao_meses"])["qtd"].sum().reset_index()
             .sort_values(["cid", "duracao_meses"]))
        h["acum"] = h.groupby("cid")["qtd"].cumsum()
        h["meio"] = h.groupby("cid")["qtd"].transform("sum") / 2
        dur_cid = h[h.acum >= h.meio].groupby("cid")["duracao_meses"].first()
        rank["Duração típica (meses)"] = rank.cid.map(dur_cid).astype(float)
    rank = rank.rename(columns={"cid": "CID", "cid_descricao": "Doença", "cid_capitulo": "Capítulo",
                                "qtd": "Concessões", "posicao": "Posição"})
    cols = ["Posição", "CID", "Doença", "Capítulo", "Concessões", "Participação"] + \
           (["Duração típica (meses)"] if tem_duracao else [])
    st.dataframe(rank[cols], hide_index=True, width="stretch", height=380, column_config={
        "Concessões": st.column_config.NumberColumn(format="%d"),
        "Participação": st.column_config.ProgressColumn(
            format="%.1f%%", min_value=0, max_value=float(rank["Participação"].max() or 1)),
        "Duração típica (meses)": st.column_config.NumberColumn(format="%.0f"),
    })
    st.caption(f"Só doenças com pelo menos {MIN_CASOS} concessões. Participação = % das "
               "concessões administrativas do perfil.")

st.markdown("### 7. O que você achou?")
if FORMULARIO_URL:
    a1, a2 = st.columns([3, 1], vertical_alignment="center")
    a1.markdown("Este painel faz parte de um projeto de extensão da PUC Goiás. Sua opinião "
                "ajuda a melhorar a ferramenta e leva 2 minutos.")
    a2.link_button("Avaliar este painel", FORMULARIO_URL, type="primary", width="stretch")
else:
    st.caption("Formulário de avaliação ainda não configurado (defina FORMULARIO_URL em app.py).")


def _sem_acento(t):
    import unicodedata
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()


@st.cache_data(ttl=600)
def carrega_avaliacoes(url):
    return pd.read_csv(url, dtype=str)


def acha_coluna(cols, *chaves):
    return next((c for c in cols if any(k in _sem_acento(c) for k in chaves)), None)


if AVALIACOES_CSV_URL:
    try:
        av = carrega_avaliacoes(AVALIACOES_CSV_URL)
    except Exception:
        av = None
        st.caption("Não foi possível carregar as avaliações agora.")
    if av is not None and not av.empty:
        c_autoriza = acha_coluna(av.columns, "autoriza", "exibir", "publicar")
        outras = [c for c in av.columns if c != c_autoriza]   # a pergunta de autorização cita "nome"
        c_nome = acha_coluna(outras, "nome")
        c_idade = acha_coluna(outras, "idade")
        c_funcao = acha_coluna(outras, "funcao", "cargo", "atuacao")
        c_facil = acha_coluna(outras, "facil")
        c_util = acha_coluna(outras, "uteis", "utilidade")
        c_coment = acha_coluna(outras, "comentario", "depoimento", "sugestao", "melhorar")

        def media(col):
            v = pd.to_numeric(av[col], errors="coerce") if col else pd.Series(dtype=float)
            return None if v.dropna().empty else v.mean()

        m1, m2, m3 = st.columns(3)
        m1.metric("Avaliações recebidas", num(len(av)))
        mf, mu = media(c_facil), media(c_util)
        m2.metric("Facilidade de uso", "–" if mf is None else f"{mf:.1f} de 5".replace(".", ","))
        m3.metric("Utilidade para o escritório", "–" if mu is None else f"{mu:.1f} de 5".replace(".", ","))

        if c_autoriza and c_coment:
            pub = av[av[c_autoriza].map(_sem_acento).str.startswith("sim")
                     & av[c_coment].fillna("").str.strip().ne("")]
            if not pub.empty:
                st.markdown("<div class='rotulo'>O que dizem os usuários</div>", unsafe_allow_html=True)
                cols_dep = st.columns(2)
                for i, r in enumerate(pub.iloc[::-1].itertuples(index=False)):  # mais recentes primeiro
                    r = dict(zip(pub.columns, r))
                    partes = [str(r[c]).strip() for c in (c_nome,) if c and pd.notna(r[c])]
                    if c_idade and pd.notna(r[c_idade]) and str(r[c_idade]).strip():
                        partes.append(f"{str(r[c_idade]).strip()} anos")
                    autor = ", ".join(partes)
                    if c_funcao and pd.notna(r[c_funcao]):
                        autor += f" – {str(r[c_funcao]).strip()}"
                    with cols_dep[i % 2].container(border=True):
                        st.markdown(f"“{str(r[c_coment]).strip()}”")
                        st.caption(autor or "Usuário do painel")

with st.expander("Como ler estes números (limitações importantes)"):
    st.markdown(f"""
- **Não é a chance de ganhar a ação.** As bases públicas do INSS mostram concessões e
  indeferimentos, mas não mostram processos judiciais perdidos. Os indicadores descrevem o
  histórico de casos parecidos; não preveem o resultado de um caso.
- **CID só nas concessões administrativas.** A planilha de indeferidos não traz o CID, e as
  concessões judiciais quase nunca trazem (menos de 2% no período). Por isso aprovação,
  negativa e via judicial são por perfil (benefício, idade, sexo, clientela), e a consulta
  por doença mostra só o que o INSS concede administrativamente.
- **Concessão judicial** = despacho "Concessão decorrente de ação judicial". Ela costuma se
  referir a um pedido feito meses antes (veja o tempo típico).
- **Tempo até a concessão** = mediana entre a data de início do benefício (DIB) e a data do
  despacho (DDB), em meses, limitada a 36. **Duração concedida** = mediana entre DIB e a data de
  cessação (DCB), limitada a 24 meses; só existe para benefícios com data de término.
- **Motivo "não classificado"**: parte das negativas vem sem motivo no arquivo do INSS.
- **Recorte**: {meta['uf_nome']}, {ini} a {fim}, {num(meta['registros'])} registros. Benefícios:
  auxílio por incapacidade temporária (espécies 31 e 91), aposentadoria por incapacidade
  permanente (32 e 92) e BPC/LOAS à pessoa com deficiência (87).
- **Privacidade (LGPD)**: só dados públicos agregados. Nenhum dado do cliente é digitado,
  salvo ou enviado.
- **Fonte**: dados.gov.br — "Benefícios concedidos" e "Benefícios indeferidos" (INSS).
""")
