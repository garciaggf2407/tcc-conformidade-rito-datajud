import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classificacao_de_atos_do_juiz import PRAZO_LEGAL_EM_DIAS

SENTENCAS_MINIMAS_POR_COMARCA = 30

caminho_do_log_de_eventos = sys.argv[1]
sys.argv = ["", caminho_do_log_de_eventos]
import contextlib
import io

with contextlib.redirect_stdout(io.StringIO()):
    import medir_prazos_do_juiz as medicao

nomes_das_unidades_por_foro = defaultdict(Counter)
with open(caminho_do_log_de_eventos, encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        if linha["movimento_codigo"] == "26":
            nomes_das_unidades_por_foro[linha["numero_processo"][-4:]][linha["orgao_julgador_nome"]] += 1

prazo = PRAZO_LEGAL_EM_DIAS["sentenca"]
sentencas_por_foro = defaultdict(list)
for numero_processo, _, dias_uteis in medicao.medicoes_por_categoria["sentenca"]:
    sentencas_por_foro[numero_processo[-4:]].append(dias_uteis)

linhas = []
for foro, dias in sentencas_por_foro.items():
    if len(dias) < SENTENCAS_MINIMAS_POR_COMARCA:
        continue
    acima = sum(1 for valor in dias if valor > prazo)
    unidade_mais_comum = nomes_das_unidades_por_foro[foro].most_common(1)[0][0]
    linhas.append((acima / len(dias), foro, len(dias), unidade_mais_comum))

print(f"Sentenças acima de {prazo} dias úteis, por foro (quatro últimos dígitos do número), com pelo menos {SENTENCAS_MINIMAS_POR_COMARCA} sentenças:")
for proporcao, foro, quantidade, unidade_mais_comum in sorted(linhas):
    print(f"  {foro}  {quantidade:>4} sentenças  {100 * proporcao:5.1f}%  (unidade mais comum: {unidade_mais_comum})")
