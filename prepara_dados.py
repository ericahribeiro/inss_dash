from __future__ import annotations

import argparse
import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd



def normaliza(txt) -> str:
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", txt.lower())).strip()


COLUNAS = {
    "competencia": "competencia",
    "especie": "especie",
    "cid": "cid",
    "despacho": "despacho",
    "motivo": "motivo indeferimento",
    "nascimento": "dt nascimento",
    "sexo": "sexo",
    "clientela": "clientela",
    "uf": "uf",
    "dt_dib": "dt dib",
    "dt_ddb": "dt ddb",
    "dt_dcb": "dt dcb",
    "dt_der": "dt der",
    "dt_indef": "dt indeferimento",
}

ESPECIES = {
    "31": "Auxílio por incapacidade temporária",       # previdenciário
    "91": "Auxílio por incapacidade temporária",       # acidentário
    "32": "Aposentadoria por incapacidade permanente", # previdenciária
    "92": "Aposentadoria por incapacidade permanente", # acidentária
    "87": "BPC/LOAS – pessoa com deficiência",
}
ESPECIES_TEXTO = [
    ("Auxílio por incapacidade temporária", r"auxilio (por )?(doenca|incapacidade temporaria)"),
    ("Aposentadoria por incapacidade permanente", r"aposentadoria (por )?(invalidez|incapacidade permanente)"),
    ("BPC/LOAS – pessoa com deficiência", r"(amp|amparo|bpc|beneficio de prestacao continuada).*deficien"),
]

CAPITULOS_CID = [
    ("A00", "B99", "I – Infecciosas e parasitárias"),
    ("C00", "D48", "II – Neoplasias (tumores)"),
    ("D50", "D89", "III – Sangue e imunidade"),
    ("E00", "E90", "IV – Endócrinas e metabólicas"),
    ("F00", "F99", "V – Transtornos mentais"),
    ("G00", "G99", "VI – Sistema nervoso"),
    ("H00", "H59", "VII – Olho"),
    ("H60", "H95", "VIII – Ouvido"),
    ("I00", "I99", "IX – Circulatório"),
    ("J00", "J99", "X – Respiratório"),
    ("K00", "K93", "XI – Digestivo"),
    ("L00", "L99", "XII – Pele"),
    ("M00", "M99", "XIII – Osteomuscular (coluna, articulações)"),
    ("N00", "N99", "XIV – Geniturinário"),
    ("O00", "O99", "XV – Gravidez e parto"),
    ("P00", "P96", "XVI – Perinatais"),
    ("Q00", "Q99", "XVII – Malformações congênitas"),
    ("R00", "R99", "XVIII – Sintomas e achados anormais"),
    ("S00", "T98", "XIX – Lesões e fraturas"),
    ("V01", "Y98", "XX – Causas externas"),
    ("Z00", "Z99", "XXI – Fatores de saúde"),
]
RE_CID = re.compile(r"^\s*([A-Z])\s*(\d{2})\.?(\d)?\s*[-–:]?\s*(.*)$")
SEM_CID = ("Não informado", "Não informado", "Não informado")

FAIXAS = [(0, 17, "0–17"), (18, 29, "18–29"), (30, 39, "30–39"), (40, 49, "40–49"),
          (50, 59, "50–59"), (60, 64, "60–64"), (65, 200, "65+")]


def parse_cid(valor) -> tuple[str, str, str]:
    if pd.isna(valor):
        return SEM_CID
    m = RE_CID.match(str(valor).upper())
    if not m:
        return SEM_CID
    cod3 = f"{m.group(1)}{m.group(2)}"
    cod = f"{cod3}.{m.group(3)}" if m.group(3) else cod3
    desc = re.sub(r"\s+", " ", str(valor).strip()[m.start(4):]).strip(" .-–:")
    cap = next((c for ini, fim, c in CAPITULOS_CID if ini <= cod3 <= fim), "Outros")
    return cod, (desc.capitalize() if desc else cod), cap


