import csv
from pathlib import Path

CODIGO_CONCLUSAO = 51
PRAZO_LEGAL_EM_DIAS = {"despacho": 5, "decisao": 10, "sentenca": 30, "embargos_de_declaracao": 5}
CAMINHO_DA_CLASSIFICACAO_OFICIAL = Path(__file__).parent.parent / "dados" / "tpu" / "tpu_classificacao.csv"


def carregar_categoria_por_codigo():
    categoria_por_codigo = {}
    with open(CAMINHO_DA_CLASSIFICACAO_OFICIAL, encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            categoria = linha["categoria"]
            if categoria not in ("despacho", "decisao", "sentenca"):
                continue
            if "embargos de declaração" in linha["caminho"].lower():
                categoria = "embargos_de_declaracao"
            categoria_por_codigo[int(linha["codigo"])] = categoria
    return categoria_por_codigo


CATEGORIA_POR_CODIGO = carregar_categoria_por_codigo()
CATEGORIA_POR_CODIGO_PROVISORIA = CATEGORIA_POR_CODIGO
