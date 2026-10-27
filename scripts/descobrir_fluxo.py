import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as pyplot
import pandas
import pm4py
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO

NOME_DA_ATIVIDADE_POR_CATEGORIA = {"despacho": "Despacho", "decisao": "Decisão", "sentenca": "Sentença"}
NOME_DE_LEITURA = {
    "Petição": "Juntada de\npetição", "Documento": "Juntada de\ndocumento", "Definitivo": "Arquivamento\ndefinitivo",
    "Expedição de documento": "Expedição de\ndocumento", "Ato ordinatório": "Ato\nordinatório",
}
POSICAO_NA_FIGURA = {
    "Distribuição": (2.6, 7.8), "Conclusão": (2.6, 4.6),
    "Decisão": (7.4, 7.8), "Despacho": (7.4, 6.2), "Sentença": (7.4, 4.6),
    "Remessa": (12.2, 6.2), "Ato ordinatório": (12.2, 3.6), "Petição": (12.2, 0.9),
    "Expedição de documento": (17.8, 8.8), "Publicação": (17.8, 6.2), "Documento": (17.8, 0.9),
}
CURVATURA_DA_LIGACAO = {("Expedição de documento", "Documento"): -0.7}
LADO_DO_NUMERO = {
    ("Distribuição", "Conclusão"): "direita", ("Ato ordinatório", "Remessa"): "direita", ("Petição", "Ato ordinatório"): "esquerda",
    ("Publicação", "Expedição de documento"): "direita",
}
LADO_DO_LACO = {"Conclusão": "esquerda", "Expedição de documento": "cima", "Petição": "baixo", "Documento": "baixo"}
LARGURA_DA_CAIXA = 3.0
COR_DA_SERIE = "#2a78d6"
COR_CLARA_DA_SERIE = "#e3eefb"
COR_DO_TEXTO = "#0b0b0b"
COR_SECUNDARIA = "#52514e"

caminho_do_log_de_eventos = Path(sys.argv[1])
caminho_da_figura = Path(sys.argv[2])
cobertura_minima_de_processos = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
frequencia_minima_da_ligacao = int(sys.argv[4]) if len(sys.argv) > 4 else 2000

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
ligacoes, inicios, _ = pm4py.discover_dfg(log)
atividade_inicial = max(inicios, key=inicios.get)
ligacao_que_sai_do_inicio = max((ligacao for ligacao in ligacoes if ligacao[0] == atividade_inicial), key=ligacoes.get)
ligacoes_mantidas = {
    ligacao: frequencia for ligacao, frequencia in ligacoes.items()
    if frequencia >= frequencia_minima_da_ligacao or ligacao == ligacao_que_sai_do_inicio
}
atividades_nas_ligacoes = {atividade for ligacao in ligacoes_mantidas for atividade in ligacao}
sem_posicao = atividades_nas_ligacoes - set(POSICAO_NA_FIGURA)
if sem_posicao:
    raise SystemExit(f"Atividades sem posição na figura: {sorted(sem_posicao)}")
ocorrencias_por_atividade = eventos_filtrados["atividade"].value_counts().to_dict()


def numero_brasileiro(numero):
    return f"{numero:,}".replace(",", ".")


pyplot.rcParams.update({"font.family": "DejaVu Sans"})
limites_x, limites_y = (-0.1, 21.4), (-1.3, 11.0)
largura_em_polegadas = 6.3
altura_em_polegadas = largura_em_polegadas * (limites_y[1] - limites_y[0]) / (limites_x[1] - limites_x[0])
figura, eixo = pyplot.subplots(figsize=(largura_em_polegadas, altura_em_polegadas), dpi=300)
eixo.set_xlim(*limites_x)
eixo.set_ylim(*limites_y)
eixo.set_aspect("equal")
eixo.axis("off")

caixa_por_atividade = {}
for atividade in atividades_nas_ligacoes:
    x, y = POSICAO_NA_FIGURA[atividade]
    rotulo = f"{NOME_DE_LEITURA.get(atividade, atividade)}\n{numero_brasileiro(ocorrencias_por_atividade[atividade])}"
    altura = 0.75 + 0.48 * rotulo.count("\n")
    ato_do_juiz = atividade in NOME_DA_ATIVIDADE_POR_CATEGORIA.values()
    caixa = FancyBboxPatch(
        (x - LARGURA_DA_CAIXA / 2, y - altura / 2), LARGURA_DA_CAIXA, altura, boxstyle="round,pad=0,rounding_size=0.22",
        facecolor=COR_DA_SERIE if ato_do_juiz else COR_CLARA_DA_SERIE, edgecolor=COR_DA_SERIE, linewidth=0.9, zorder=3,
    )
    eixo.add_patch(caixa)
    eixo.text(x, y, rotulo, ha="center", va="center", fontsize=7, linespacing=1.15, color="white" if ato_do_juiz else COR_DO_TEXTO, zorder=4)
    caixa_por_atividade[atividade] = caixa

