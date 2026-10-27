import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

caminho_do_log_de_eventos = Path(sys.argv[1])

eventos_por_processo = defaultdict(list)
contagem_por_codigo = Counter()
nome_por_codigo = {}
datas_de_ajuizamento = []
niveis_de_sigilo = Counter()

with open(caminho_do_log_de_eventos, encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        codigo = int(linha["movimento_codigo"]) if linha["movimento_codigo"] else None
        contagem_por_codigo[codigo] += 1
        nome_por_codigo[codigo] = linha["movimento_nome"]
        eventos_por_processo[linha["numero_processo"]].append((linha["movimento_data_hora"], codigo))
        if len(eventos_por_processo[linha["numero_processo"]]) == 1:
            datas_de_ajuizamento.append(linha["data_ajuizamento"])
            niveis_de_sigilo[linha["nivel_sigilo"]] += 1

quantidade_de_eventos_por_processo = sorted(len(eventos) for eventos in eventos_por_processo.values())
metade = len(quantidade_de_eventos_por_processo) // 2

print(f"Processos: {len(eventos_por_processo)}")
print(f"Eventos por processo: mínimo {quantidade_de_eventos_por_processo[0]}, mediana {quantidade_de_eventos_por_processo[metade]}, máximo {quantidade_de_eventos_por_processo[-1]}")
print(f"Ajuizamento: de {min(datas_de_ajuizamento)} a {max(datas_de_ajuizamento)}")
print(f"Nível de sigilo: {dict(niveis_de_sigilo)}")

todas_as_datas = [data for eventos in eventos_por_processo.values() for data, _ in eventos if data]
print(f"Movimentos: de {min(todas_as_datas)} a {max(todas_as_datas)}")
print(f"Movimentos sem data: {sum(1 for eventos in eventos_por_processo.values() for data, _ in eventos if not data)}")
print(f"Movimentos sem código: {contagem_por_codigo.get(None, 0)}")
print()
print("Todos os códigos de movimento, do mais frequente ao menos frequente:")
print(f"{'código':>7}  {'ocorrências':>11}  {'processos':>9}  nome")
processos_por_codigo = Counter()
for eventos in eventos_por_processo.values():
    for codigo in {codigo for _, codigo in eventos}:
        processos_por_codigo[codigo] += 1
for codigo, ocorrencias in contagem_por_codigo.most_common():
    print(f"{str(codigo):>7}  {ocorrencias:>11}  {processos_por_codigo[codigo]:>9}  {nome_por_codigo[codigo]}")
