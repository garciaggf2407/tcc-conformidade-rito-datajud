import contextlib
import io
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as pyplot

caminho_do_log_de_eventos = sys.argv[1]
pasta_das_figuras = Path(sys.argv[2])
pasta_das_figuras.mkdir(parents=True, exist_ok=True)

sys.argv = ["", caminho_do_log_de_eventos]
sys.path.insert(0, str(Path(__file__).parent))
with contextlib.redirect_stdout(io.StringIO()):
    import medir_prazos_do_juiz as medicao
from classificacao_de_atos_do_juiz import CATEGORIA_POR_CODIGO, CODIGO_CONCLUSAO, PRAZO_LEGAL_EM_DIAS

COR_DA_SERIE = "#2a78d6"
COR_DO_TEXTO = "#0b0b0b"
COR_SECUNDARIA = "#52514e"
COR_DA_GRADE = "#e4e3df"
NOME_DA_CATEGORIA = {"despacho": "Despacho", "decisao": "Decisão", "sentenca": "Sentença", "embargos_de_declaracao": "Embargos de\ndeclaração"}

pyplot.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": COR_SECUNDARIA, "axes.labelcolor": COR_DO_TEXTO,
    "xtick.color": COR_SECUNDARIA, "ytick.color": COR_SECUNDARIA, "axes.spines.top": False, "axes.spines.right": False,
})

eventos_por_processo = {numero: sorted(eventos) for numero, eventos in medicao.eventos_por_processo.items()}

o_que_vem_depois_da_conclusao_sem_ato = Counter()
for eventos in eventos_por_processo.values():
    for posicao, (_, codigo) in enumerate(eventos):
        if codigo != CODIGO_CONCLUSAO:
            continue
        seguintes = eventos[posicao + 1:]
        teve_ato = False
        for _, codigo_seguinte in seguintes:
            if codigo_seguinte == CODIGO_CONCLUSAO:
                break
            if codigo_seguinte in CATEGORIA_POR_CODIGO:
                teve_ato = True
                break
        if teve_ato:
            continue
        if not seguintes:
            o_que_vem_depois_da_conclusao_sem_ato["fim dos dados"] += 1
        elif seguintes[0][1] == CODIGO_CONCLUSAO:
            o_que_vem_depois_da_conclusao_sem_ato["outra Conclusão em seguida"] += 1
        else:
            o_que_vem_depois_da_conclusao_sem_ato["outro movimento e depois nova Conclusão ou fim"] += 1

dias_ate_a_primeira_sentenca = []
for eventos in eventos_por_processo.values():
    data_inicial = eventos[0][0]
    primeira_sentenca = next((data for data, codigo in eventos if CATEGORIA_POR_CODIGO.get(codigo) == "sentenca"), None)
    if primeira_sentenca is not None:
        dias_ate_a_primeira_sentenca.append((primeira_sentenca - data_inicial).days)
dias_ate_a_primeira_sentenca.sort()

unidades_com_pelo_menos_30_atos = {}
for categoria, medicoes in medicao.medicoes_por_categoria.items():
    unidades = Counter()
    for numero_processo, _, _ in medicoes:
        unidades[numero_processo[-4:]] += 1
    unidades_com_pelo_menos_30_atos[categoria] = sum(1 for quantidade in unidades.values() if quantidade >= 30)

print("Conclusões sem ato do juiz, pelo que vem depois:")
for desfecho, quantidade in o_que_vem_depois_da_conclusao_sem_ato.most_common():
    print(f"  {quantidade:>5}  {desfecho}")
print(f"Processos com sentença até o fim dos dados: {len(dias_ate_a_primeira_sentenca)} de {len(eventos_por_processo)}")
print(f"Dias corridos da distribuição à primeira sentença: mediana {dias_ate_a_primeira_sentenca[len(dias_ate_a_primeira_sentenca) // 2]}, "
      f"quartis {dias_ate_a_primeira_sentenca[len(dias_ate_a_primeira_sentenca) // 4]} e {dias_ate_a_primeira_sentenca[3 * len(dias_ate_a_primeira_sentenca) // 4]}")
