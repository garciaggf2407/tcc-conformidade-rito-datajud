import os
import sys
from collections import Counter
from pathlib import Path

import pandas
import pm4py

os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"
sys.path.insert(0, str(Path(__file__).parent))
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO

caminho_do_log_de_eventos = Path(sys.argv[1])
pasta_do_modelo = Path(sys.argv[2])
pasta_do_modelo.mkdir(parents=True, exist_ok=True)

CODIGO_DISTRIBUICAO = 26
CODIGO_EMENDA_DA_INICIAL = 15085
CODIGO_AUDIENCIA = 970
CODIGOS_DE_RESULTADO_DA_CONCILIACAO = {12531, 12532}
CODIGO_SANEAMENTO = 12387
CODIGO_TRANSITO_EM_JULGADO = 848
CODIGO_INICIO_DO_CUMPRIMENTO_DE_SENTENCA = 11385
CODIGOS_DE_JULGAMENTO_FORA_DA_FASE_DE_CONHECIMENTO = {196, 14099, 1049, 1042}

MODELO_NORMATIVO = (
    "->( 'Distribuição', *( tau, 'Emenda da inicial' ), "
    "X( 'Sentença', ->( X( 'Audiência de conciliação', tau ), "
    "X( 'Sentença', ->( 'Saneamento', X( 'Audiência de instrução', tau ), 'Sentença' ) ) ) ), "
    "X( 'Trânsito em julgado', tau ) )"
)


def etapa_do_rito(codigo, complementos):
    complementos = complementos if isinstance(complementos, str) else ""
    if codigo == CODIGO_DISTRIBUICAO:
        return "Distribuição"
    if codigo == CODIGO_EMENDA_DA_INICIAL:
        return "Emenda da inicial"
    if codigo in CODIGOS_DE_RESULTADO_DA_CONCILIACAO:
        return "Audiência de conciliação"
    if codigo == CODIGO_AUDIENCIA and "situacao_da_audiencia=realizada" in complementos:
        if "tipo_de_audiencia=conciliação" in complementos or "tipo_de_audiencia=mediação" in complementos:
            return "Audiência de conciliação"
        if "tipo_de_audiencia=instrução" in complementos:
            return "Audiência de instrução"
        return None
    if codigo == CODIGO_SANEAMENTO:
        return "Saneamento"
    if codigo == CODIGO_TRANSITO_EM_JULGADO:
        return "Trânsito em julgado"
    categoria = CATEGORIA_POR_CODIGO.get(codigo)
    if categoria == "sentenca" and codigo not in CODIGOS_DE_JULGAMENTO_FORA_DA_FASE_DE_CONHECIMENTO:
        return "Sentença"
    return None


eventos = pandas.read_csv(caminho_do_log_de_eventos, dtype={"numero_processo": str})
eventos = eventos.drop_duplicates(subset=["numero_processo", "movimento_codigo", "movimento_data_hora"])
eventos["momento"] = pandas.to_datetime(eventos["movimento_data_hora"], utc=True)
eventos = eventos.sort_values(["numero_processo", "momento", "movimento_codigo"])

linhas_do_log_do_rito = []
processos_cortados_no_cumprimento = 0
for numero_processo, eventos_do_processo in eventos.groupby("numero_processo", sort=False):
    etapa_anterior = None
    for linha in eventos_do_processo.itertuples():
        if linha.movimento_codigo == CODIGO_INICIO_DO_CUMPRIMENTO_DE_SENTENCA:
            processos_cortados_no_cumprimento += 1
            break
        etapa = etapa_do_rito(linha.movimento_codigo, linha.complementos)
        if etapa is None or etapa == etapa_anterior:
            continue
        linhas_do_log_do_rito.append({"case:concept:name": numero_processo, "concept:name": etapa, "time:timestamp": linha.momento})
        etapa_anterior = etapa

log_do_rito_completo = pandas.DataFrame(linhas_do_log_do_rito)
processos_com_sentenca = set(log_do_rito_completo.loc[log_do_rito_completo["concept:name"] == "Sentença", "case:concept:name"])
processos_sem_sentenca = log_do_rito_completo["case:concept:name"].nunique() - len(processos_com_sentenca)
log_do_rito = log_do_rito_completo[log_do_rito_completo["case:concept:name"].isin(processos_com_sentenca)]
quantidade_de_processos = log_do_rito["case:concept:name"].nunique()

arvore = pm4py.parse_process_tree(MODELO_NORMATIVO)
rede, marcacao_inicial, marcacao_final = pm4py.convert_to_petri_net(arvore)
modelo_bpmn = pm4py.convert_to_bpmn(arvore)
pm4py.write_bpmn(modelo_bpmn, str(pasta_do_modelo / "modelo_normativo.bpmn"))

