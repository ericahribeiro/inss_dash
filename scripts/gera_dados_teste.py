import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

random.seed(7)

ESPECIES = [("31", "Auxílio Doenca Previdenciário"), ("32", "Aposentadoria por Invalidez Previdenciária"),
            ("87", "Amp. Social Pessoa Portadora Deficiencia"), ("41", "Aposentadoria por Idade")]
CIDS = [("M545", "M54.5 Dor Lombar Baixa"), ("M511", "M51.1 Transt Disco Lombar Outr Intervert Radi"),
        ("F322", "F32.2 Episodio Depressivo Grave s/Sint Psicot"), ("G560", "G56.0 Sindr do Tunel do Carpo"),
        ("0", "Zerados")]
MOTIVOS = ["Nao Constatacao Incapacidade Laborativa", "Perda de Qualidade do Segurado",
           "Nao Atende ao Criterio de Deficiencia para Acesso ao Bpc-Loas", "{ñ class}"]
UFS = ["Rio Grande do Sul"] * 5 + ["Santa Catarina", "Paraná"]

COLS_CONC = ["APS", "APS", "Competência concessão", "Espécie", "Espécie", "CID", "CID", "Despacho",
             "Despacho", "Dt Nascimento", "Sexo.", "Clientela", "UF", "Dt DCB", "Dt DDB", "Dt DIB"]
COLS_IND = ["Competência indeferimento", "Espécie", "Espécie", "Motivo Indeferimento", "Dt Nascimento",
            "Sexo.", "Clientela", "UF", "Dt Indeferimento", "Dt DER"]


def dt(d):
    return d.strftime("%Y-%m-%d 00:00:00")


def main(destino):
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    for ano, mes in [(2025, m) for m in range(9, 13)] + [(2026, m) for m in range(1, 9)]:
        comp, base = f"{ano}{mes:02d}", date(ano, mes, 15)
        conc, ind = [COLS_CONC], [COLS_IND]
        for _ in range(3000):
            cod, nome = random.choice(ESPECIES)
            cid = random.choice(CIDS)
            nasc = dt(base - timedelta(days=365 * random.randint(18, 70)))
            sexo, cli, uf = random.choice(["Masculino", "Feminino"]), random.choice(["Urbano", "Rural"]), random.choice(UFS)
            if random.random() < 0.55:
                judicial = random.random() < 0.15
                dib = base - timedelta(days=random.randint(200, 400) if judicial else random.randint(5, 40))
                dcb = dt(dib + timedelta(days=random.randint(30, 180))) if cod == "31" else "00/00/0000"
                desp = ("4", "Concessao Decorrente de Acao Judicial") if judicial else ("0", "Concessao Normal")
                cid_j = ("0", "Em Branco") if judicial else cid
                conc.append(["1", "Aps Teste", comp, cod, nome, *cid_j, *desp, nasc, sexo, cli, uf,
                             dcb, dt(base), dt(dib)])
            else:
                ind.append([comp, cod, nome, random.choice(MOTIVOS), nasc, sexo, cli, uf,
                            dt(base), dt(base - timedelta(days=random.randint(5, 60)))])
        for nome_arq, linhas in [(f"concedidos_{ano}-{mes:02d}.csv", conc),
                                 (f"indeferidos_{ano}-{mes:02d}.csv", ind)]:
            with open(pasta / nome_arq, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f, delimiter=";").writerows(linhas)
    print(f"Planilhas de teste criadas em {pasta}/")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "teste_brutos")