print(f"Comarcas com pelo menos 30 atos do tipo: {unidades_com_pelo_menos_30_atos}")

dias_uteis_das_sentencas = [dias_uteis for _, _, dias_uteis in medicao.medicoes_por_categoria["sentenca"]]
limite_do_eixo = 120
acima_do_limite = sum(1 for dias in dias_uteis_das_sentencas if dias > limite_do_eixo)
figura, eixo = pyplot.subplots(figsize=(6.3, 3.4), dpi=300)
eixo.hist([min(dias, limite_do_eixo + 2) for dias in dias_uteis_das_sentencas], bins=range(0, limite_do_eixo + 5, 5), color=COR_DA_SERIE, edgecolor="white", linewidth=0.8)
eixo.axvline(PRAZO_LEGAL_EM_DIAS["sentenca"], color=COR_DO_TEXTO, linestyle=(0, (4, 3)), linewidth=1)
eixo.text(PRAZO_LEGAL_EM_DIAS["sentenca"] + 2, eixo.get_ylim()[1] * 0.92, "prazo legal: 30 dias úteis", color=COR_DO_TEXTO, fontsize=9)
eixo.set_xlabel("Dias úteis entre a Conclusão e a sentença")
eixo.set_ylabel("Número de sentenças")
eixo.set_xlim(0, limite_do_eixo + 5)
eixo.grid(axis="y", color=COR_DA_GRADE, linewidth=0.6)
eixo.set_axisbelow(True)
eixo.text(limite_do_eixo + 4, eixo.get_ylim()[1] * 0.05, f"{acima_do_limite} acima\nde {limite_do_eixo}", ha="right", color=COR_SECUNDARIA, fontsize=8)
figura.tight_layout()
figura.savefig(pasta_das_figuras / "sentencas_dias_uteis.png")

categorias = ["despacho", "decisao", "sentenca", "embargos_de_declaracao"]
proporcoes, erros_abaixo, erros_acima = [], [], []
for categoria in categorias:
    medicoes = medicao.medicoes_por_categoria[categoria]
    prazo = PRAZO_LEGAL_EM_DIAS[categoria]
    proporcao = medicao.proporcao_acima_do_prazo(medicoes, prazo)
    limite_inferior, limite_superior = medicao.intervalo_de_confianca_por_processo(medicoes, prazo)
    proporcoes.append(100 * proporcao)
    erros_abaixo.append(100 * (proporcao - limite_inferior))
    erros_acima.append(100 * (limite_superior - proporcao))
figura, eixo = pyplot.subplots(figsize=(6.3, 3.2), dpi=300)
posicoes = range(len(categorias))
eixo.bar(posicoes, proporcoes, width=0.55, color=COR_DA_SERIE)
eixo.errorbar(posicoes, proporcoes, yerr=[erros_abaixo, erros_acima], fmt="none", ecolor=COR_DO_TEXTO, elinewidth=1, capsize=4)
for posicao, proporcao, erro in zip(posicoes, proporcoes, erros_acima):
    eixo.text(posicao, proporcao + erro + 1, f"{proporcao:.1f}%".replace(".", ","), ha="center", color=COR_DO_TEXTO, fontsize=9)
eixo.set_xticks(list(posicoes), [f"{NOME_DA_CATEGORIA[categoria]}\n(prazo {PRAZO_LEGAL_EM_DIAS[categoria]} dias)" for categoria in categorias])
eixo.set_ylabel("Atos acima do prazo (%)")
eixo.set_ylim(0, max(proporcoes) + max(erros_acima) + 8)
eixo.grid(axis="y", color=COR_DA_GRADE, linewidth=0.6)
eixo.set_axisbelow(True)
figura.tight_layout()
figura.savefig(pasta_das_figuras / "atos_acima_do_prazo.png")
print(f"Figuras gravadas em {pasta_das_figuras}")
