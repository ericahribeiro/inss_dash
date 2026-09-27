import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import unquote

API = "https://dados.gov.br/api/publico/conjuntos-dados/"
CONJUNTOS = {
    "concedidos": "beneficios-concedidos-plano-de-dados-abertos-jun-2023-a-jun-2025",
    "indeferidos": "beneficios-indeferidos-plano-de-dados-abertos-jun-2023-a-jun-2025",
}
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
CABECALHO = {"User-Agent": "Mozilla/5.0 (projeto academico PUC Goias)"}


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def mes_do_titulo(titulo: str):
    t = sem_acento(titulo)
    ano = re.search(r"(20\d{2})", t)
    mes = next((n for nome, n in MESES.items() if nome in t), None)
    return (int(ano.group(1)), mes) if ano and mes else None


def lista_recursos(conjunto: str):
    req = urllib.request.Request(API + conjunto, headers=CABECALHO)
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = json.load(r)
    itens = []
    for rec in dados["resources"]:
        ym = mes_do_titulo(rec.get("name") or rec.get("titulo") or "")
        if ym:
            itens.append((ym, rec["url"]))
    return sorted(itens)


def baixa(url: str, destino: Path):
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    req = urllib.request.Request(url, headers=CABECALHO)
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        feito = 0
        while bloco := r.read(1 << 20):
            f.write(bloco)
            feito += len(bloco)
            if total:
                print(f"\r   {feito/1e6:6.1f} de {total/1e6:.1f} MB", end="", flush=True)
    tmp.rename(destino)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=12)
    ap.add_argument("--destino", default="dados_brutos")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()

    pasta = Path(a.destino)
    pasta.mkdir(exist_ok=True)
    for tipo, conjunto in CONJUNTOS.items():
        recursos = lista_recursos(conjunto)
        escolhidos = recursos[-a.meses:]
        print(f"\n{tipo.upper()}: {len(recursos)} meses publicados; usando "
              f"{escolhidos[0][0][1]:02d}/{escolhidos[0][0][0]} a {escolhidos[-1][0][1]:02d}/{escolhidos[-1][0][0]}")
        for (ano, mes), url in escolhidos:
            ext = Path(unquote(url)).suffix.lower() or ".xlsx"
            if ext == ".xlsx" and url.endswith(".xlsx.xlsx"):
                ext = ".xlsx"
            destino = pasta / f"{tipo}_{ano}-{mes:02d}{ext}"
            if a.listar:
                print(f"  {destino.name}  <-  {unquote(url.split('/')[-1])}")
                continue
            if destino.exists():
                print(f"  já existe: {destino.name}")
                continue
            print(f"  baixando {destino.name}")
            try:
                baixa(url, destino)
            except Exception as e:
                print(f"  ERRO ao baixar {destino.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
