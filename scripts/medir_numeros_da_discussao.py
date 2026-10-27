import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))
from calendario_forense import contar_dias_uteis
from classificacao_de_atos_do_juiz import CAMINHO_DA_CLASSIFICACAO_OFICIAL, CATEGORIA_POR_CODIGO, CODIGO_CONCLUSAO, PRAZO_LEGAL_EM_DIAS

ORDEM_DAS_CATEGORIAS = ("despacho", "decisao", "sentenca", "embargos_de_declaracao")
CODIGO_PETICAO = 85
CODIGO_AUDIENCIA = 970
REPETICOES_DO_BOOTSTRAP = 1000
ATOS_MINIMOS_POR_GRUPO = 30


def ler_data(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


caminho_do_log_de_eventos = Path(sys.argv[1])
caminho_do_log_do_rito = Path(sys.argv[2])

eventos_por_processo = defaultdict(set)
unidade_por_processo = {}
complementos_das_audiencias = Counter()
with open(caminho_do_log_de_eventos, encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        eventos_por_processo[linha["numero_processo"]].add((ler_data(linha["movimento_data_hora"]), int(linha["movimento_codigo"])))
        unidade_por_processo[linha["numero_processo"]] = linha["orgao_julgador_codigo"]
        if int(linha["movimento_codigo"]) == CODIGO_AUDIENCIA:
            complementos_das_audiencias[(linha["numero_processo"], linha["movimento_data_hora"], linha["complementos"])] += 1
eventos_por_processo = {numero: sorted(eventos) for numero, eventos in eventos_por_processo.items()}

medicoes_por_categoria = defaultdict(list)
for numero_processo, eventos in eventos_por_processo.items():
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
            continue
        inicio_da_sequencia = posicao
        while inicio_da_sequencia > 0 and eventos[inicio_da_sequencia - 1][1] == CODIGO_CONCLUSAO:
            inicio_da_sequencia -= 1
        data_do_ato, categoria = ato_encontrado
        medicoes_por_categoria[categoria].append((
            numero_processo,
            contar_dias_uteis(data_da_conclusao, data_do_ato),
            contar_dias_uteis(eventos[inicio_da_sequencia][0], data_do_ato),
            inicio_da_sequencia != posicao,
        ))


def proporcao_acima_do_prazo(medicoes, prazo, indice_dos_dias):
    return sum(1 for medicao in medicoes if medicao[indice_dos_dias] > prazo) / len(medicoes)


def intervalo_de_confianca_por_processo(medicoes, prazo, indice_dos_dias):
    medicoes_por_processo = defaultdict(list)
    for medicao in medicoes:
        medicoes_por_processo[medicao[0]].append(medicao)
    processos = list(medicoes_por_processo)
    sorteador = random.Random(2026)
    estimativas = []
    for _ in range(REPETICOES_DO_BOOTSTRAP):
        reamostra = [medicao for processo in sorteador.choices(processos, k=len(processos)) for medicao in medicoes_por_processo[processo]]
        estimativas.append(proporcao_acima_do_prazo(reamostra, prazo, indice_dos_dias))
    estimativas.sort()
    return estimativas[int(0.025 * REPETICOES_DO_BOOTSTRAP)], estimativas[int(0.975 * REPETICOES_DO_BOOTSTRAP) - 1]


print("1. Sensibilidade ao critério de início da contagem: última Conclusão antes do ato (critério do trabalho) x primeira de uma sequência de Conclusões seguidas")
for categoria in ORDEM_DAS_CATEGORIAS:
    medicoes = medicoes_por_categoria[categoria]
    prazo = PRAZO_LEGAL_EM_DIAS[categoria]
    linha = f"  {categoria:>22}: {len(medicoes)} atos, {sum(1 for medicao in medicoes if medicao[3])} precedidos de Conclusões seguidas"
    for rotulo, indice_dos_dias in (("última", 1), ("primeira", 2)):
        limite_inferior, limite_superior = intervalo_de_confianca_por_processo(medicoes, prazo, indice_dos_dias)
        linha += (
            f"; contando da {rotulo}: {100 * proporcao_acima_do_prazo(medicoes, prazo, indice_dos_dias):.1f}% acima do prazo "
            f"({100 * limite_inferior:.1f}% a {100 * limite_superior:.1f}%)"
        )
    print(linha)

print()
print(f"2. Grupos com pelo menos {ATOS_MINIMOS_POR_GRUPO} sentenças na amostra")
sentencas = medicoes_por_categoria["sentenca"]
sentencas_por_unidade = Counter(unidade_por_processo[medicao[0]] for medicao in sentencas)
sentencas_por_foro = Counter(medicao[0][-4:] for medicao in sentencas)
print(f"  unidades judiciárias: {len(sentencas_por_unidade)} com sentença; {sum(1 for quantidade in sentencas_por_unidade.values() if quantidade >= ATOS_MINIMOS_POR_GRUPO)} com pelo menos {ATOS_MINIMOS_POR_GRUPO}; maior: {max(sentencas_por_unidade.values())} sentenças")
print(f"  foros (quatro últimos dígitos do número): {len(sentencas_por_foro)} com sentença; {sum(1 for quantidade in sentencas_por_foro.values() if quantidade >= ATOS_MINIMOS_POR_GRUPO)} com pelo menos {ATOS_MINIMOS_POR_GRUPO}")

print()
print("3. Processos sem etapa intermediária registrada antes da primeira sentença: o que há entre a distribuição e a sentença")
etapas_por_processo = defaultdict(list)
with open(caminho_do_log_do_rito, encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        etapas_por_processo[linha["case:concept:name"]].append((linha["concept:name"], datetime.fromisoformat(linha["time:timestamp"])))
processos_sem_etapa_intermediaria = {}
for numero_processo, etapas in etapas_por_processo.items():
    nomes = [nome for nome, _ in etapas]
    if "Sentença" not in nomes:
        continue
    posicao_da_primeira_sentenca = nomes.index("Sentença")
    if nomes[:posicao_da_primeira_sentenca] in (["Distribuição"], ["Distribuição", "Emenda da inicial"]):
        processos_sem_etapa_intermediaria[numero_processo] = (etapas[0][1], etapas[posicao_da_primeira_sentenca][1])
peticoes_antes_da_sentenca = []
processos_com_audiencia_de_qualquer_tipo = 0
for numero_processo, (data_da_distribuicao, data_da_sentenca) in processos_sem_etapa_intermediaria.items():
    entre_as_duas = [codigo for data, codigo in eventos_por_processo[numero_processo] if data_da_distribuicao < data < data_da_sentenca]
    peticoes_antes_da_sentenca.append(entre_as_duas.count(CODIGO_PETICAO))
    processos_com_audiencia_de_qualquer_tipo += CODIGO_AUDIENCIA in entre_as_duas
quantidade = len(peticoes_antes_da_sentenca)
print(f"  processos: {quantidade}")
for minimo in (1, 2, 3):
    com_peticoes = sum(1 for peticoes in peticoes_antes_da_sentenca if peticoes >= minimo)
    print(f"  com pelo menos {minimo} petição(ões) juntada(s) antes da sentença: {com_peticoes} ({100 * com_peticoes / quantidade:.1f}%)")
print(f"  mediana de petições antes da sentença: {median(peticoes_antes_da_sentenca)}")
print(f"  com algum movimento de audiência (qualquer tipo ou situação) antes da sentença: {processos_com_audiencia_de_qualquer_tipo} ({100 * processos_com_audiencia_de_qualquer_tipo / quantidade:.1f}%)")
with open(CAMINHO_DA_CLASSIFICACAO_OFICIAL, encoding="utf-8") as arquivo:
    caminho_na_tpu_por_codigo = {int(linha["codigo"]): linha["caminho"] for linha in csv.DictReader(arquivo)}
tipo_da_primeira_sentenca = Counter()
for numero_processo, (_, data_da_sentenca) in processos_sem_etapa_intermediaria.items():
    codigo_da_sentenca = next(codigo for data, codigo in eventos_por_processo[numero_processo] if data == data_da_sentenca and CATEGORIA_POR_CODIGO.get(codigo) == "sentenca")
    caminho = caminho_na_tpu_por_codigo[codigo_da_sentenca]
    if "Homologação de Transação" in caminho:
        tipo_da_primeira_sentenca["homologação de acordo (transação)"] += 1
    elif "Sem Resolução de Mérito" in caminho:
        tipo_da_primeira_sentenca["sem resolução de mérito"] += 1
    else:
        tipo_da_primeira_sentenca["com resolução de mérito, fora a homologação de acordo"] += 1
print("  primeira sentença, pelo ramo da TPU:")
for tipo, processos in tipo_da_primeira_sentenca.most_common():
    print(f"    {processos:>5} ({100 * processos / quantidade:4.1f}%)  {tipo}")

print()
print("4. Movimentos de audiência (código 970), sem repetições, pelo que o complemento informa")
audiencias = [complementos for _, _, complementos in complementos_das_audiencias]
realizadas = [complementos for complementos in audiencias if "situacao_da_audiencia=realizada" in complementos]
print(f"  movimentos: {len(audiencias)}; sem tipo informado: {sum(1 for complementos in audiencias if 'tipo_de_audiencia=' not in complementos)}")
print(f"  realizadas: {len(realizadas)}; realizadas sem tipo informado: {sum(1 for complementos in realizadas if 'tipo_de_audiencia=' not in complementos)}")
print(f"  sem situação informada: {sum(1 for complementos in audiencias if 'situacao_da_audiencia=' not in complementos)}")

print()
print("5. Processos sem sentença registrada: tempo entre o ajuizamento e a última atualização do registro no DataJud")
caminho_dos_processos = Path(str(caminho_do_log_de_eventos).replace("_eventos.csv", "_processos.jsonl"))
ajuizamento_por_processo = {}
ultima_atualizacao_por_processo = {}
with open(caminho_dos_processos, encoding="utf-8") as arquivo:
    for linha in arquivo:
        registro = json.loads(linha)
        numero_processo = registro["numeroProcesso"]
        ajuizamento = ler_data(registro["dataAjuizamento"])
        atualizacao = ler_data(registro["dataHoraUltimaAtualizacao"])
        ajuizamento_por_processo[numero_processo] = min(ajuizamento, ajuizamento_por_processo.get(numero_processo, ajuizamento))
        ultima_atualizacao_por_processo[numero_processo] = max(atualizacao, ultima_atualizacao_por_processo.get(numero_processo, atualizacao))
processos_sem_sentenca = [numero for numero in eventos_por_processo if numero not in etapas_por_processo]
dias_sem_sentenca = sorted((ultima_atualizacao_por_processo[numero] - ajuizamento_por_processo[numero]).days for numero in processos_sem_sentenca)
print(f"  processos: {len(dias_sem_sentenca)}; dias entre o ajuizamento e a última atualização: mínimo {dias_sem_sentenca[0]}, mediana {median(dias_sem_sentenca)}, máximo {dias_sem_sentenca[-1]}")
print(f"  com menos de 730 dias: {sum(1 for dias in dias_sem_sentenca if dias < 730)}")