menor_frequencia, maior_frequencia = min(ligacoes_mantidas.values()), max(ligacoes_mantidas.values())


def espessura(frequencia):
    return 0.6 + 2.4 * (frequencia - menor_frequencia) / (maior_frequencia - menor_frequencia)


def escrever_numero(x, y, frequencia, lado="centro"):
    deslocamento, alinhamento = {"centro": (0, "center"), "direita": (0.25, "left"), "esquerda": (-0.25, "right")}[lado]
    eixo.text(
        x + deslocamento, y, numero_brasileiro(frequencia), ha=alinhamento, va="center",
        fontsize=6.3, color=COR_SECUNDARIA, zorder=5, bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none"},
    )


for (origem, destino), frequencia in sorted(ligacoes_mantidas.items(), key=lambda item: item[1]):
    x_origem, y_origem = POSICAO_NA_FIGURA[origem]
    if origem == destino:
        caixa = caixa_por_atividade[origem]
        meia_largura, meia_altura = LARGURA_DA_CAIXA / 2, caixa.get_height() / 2
        lado = LADO_DO_LACO[origem]
        if lado == "cima":
            inicio, fim, curvatura, posicao_do_numero = (x_origem - 0.35, y_origem + meia_altura), (x_origem + 0.35, y_origem + meia_altura), -2.2, (x_origem, y_origem + meia_altura + 0.95)
        elif lado == "baixo":
            inicio, fim, curvatura, posicao_do_numero = (x_origem - 0.35, y_origem - meia_altura), (x_origem + 0.35, y_origem - meia_altura), 2.2, (x_origem, y_origem - meia_altura - 0.95)
        elif lado == "esquerda":
            inicio, fim, curvatura, posicao_do_numero = (x_origem - meia_largura, y_origem - 0.2), (x_origem - meia_largura, y_origem + 0.2), -2.4, (x_origem - meia_largura - 0.95, y_origem)
        else:
            inicio, fim, curvatura, posicao_do_numero = (x_origem + meia_largura, y_origem + 0.2), (x_origem + meia_largura, y_origem - 0.2), -2.4, (x_origem + meia_largura + 0.95, y_origem)
        seta = FancyArrowPatch(inicio, fim, connectionstyle=f"arc3,rad={curvatura}", arrowstyle="-|>", mutation_scale=6,
                               linewidth=espessura(frequencia), color=COR_SECUNDARIA, shrinkA=0, shrinkB=0, zorder=2)
        eixo.add_patch(seta)
        escrever_numero(*posicao_do_numero, frequencia)
        continue
    x_destino, y_destino = POSICAO_NA_FIGURA[destino]
    curvatura = CURVATURA_DA_LIGACAO.get((origem, destino), 0.12 if (destino, origem) in ligacoes_mantidas else 0.0)
    seta = FancyArrowPatch(
        (x_origem, y_origem), (x_destino, y_destino), connectionstyle=f"arc3,rad={curvatura}", arrowstyle="-|>",
        mutation_scale=6 + 1.5 * espessura(frequencia), linewidth=espessura(frequencia), color=COR_SECUNDARIA,
        patchA=caixa_por_atividade[origem], patchB=caixa_por_atividade[destino], shrinkA=1, shrinkB=2, zorder=2,
    )
    eixo.add_patch(seta)
    diferenca_x, diferenca_y = x_destino - x_origem, y_destino - y_origem
    meio_x = (x_origem + x_destino) / 2 + 0.5 * curvatura * diferenca_y
    meio_y = (y_origem + y_destino) / 2 - 0.5 * curvatura * diferenca_x
    escrever_numero(meio_x, meio_y, frequencia, LADO_DO_NUMERO.get((origem, destino), "centro"))

caminho_da_figura.parent.mkdir(parents=True, exist_ok=True)
figura.savefig(caminho_da_figura, facecolor="white", bbox_inches="tight", pad_inches=0.04)
figura.savefig(caminho_da_figura.with_suffix(".svg"), facecolor="white", bbox_inches="tight", pad_inches=0.04)

print(f"Processos: {quantidade_de_processos}")
print(f"Atividades presentes em pelo menos {cobertura_minima_de_processos:.0%} dos processos: {len(atividades_mantidas)} de {processos_por_atividade.size}")
print(f"Atividades no desenho: {len(atividades_nas_ligacoes)}; ligações com pelo menos {frequencia_minima_da_ligacao} passagens, mais a que sai de {atividade_inicial}: {len(ligacoes_mantidas)} de {len(ligacoes)}")
for (origem, destino), frequencia in sorted(ligacoes_mantidas.items(), key=lambda item: -item[1]):
    print(f"  {frequencia:>6}  {origem} -> {destino}")
print(f"Figura: {caminho_da_figura}")
