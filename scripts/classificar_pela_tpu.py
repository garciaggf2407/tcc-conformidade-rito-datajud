import csv
import json
import sys
from pathlib import Path

caminho_da_tabela = Path(sys.argv[1])
caminho_de_saida = Path(sys.argv[2])

itens = json.loads(caminho_da_tabela.read_text(encoding="utf-8"))
item_por_codigo = {item["id"]: item for item in itens}


def caminho_ate_a_raiz(codigo):
    caminho = []
    atual = item_por_codigo.get(codigo)
    while atual is not None:
        caminho.append(atual)
        atual = item_por_codigo.get(atual.get("cod_item_pai"))
    return list(reversed(caminho))


CATEGORIA_POR_RAMO_DO_MAGISTRADO = {"despacho": "despacho", "decisão": "decisao", "julgamento": "sentenca"}

with open(caminho_de_saida, "w", encoding="utf-8", newline="") as arquivo:
    escritor = csv.writer(arquivo)
    escritor.writerow(["codigo", "nome", "nivel_1", "nivel_2", "categoria", "caminho"])
    for codigo in sorted(item_por_codigo):
        caminho = caminho_ate_a_raiz(codigo)
        nomes = [item["nome"].strip() for item in caminho]
        nivel_1 = nomes[0] if nomes else ""
        nivel_2 = nomes[1] if len(nomes) > 1 else ""
        categoria = ""
        if nivel_1.lower() == "magistrado":
            categoria = CATEGORIA_POR_RAMO_DO_MAGISTRADO.get(nivel_2.lower(), "outro ato do magistrado")
        escritor.writerow([codigo, item_por_codigo[codigo]["nome"].strip(), nivel_1, nivel_2, categoria, " > ".join(nomes)])

raizes = sorted({caminho_ate_a_raiz(codigo)[0]["nome"].strip() for codigo in item_por_codigo})
ramos_do_magistrado = sorted({caminho_ate_a_raiz(codigo)[1]["nome"].strip() for codigo in item_por_codigo if len(caminho_ate_a_raiz(codigo)) > 1 and caminho_ate_a_raiz(codigo)[0]["nome"].strip().lower() == "magistrado"})
print(f"Códigos na tabela: {len(item_por_codigo)}")
print(f"Raízes (nível 1): {raizes}")
print(f"Ramos sob Magistrado (nível 2): {ramos_do_magistrado}")
print(f"Classificação gravada em {caminho_de_saida}")
