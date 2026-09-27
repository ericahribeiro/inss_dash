# Painel de Referência Previdenciária – RS

Projeto Integrador V-A · PUC Goiás · Big Data e Inteligência Artificial

Dashboard em Streamlit que mostra como o INSS decidiu pedidos parecidos com o de um
cliente (benefício, idade, sexo, clientela e doença/CID), com dados abertos do INSS.

## Como rodar

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
2. Abrir o painel (os dados já processados estão em `dados/`):
   ```
   streamlit run app.py
   ```

### Para atualizar os dados

1. Baixe as planilhas mensais (.xlsx) de **Benefícios concedidos** e **Benefícios
   indeferidos** para `dados_brutos/` (cada uma tem de 25 a 130 MB):
   ```
   python scripts/baixa_dados.py            # últimos 12 meses
   ```
2. Rode:
   ```
   python prepara_dados.py
   ```
   O script mostra quantas linhas leu de cada arquivo e quantas entraram no recorte.
   Cada planilha nacional leva cerca de 30 segundos para ser lida.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `prepara_dados.py` | Lê as planilhas, acha o cabeçalho, filtra RS e as espécies 31, 91, 32, 92 e 87, classifica o desfecho (concedido administrativo, concedido judicial, indeferido), calcula faixa etária, capítulo da CID e tempo até a decisão, e agrega |
| `app.py` | Dashboard: perfil → KPIs → motivos de negativa → idade → tendência → consulta por doença (CID) |
| `dados/agregado.parquet` | Dados agregados (sem dados pessoais) |
| `dados/metadados.json` | Período, total de registros e log de cada arquivo lido |
| `scripts/baixa_dados.py` | Baixa as planilhas do INSS pela API do dados.gov.br |
| `scripts/inspeciona_planilha.py` | Mostra colunas e valores mais comuns de uma planilha (análise exploratória) |
| `scripts/valida_numeros.py` | Recalcula um mês direto das planilhas e confere com o painel |
| `scripts/gera_dados_teste.py` | Gera planilhas sintéticas para testar sem baixar os dados reais |

## Validação

Janeiro/2026 recalculado direto das planilhas originais bate exatamente com o painel
(`python scripts/valida_numeros.py <concedidos jan> <indeferidos jan>` → "Tudo confere.").

## Indicadores (KPIs)

Por perfil (benefício, idade, sexo, clientela e período):

| KPI | Cálculo |
|---|---|
| Pedidos decididos pelo INSS | concessões administrativas + indeferimentos |
| Aprovados direto no INSS | concessões administrativas ÷ pedidos decididos |
| Concessões que vieram da Justiça | concessões judiciais ÷ total de concessões |
| Tempo típico até concessão judicial | mediana de meses entre DIB e DDB |

Por doença (CID), só com concessões administrativas: número de concessões, posição no
ranking, faixa etária mais comum e duração típica concedida (mediana entre DIB e DCB).

**Por que o CID não entra na taxa de aprovação:** a planilha de indeferidos do INSS não
traz o CID, e as concessões judiciais quase nunca trazem (menos de 2% no período).

Fonte: dados.gov.br — "Benefícios concedidos" e "Benefícios indeferidos" (INSS).
