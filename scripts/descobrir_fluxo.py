import os
import sys
from pathlib import Path

import pandas
import pm4py
from pm4py.visualization.dfg import visualizer as visualizador_de_ligacoes

os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"
sys.path.insert(0, str(Path(__file__).parent))
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO_PROVISORIA

NOME_DA_ATIVIDADE_POR_CATEGORIA = {"despacho": "Despacho (juiz)", "decisao": "Decisão (juiz)", "sentenca": "Sentença (juiz)"}

caminho_do_log_de_eventos = Path(sys.argv[1])
caminho_da_figura = Path(sys.argv[2])
cobertura_minima_de_processos = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
frequencia_minima_da_ligacao = int(sys.argv[4]) if len(sys.argv) > 4 else 100

eventos = pandas.read_csv(caminho_do_log_de_eventos, dtype={"numero_processo": str})
eventos = eventos.drop_duplicates(subset=["numero_processo", "movimento_codigo", "movimento_data_hora"])
eventos["atividade"] = [
    NOME_DA_ATIVIDADE_POR_CATEGORIA.get(CATEGORIA_POR_CODIGO_PROVISORIA.get(codigo), str(nome).strip())
    for codigo, nome in zip(eventos["movimento_codigo"], eventos["movimento_nome"])
]
eventos["momento"] = pandas.to_datetime(eventos["movimento_data_hora"], utc=True)

quantidade_de_processos = eventos["numero_processo"].nunique()
processos_por_atividade = eventos.groupby("atividade")["numero_processo"].nunique()
atividades_mantidas = processos_por_atividade[processos_por_atividade >= cobertura_minima_de_processos * quantidade_de_processos].index
eventos_filtrados = eventos[eventos["atividade"].isin(atividades_mantidas)]

log = pm4py.format_dataframe(eventos_filtrados, case_id="numero_processo", activity_key="atividade", timestamp_key="momento")
ligacoes, inicios, fins = pm4py.discover_dfg(log)
ligacoes_mantidas = {ligacao: frequencia for ligacao, frequencia in ligacoes.items() if frequencia >= frequencia_minima_da_ligacao}
atividades_nas_ligacoes = {atividade for ligacao in ligacoes_mantidas for atividade in ligacao}
inicios = {atividade: quantidade for atividade, quantidade in inicios.items() if atividade in atividades_nas_ligacoes}
fins = {atividade: quantidade for atividade, quantidade in fins.items() if atividade in atividades_nas_ligacoes}

ocorrencias_por_atividade = eventos_filtrados["atividade"].value_counts().to_dict()
ocorrencias_por_atividade = {atividade: ocorrencias for atividade, ocorrencias in ocorrencias_por_atividade.items() if atividade in atividades_nas_ligacoes}

caminho_da_figura.parent.mkdir(parents=True, exist_ok=True)
desenho = visualizador_de_ligacoes.apply(
    ligacoes_mantidas,
    activities_count=ocorrencias_por_atividade,
    parameters={"start_activities": inicios, "end_activities": fins, "format": caminho_da_figura.suffix.lstrip(".")},
)
visualizador_de_ligacoes.save(desenho, str(caminho_da_figura))

print(f"Processos: {quantidade_de_processos}")
print(f"Atividades mantidas ({len(atividades_mantidas)} de {processos_por_atividade.size}), presentes em pelo menos {cobertura_minima_de_processos:.0%} dos processos:")
for atividade, processos in processos_por_atividade[atividades_mantidas].sort_values(ascending=False).items():
    print(f"  {processos:>4}  {atividade}")
print(f"Ligações mantidas: {len(ligacoes_mantidas)} de {len(ligacoes)} (frequência mínima {frequencia_minima_da_ligacao})")
print(f"Figura: {caminho_da_figura}")