alinhamentos = pm4py.conformance_diagnostics_alignments(log_do_rito, rede, marcacao_inicial, marcacao_final)
identificadores = list(log_do_rito.groupby("case:concept:name", sort=False).groups.keys())
aderencias = [alinhamento["fitness"] for alinhamento in alinhamentos]
etapas_fora_do_rito = Counter()
etapas_previstas_puladas = Counter()
processos_com_desvio = 0
for alinhamento in alinhamentos:
    houve_desvio = False
    for passo_no_log, passo_no_modelo in alinhamento["alignment"]:
        if passo_no_log != ">>" and passo_no_modelo == ">>":
            etapas_fora_do_rito[passo_no_log] += 1
            houve_desvio = True
        elif passo_no_log == ">>" and passo_no_modelo not in (">>", None):
            etapas_previstas_puladas[passo_no_modelo] += 1
            houve_desvio = True
    processos_com_desvio += houve_desvio

aderencia_do_log = pm4py.fitness_alignments(log_do_rito, rede, marcacao_inicial, marcacao_final)
variantes = log_do_rito.groupby("case:concept:name")["concept:name"].apply(lambda etapas: " → ".join(etapas)).value_counts()
processos_por_etapa = log_do_rito.groupby("concept:name")["case:concept:name"].nunique().sort_values(ascending=False)

print(f"Processos com sentença, analisados: {quantidade_de_processos}; sem sentença até o fim dos dados, fora da análise: {processos_sem_sentenca}; cortados no início do cumprimento de sentença: {processos_cortados_no_cumprimento}")
padroes = Counter()
for etapas in log_do_rito.groupby("case:concept:name", sort=False)["concept:name"].apply(list):
    posicao_da_primeira_sentenca = etapas.index("Sentença")
    antes, depois = etapas[:posicao_da_primeira_sentenca], etapas[posicao_da_primeira_sentenca + 1:]
    if antes in (["Distribuição"], ["Distribuição", "Emenda da inicial"]):
        padroes["nenhuma etapa intermediária observável antes da sentença"] += 1
    if etapas.count("Sentença") > 1:
        padroes["mais de uma sentença registrada"] += 1
    if "Audiência de instrução" in antes and "Saneamento" not in antes[:antes.index("Audiência de instrução")]:
        padroes["audiência de instrução sem saneamento registrado antes"] += 1
    if "Trânsito em julgado" in depois and "Sentença" in depois[depois.index("Trânsito em julgado") + 1:]:
        padroes["sentença registrada depois do trânsito em julgado"] += 1
    if "Audiência de conciliação" in antes and "Saneamento" in antes and antes.index("Saneamento") < antes.index("Audiência de conciliação"):
        padroes["conciliação depois do saneamento"] += 1
    if any(etapa in depois for etapa in ("Saneamento", "Audiência de instrução", "Audiência de conciliação", "Emenda da inicial")):
        padroes["etapa anterior à sentença registrada depois dela"] += 1
print("Padrões nas sequências dos processos com sentença:")
for padrao, quantidade in padroes.most_common():
    print(f"  {quantidade:>5} ({100 * quantidade / quantidade_de_processos:4.1f}%)  {padrao}")
print("Processos em que cada etapa aparece:")
for etapa, processos in processos_por_etapa.items():
    print(f"  {processos:>5} ({100 * processos / quantidade_de_processos:4.1f}%)  {etapa}")
print(f"Aderência média por processo: {sum(aderencias) / len(aderencias):.3f}; aderência do log: {aderencia_do_log}")
print(f"Processos totalmente aderentes: {sum(1 for valor in aderencias if valor == 1.0)} ({100 * sum(1 for valor in aderencias if valor == 1.0) / len(aderencias):.1f}%)")
print(f"Processos com algum desvio: {processos_com_desvio} ({100 * processos_com_desvio / len(alinhamentos):.1f}%)")
print("Etapas registradas fora do lugar previsto no rito (movimentos só no log):")
for etapa, quantidade in etapas_fora_do_rito.most_common():
    print(f"  {quantidade:>5}  {etapa}")
print("Etapas obrigatórias do modelo que não aparecem (movimentos só no modelo):")
for etapa, quantidade in etapas_previstas_puladas.most_common():
    print(f"  {quantidade:>5}  {etapa}")
print("Variantes mais frequentes:")
for variante, quantidade in variantes.head(12).items():
    print(f"  {quantidade:>5} ({100 * quantidade / quantidade_de_processos:4.1f}%)  {variante}")
log_do_rito.to_csv(pasta_do_modelo / "log_do_rito.csv", index=False)
pandas.DataFrame({"numero_processo": identificadores, "aderencia": aderencias}).to_csv(pasta_do_modelo / "aderencia_por_processo.csv", index=False)