def para_data(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip()
    d = pd.to_datetime(s.str[:10], format="%Y-%m-%d", errors="coerce")
    return d.fillna(pd.to_datetime(s, format="%d/%m/%Y", errors="coerce"))


def mes_competencia(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.replace(r"\D", "", regex=True).str[:6]
    return pd.to_datetime(s, format="%Y%m", errors="coerce")


def faixa_etaria(idade) -> str:
    if pd.isna(idade) or idade < 0 or idade > 120:
        return "Não informada"
    idade = int(idade)
    return next(r for a, b, r in FAIXAS if a <= idade <= b)


def cabecalho_real(t: pd.DataFrame) -> pd.DataFrame:
    nomes = list(t.columns)
    if not any("especie" in normaliza(c) for c in nomes):
        for i in range(min(15, len(t))):
            linha = t.iloc[i].tolist()
            if any(normaliza(v) == "especie" for v in linha):
                nomes = [str(v) for v in linha]
                t = t.iloc[i + 1:]
                break
    vistos, finais = set(), []
    for n in nomes:
        n = re.sub(r"\.\d+$", "", str(n))
        base = normaliza(n)
        finais.append(f"{n}__desc" if base in vistos else n)
        vistos.add(base)
    t = t.copy()
    t.columns = finais
    return t


def le_tabelas(caminho: Path):
    def _csv(buf: bytes):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                amostra = buf[:5000].decode(enc)
                sep = ";" if amostra.count(";") >= amostra.count(",") else ","
                return pd.read_csv(io.BytesIO(buf), sep=sep, encoding=enc, dtype=str,
                                   on_bad_lines="skip", low_memory=False)
            except UnicodeDecodeError:
                continue

    suf = caminho.suffix.lower()
    if suf == ".zip":
        with zipfile.ZipFile(caminho) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(".csv"):
                    yield f"{caminho.name}/{info.filename}", cabecalho_real(_csv(z.read(info)))
    elif suf == ".csv":
        yield caminho.name, cabecalho_real(_csv(caminho.read_bytes()))
    elif suf in (".xlsx", ".xls"):
        try:
            abas = pd.read_excel(caminho, sheet_name=None, dtype=str, engine="calamine")
        except ImportError:
            abas = pd.read_excel(caminho, sheet_name=None, dtype=str)
        for aba, tabela in abas.items():
            yield f"{caminho.name}/{aba}", cabecalho_real(tabela)


def mapeia_colunas(cols: list[str]) -> dict[str, str]:
    mapa = {}
    for canon, prefixo in COLUNAS.items():
        candidatas = [c for c in cols if normaliza(c.replace("__desc", "")).startswith(prefixo)]
        if not candidatas:
            continue
        desc = [c for c in candidatas if c.endswith("__desc")]
        cod = [c for c in candidatas if not c.endswith("__desc")]
        if canon == "especie" and cod:
            mapa[cod[0]] = "especie_cod"
        escolha = (desc or cod)[0]
        mapa[escolha] = canon
    return mapa


SAIDA = ["mes", "grupo_especie", "cid", "cid_descricao", "cid_capitulo", "faixa_etaria",
         "sexo", "clientela", "desfecho", "motivo", "meses_ate_decisao", "duracao_meses"]

def processa(bruto: pd.DataFrame, uf_nome: str) -> pd.DataFrame | None:
    df = bruto.rename(columns=mapeia_colunas(list(bruto.columns)))
    if "despacho" in df:
        tipo = "concedido"
    elif "motivo" in df:
        tipo = "indeferido"
    else:
        return None

    df = df[df["uf"].map(normaliza) == normaliza(uf_nome)]
    cod = df.get("especie_cod", pd.Series(index=df.index, dtype=str)).astype(str).str.strip()
    grupo = cod.map(ESPECIES)
    if "especie" in df:
        por_texto = df["especie"].map(
            lambda v: next((g for g, p in ESPECIES_TEXTO if re.search(p, normaliza(v))), None))
        grupo = grupo.fillna(por_texto)
    df = df.assign(grupo_especie=grupo)
    df = df[df.grupo_especie.notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=SAIDA)

    df["mes"] = mes_competencia(df["competencia"])
    idade = (df["mes"] - para_data(df["nascimento"])).dt.days / 365.25
    df["faixa_etaria"] = idade.map(faixa_etaria)
    df["sexo"] = df["sexo"].fillna("Não informado").str.strip().replace({"Nao Informado": "Não informado"})
    df["clientela"] = df["clientela"].fillna("Não informada").str.strip()

    if tipo == "concedido":
        cid = df["cid"].map(parse_cid)
        df["cid"], df["cid_descricao"], df["cid_capitulo"] = cid.str[0], cid.str[1], cid.str[2]
        judicial = df["despacho"].map(lambda v: "judic" in normaliza(v))
        df["desfecho"] = judicial.map({True: "Concedido judicial", False: "Concedido administrativo"})
        df["motivo"] = None
        inicio, fim = para_data(df["dt_dib"]), para_data(df["dt_ddb"])
        dcb = para_data(df.get("dt_dcb", pd.Series(index=df.index, dtype=str)))
        dur = ((dcb - inicio).dt.days / 30.44).round()
        df["duracao_meses"] = dur.where((dur >= 0) & (dur < 600)).clip(upper=24)
    else:
        df["cid"], df["cid_descricao"], df["cid_capitulo"] = "Não disponível", "Não disponível", "Não disponível"
        df["desfecho"] = "Indeferido"
        df["duracao_meses"] = float("nan")
        m = df["motivo"].fillna("").str.strip()
        m = m.str.replace(r"\bNao\b", "Não", regex=True).str.rstrip(".")
        df["motivo"] = m.where(~m.isin(["", "{ñ class}"]), "Não classificado pelo INSS")
        inicio, fim = para_data(df.get("dt_der", pd.Series(index=df.index))), para_data(df["dt_indef"])

    meses = ((fim - inicio).dt.days / 30.44).round()
    df["meses_ate_decisao"] = meses.where((meses >= 0) & (meses < 600)).clip(upper=36)

    return df[SAIDA]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="dados_brutos")
    ap.add_argument("--saida", default="dados")
    ap.add_argument("--uf", default="RS")
    ap.add_argument("--uf-nome", default="Rio Grande do Sul")
    ap.add_argument("--sintetico", action="store_true", help="marca a saída como dados de TESTE")
    a = ap.parse_args()

    partes, log = [], []
    arquivos = [p for p in sorted(Path(a.entrada).expanduser().glob("*"))
                if p.suffix.lower() in (".xlsx", ".xls", ".csv", ".zip")]
    for arq in arquivos:
        try:
            for nome, bruto in le_tabelas(arq):
                res = processa(bruto, a.uf_nome)
                if res is None:
                    log.append(f"IGNORADO (não parece arquivo do INSS): {nome}")
                    continue
                log.append(f"{nome}: {len(bruto):,} linhas -> {len(res):,} no recorte")
                print(log[-1], flush=True)
                partes.append(res)
        except Exception as e:
            log.append(f"ERRO em {arq.name}: {e}")
            print(log[-1], flush=True)
    if not partes:
        raise SystemExit("Nenhum dado no recorte. Verifique a pasta de entrada.")

    base = pd.concat(partes, ignore_index=True)
    desc = (base[~base.cid.isin(["Não informado", "Não disponível"])]
            .groupby("cid")["cid_descricao"].agg(lambda s: s.value_counts().index[0]))
    base["cid_descricao"] = base["cid"].map(desc).fillna(base["cid_descricao"])

    chaves = ["mes", "grupo_especie", "cid", "cid_descricao", "cid_capitulo", "faixa_etaria",
              "sexo", "clientela", "desfecho", "motivo", "meses_ate_decisao", "duracao_meses"]
    agg = (base.fillna({"motivo": "-", "meses_ate_decisao": -1, "duracao_meses": -1}).groupby(chaves)
           .size().rename("qtd").reset_index())
    agg.loc[agg.motivo == "-", "motivo"] = None
    agg.loc[agg.meses_ate_decisao < 0, "meses_ate_decisao"] = None
    agg.loc[agg.duracao_meses < 0, "duracao_meses"] = None

    out = Path(a.saida); out.mkdir(exist_ok=True)
    agg.to_parquet(out / "agregado.parquet", index=False)
    meta = {
        "uf": a.uf, "uf_nome": a.uf_nome,
        "periodo_inicio": str(base.mes.min().date()), "periodo_fim": str(base.mes.max().date()),
        "registros": int(len(base)), "gerado_em": datetime.now().isoformat(timespec="minutes"),
        "sintetico": a.sintetico, "arquivos": log,
    }
    (out / "metadados.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK: {len(base):,} registros -> {len(agg):,} linhas agregadas em {out/'agregado.parquet'}")
    print(base.groupby(["grupo_especie", "desfecho"]).size().to_string())


if __name__ == "__main__":
    main()
