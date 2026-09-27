import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepara_dados import cabecalho_real  # noqa: E402


def main(caminho: str, top: int = 5):
    abas = pd.read_excel(caminho, sheet_name=None, dtype=str, engine="calamine")
    for nome, bruto in abas.items():
        t = cabecalho_real(bruto)
        print(f"\n=== Aba '{nome}': {len(t):,} linhas x {t.shape[1]} colunas ===")
        for col in t.columns:
            freq = t[col].value_counts(dropna=False).head(top)
            vazios = t[col].isna().mean()
            print(f"\n- {col}  (vazios: {vazios:.0%}, valores distintos: {t[col].nunique():,})")
            for valor, n in freq.items():
                print(f"    {str(valor)[:60]:<60} {n:>9,}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
