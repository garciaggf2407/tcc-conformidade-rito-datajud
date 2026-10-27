import sys
from pathlib import Path

import pandas
import pm4py

sys.path.insert(0, str(Path(__file__).parent))
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO

NOME_DA_ATIVIDADE_POR_CATEGORIA = {"despacho": "Despacho (juiz)", "decisao": "Decisão (juiz)", "sentenca": "Sentença (juiz)"}
SEGUNDOS_POR_DIA = 86400

caminho_do_log_de_eventos = Path(sys.argv[1])
cobertura_minima_de_processos = float(sys.argv[2]) if len(sys.argv) > 2 else 0.2
frequencia_minima_da_ligacao = int(sys.argv[3]) if len(sys.argv) > 3 else 500

eventos = pandas.read_csv(caminho_do_log_de_eventos, dtype={"numero_processo": str})
eventos = eventos.drop_duplicates(subset=["numero_processo", "movimento_codigo", "movimento_data_hora"])
eventos["atividade"] = [
    NOME_DA_ATIVIDADE_POR_CATEGORIA.get(CATEGORIA_POR_CODIGO.get(codigo), str(nome).strip())
    for codigo, nome in zip(eventos["movimento_codigo"], eventos["movimento_nome"])
]
eventos["momento"] = pandas.to_datetime(eventos["movimento_data_hora"], utc=True)

quantidade_de_processos = eventos["numero_processo"].nunique()
processos_por_atividade = eventos.groupby("atividade")["numero_processo"].nunique()
atividades_mantidas = processos_por_atividade[processos_por_atividade >= cobertura_minima_de_processos * quantidade_de_processos].index
eventos_filtrados = eventos[eventos["atividade"].isin(atividades_mantidas)]

log = pm4py.format_dataframe(eventos_filtrados, case_id="numero_processo", activity_key="atividade", timestamp_key="momento")
ligacoes, _, _ = pm4py.discover_dfg(log)
tempos_por_ligacao, _, _ = pm4py.discover_performance_dfg(log)

ligacoes_mantidas = sorted(
    (ligacao for ligacao, frequencia in ligacoes.items() if frequencia >= frequencia_minima_da_ligacao),
    key=lambda ligacao: -ligacoes[ligacao],
)
tempo_total_de_todas_as_ligacoes = sum(tempos["sum"] for tempos in tempos_por_ligacao.values())

print(f"Processos: {quantidade_de_processos}; ligações com pelo menos {frequencia_minima_da_ligacao} passagens: {len(ligacoes_mantidas)} de {len(ligacoes)}")
print("Tempo entre atividades no grafo da Figura 1 (dias corridos):")
print(f"{'de':>28}  {'para':>28}  {'passagens':>9}  {'mediana':>7}  {'p. do tempo total':>17}")
for origem, destino in ligacoes_mantidas:
    tempos = tempos_por_ligacao[(origem, destino)]
    print(
        f"{origem[:28]:>28}  {destino[:28]:>28}  {ligacoes[(origem, destino)]:>9}  "
        f"{tempos['median'] / SEGUNDOS_POR_DIA:>7.1f}  {100 * tempos['sum'] / tempo_total_de_todas_as_ligacoes:>16.1f}%"
    )
parcela_das_ligacoes_mantidas = sum(tempos_por_ligacao[ligacao]["sum"] for ligacao in ligacoes_mantidas) / tempo_total_de_todas_as_ligacoes
print(f"As ligações mantidas somam {100 * parcela_das_ligacoes_mantidas:.1f}% do tempo entre atividades do log filtrado.")
ligacoes_da_conclusao_ao_ato = [("Conclusão", atividade) for atividade in NOME_DA_ATIVIDADE_POR_CATEGORIA.values() if ("Conclusão", atividade) in tempos_por_ligacao]
parcela_da_conclusao_ao_ato = sum(tempos_por_ligacao[ligacao]["sum"] for ligacao in ligacoes_da_conclusao_ao_ato) / tempo_total_de_todas_as_ligacoes
print(f"As ligações da Conclusão ao despacho, à decisão e à sentença somam {100 * parcela_da_conclusao_ao_ato:.1f}% desse tempo.")
