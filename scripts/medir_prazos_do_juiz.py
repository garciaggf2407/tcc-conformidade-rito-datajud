import csv
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median, quantiles

sys.path.insert(0, str(Path(__file__).parent))
from calendario_forense import contar_dias_uteis
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO, CODIGO_CONCLUSAO, PRAZO_LEGAL_EM_DIAS

ORDEM_DAS_CATEGORIAS = ("despacho", "decisao", "sentenca", "embargos_de_declaracao")
REPETICOES_DO_BOOTSTRAP = 1000


def ler_data(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


eventos_por_processo = defaultdict(set)
with open(Path(sys.argv[1]), encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        eventos_por_processo[linha["numero_processo"]].add((ler_data(linha["movimento_data_hora"]), int(linha["movimento_codigo"])))

medicoes_por_categoria = defaultdict(list)
desfecho_das_conclusoes = Counter()
for numero_processo, conjunto_de_eventos in eventos_por_processo.items():
    eventos = sorted(conjunto_de_eventos)
    for posicao, (data_da_conclusao, codigo) in enumerate(eventos):
        if codigo != CODIGO_CONCLUSAO:
            continue
        ato_encontrado = None
        for data_seguinte, codigo_seguinte in eventos[posicao + 1:]:
            if codigo_seguinte == CODIGO_CONCLUSAO:
                break
            if codigo_seguinte in CATEGORIA_POR_CODIGO:
                ato_encontrado = (data_seguinte, CATEGORIA_POR_CODIGO[codigo_seguinte])
                break
        if ato_encontrado is None:
            desfecho_das_conclusoes["sem ato do juiz antes da próxima Conclusão ou do fim"] += 1
            continue
        data_do_ato, categoria = ato_encontrado
        dias_corridos = (data_do_ato - data_da_conclusao).total_seconds() / 86400
        dias_uteis = contar_dias_uteis(data_da_conclusao, data_do_ato)
        medicoes_por_categoria[categoria].append((numero_processo, dias_corridos, dias_uteis))
        desfecho_das_conclusoes[f"seguida de {categoria}"] += 1


def proporcao_acima_do_prazo(medicoes, prazo):
    return sum(1 for _, _, dias_uteis in medicoes if dias_uteis > prazo) / len(medicoes)


def intervalo_de_confianca_por_processo(medicoes, prazo):
    medicoes_por_processo = defaultdict(list)
    for medicao in medicoes:
        medicoes_por_processo[medicao[0]].append(medicao)
    processos = list(medicoes_por_processo)
    sorteador = random.Random(2026)
    estimativas = []
    for _ in range(REPETICOES_DO_BOOTSTRAP):
        reamostra = [medicao for processo in sorteador.choices(processos, k=len(processos)) for medicao in medicoes_por_processo[processo]]
        estimativas.append(proporcao_acima_do_prazo(reamostra, prazo))
    estimativas.sort()
    return estimativas[int(0.025 * REPETICOES_DO_BOOTSTRAP)], estimativas[int(0.975 * REPETICOES_DO_BOOTSTRAP) - 1]


print(f"Processos: {len(eventos_por_processo)}")
print("O que vem depois de cada Conclusão (51):")
for desfecho, quantidade in desfecho_das_conclusoes.most_common():
    print(f"  {quantidade:>6}  {desfecho}")
print()
print("Intervalo entre a Conclusão e o ato do juiz (dias úteis: sem fins de semana, feriados, dias sem expediente do TJSP e recesso do art. 220):")
print(f"{'ato':>22}  {'atos':>5}  {'processos':>9}  {'mediana corr.':>13}  {'mediana úteis':>13}  {'p90 úteis':>9}  {'prazo':>5}  {'acima do prazo (IC 95%)':>26}")
for categoria in ORDEM_DAS_CATEGORIAS:
    medicoes = medicoes_por_categoria[categoria]
    if not medicoes:
        continue
    prazo = PRAZO_LEGAL_EM_DIAS[categoria]
    dias_uteis = sorted(medicao[2] for medicao in medicoes)
    percentil_90 = quantiles(dias_uteis, n=10)[-1] if len(dias_uteis) > 1 else dias_uteis[0]
    limite_inferior, limite_superior = intervalo_de_confianca_por_processo(medicoes, prazo)
    print(
        f"{categoria:>22}  {len(medicoes):>5}  {len({medicao[0] for medicao in medicoes}):>9}  "
        f"{median(medicao[1] for medicao in medicoes):>13.1f}  {median(dias_uteis):>13.1f}  {percentil_90:>9.1f}  {prazo:>4}d  "
        f"{100 * proporcao_acima_do_prazo(medicoes, prazo):>5.1f}% ({100 * limite_inferior:4.1f}% a {100 * limite_superior:4.1f}%)"
    )
