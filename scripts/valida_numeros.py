import sys

import pandas as pd

UF = "Rio Grande do Sul"
GRUPOS = {
    "Auxílio por incapacidade temporária": ["31", "91"],
    "Aposentadoria por incapacidade permanente": ["32", "92"],
    "BPC/LOAS – pessoa com deficiência": ["87"],
}


def le(caminho):
    return pd.read_excel(caminho, dtype=str, engine="calamine", header=1)


def main(arq_conc, arq_ind):
    c, i = le(arq_conc), le(arq_ind)
    mes = pd.to_datetime(c["Competência concessão"].iloc[0], format="%Y%m")
    agg = pd.read_parquet("dados/agregado.parquet")
    agg = agg[agg.mes == mes]

    ok = True
    print(f"Mês {mes:%m/%Y} – {UF}\n")
    print(f"{'Benefício':<45}{'Desfecho':<27}{'Planilha':>10}{'Painel':>10}")
    for grupo, cods in GRUPOS.items():
        cc = c[(c.UF == UF) & c["Espécie"].isin(cods)]
        ii = i[(i.UF == UF) & i["Espécie"].isin(cods)]
        jud = cc["Despacho.1"].str.contains("Judicial", na=False).sum()
        bruto = {"Concedido administrativo": len(cc) - jud, "Concedido judicial": jud,
                 "Indeferido": len(ii)}
        painel = agg[agg.grupo_especie == grupo].groupby("desfecho")["qtd"].sum()
        for desf, n in bruto.items():
            p = int(painel.get(desf, 0))
            marca = "" if p == n else "  <-- DIFERENTE"
            ok &= p == n
            print(f"{grupo:<45}{desf:<27}{n:>10,}{p:>10,}{marca}")
    print("\nTudo confere." if ok else "\nHá diferenças – verifique o pipeline.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
