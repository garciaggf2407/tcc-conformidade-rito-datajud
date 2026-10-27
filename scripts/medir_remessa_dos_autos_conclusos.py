import csv
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median, quantiles

sys.path.insert(0, str(Path(__file__).parent))
from calendario_forense import contar_dias_uteis
from classificacao_de_atos_do_juiz import CODIGO_CONCLUSAO

CODIGOS_DE_JUNTADA = {85: "petição", 581: "documento"}
PRAZO_DA_REMESSA_EM_DIAS = 1
REPETICOES_DO_BOOTSTRAP = 1000


def ler_data(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


eventos_por_processo = defaultdict(set)
nome_por_codigo = {}
with open(Path(sys.argv[1]), encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        codigo = int(linha["movimento_codigo"])
        eventos_por_processo[linha["numero_processo"]].add((ler_data(linha["movimento_data_hora"]), codigo))
        nome_por_codigo[codigo] = linha["movimento_nome"]

medicoes = []
movimento_anterior_a_conclusao = Counter()
quantidade_de_conclusoes = 0
for numero_processo, conjunto_de_eventos in eventos_por_processo.items():
    eventos = sorted(conjunto_de_eventos)
    for posicao, (data_da_conclusao, codigo) in enumerate(eventos):
        if codigo != CODIGO_CONCLUSAO:
            continue
        quantidade_de_conclusoes += 1
        if posicao == 0:
            movimento_anterior_a_conclusao["nenhum"] += 1
            continue
        data_anterior, codigo_anterior = eventos[posicao - 1]
        movimento_anterior_a_conclusao[nome_por_codigo[codigo_anterior]] += 1
        if codigo_anterior not in CODIGOS_DE_JUNTADA:
            continue
        dias_corridos = (data_da_conclusao - data_anterior).total_seconds() / 86400
        dias_uteis = contar_dias_uteis(data_anterior, data_da_conclusao)
        medicoes.append((numero_processo, dias_corridos, dias_uteis, CODIGOS_DE_JUNTADA[codigo_anterior]))


def proporcao_acima_do_prazo(lista_de_medicoes):
    return sum(1 for medicao in lista_de_medicoes if medicao[2] > PRAZO_DA_REMESSA_EM_DIAS) / len(lista_de_medicoes)


def intervalo_de_confianca_por_processo(lista_de_medicoes):
    medicoes_por_processo = defaultdict(list)
    for medicao in lista_de_medicoes:
        medicoes_por_processo[medicao[0]].append(medicao)
    processos = list(medicoes_por_processo)
    sorteador = random.Random(2026)
    estimativas = []
    for _ in range(REPETICOES_DO_BOOTSTRAP):
        reamostra = [medicao for processo in sorteador.choices(processos, k=len(processos)) for medicao in medicoes_por_processo[processo]]
        estimativas.append(proporcao_acima_do_prazo(reamostra))
    estimativas.sort()
    return estimativas[int(0.025 * REPETICOES_DO_BOOTSTRAP)], estimativas[int(0.975 * REPETICOES_DO_BOOTSTRAP) - 1]


print(f"Conclusões: {quantidade_de_conclusoes}")
print("Movimento imediatamente anterior a cada Conclusão:")
for nome, quantidade in movimento_anterior_a_conclusao.most_common(10):
    print(f"  {quantidade:>6} ({100 * quantidade / quantidade_de_conclusoes:4.1f}%)  {nome}")
print()
print(f"Remessa dos autos conclusos (art. 228), medida quando a Conclusão vem logo depois de juntada de petição ou documento; prazo de {PRAZO_DA_REMESSA_EM_DIAS} dia útil:")
grupos = [("petição ou documento", medicoes)] + [(tipo, [medicao for medicao in medicoes if medicao[3] == tipo]) for tipo in CODIGOS_DE_JUNTADA.values()]
for rotulo, grupo in grupos:
    if not grupo:
        continue
    dias_uteis = sorted(medicao[2] for medicao in grupo)
    percentil_90 = quantiles(dias_uteis, n=10)[-1] if len(dias_uteis) > 1 else dias_uteis[0]
    limite_inferior, limite_superior = intervalo_de_confianca_por_processo(grupo)
    no_mesmo_dia = sum(1 for dias in dias_uteis if dias == 0) / len(dias_uteis)
    print(
        f"  {rotulo:>22}: {len(grupo)} remessas em {len({medicao[0] for medicao in grupo})} processos; "
        f"mediana {median(medicao[1] for medicao in grupo):.1f} dias corridos e {median(dias_uteis):.1f} úteis; p90 {percentil_90:.1f} úteis; "
        f"sem dia útil decorrido {100 * no_mesmo_dia:.1f}%; acima do prazo {100 * proporcao_acima_do_prazo(grupo):.1f}% "
        f"({100 * limite_inferior:.1f}% a {100 * limite_superior:.1f}%)"
    )
