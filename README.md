# Conformidade entre o rito legal e a tramitação real

Scripts, modelo e resultados do artigo *Conformidade entre o rito legal e a tramitação real: mineração de processos sobre dados abertos do Poder Judiciário*.

O trabalho modela em BPMN o rito do procedimento comum do Código de Processo Civil, a partir da lei, e o compara com a tramitação de 2.390 processos do Tribunal de Justiça de São Paulo (primeiro grau, Procedimento Comum Cível, ajuizados em 2022), obtida pela API pública do DataJud. Mede também os prazos do juiz (art. 226) e o prazo de remessa dos autos conclusos (art. 228) em dias úteis.

## O que está aqui

| pasta | conteúdo |
|---|---|
| `scripts/` | coleta, tratamento, medições e figuras |
| `modelo/` | o modelo normativo: `modelo_normativo.bpmn`, gerado a partir da árvore de processo usada no cálculo, e `modelo_normativo_leitura.bpmn`, a versão desenhada para leitura (Figura 2) |
| `resultados/` | as saídas dos scripts, com os números citados no artigo |
| `figuras/` | as figuras do artigo e dois gráficos dos prazos que ficaram fora dele |
| `dados/tpu/` | a classificação dos movimentos pela tabela oficial da TPU, usada pelos scripts |

## O que não está aqui

Os registros coletados ficam fora, porque o Termo de Uso da API pública do DataJud proíbe distribuir a API ou informação derivada dela (item 3.8). Quem quiser os dados roda a coleta de novo, como descrito abaixo. A chave de acesso à API também fica fora: é pública, e cada usuário a copia da página do CNJ.

A coleta usada no artigo foi feita em 26/10/2026. O sorteio usa semente fixa, mas a base é atualizada pelos tribunais, e uma coleta feita em outra data pode trazer outra amostra.

## Como reproduzir

Requisitos: Python 3.12, as bibliotecas de `requirements.txt` e o [Graphviz](https://graphviz.org/) instalado. Os scripts procuram o Graphviz em `C:\Program Files\Graphviz\bin`.

```bash
python -m pip install -r requirements.txt
```

A chave pública da API está em [Datajud-Wiki > API Pública > Acesso](https://datajud-wiki.cnj.jus.br/api-publica/acesso). No Windows, grave-a na variável `DATAJUD_API_KEY`:

```bash
setx DATAJUD_API_KEY "a-chave-copiada"
```

Rode os scripts com `python -X utf8`, para que os arquivos de resultado saiam em UTF-8. Na ordem:

| passo | comando | o que produz |
|---|---|---|
| 1. coleta | `python -X utf8 scripts/baixar_amostra_datajud.py --sorteio-por-mes 200 --semente 2026 --pagina 50 --saida dados` | `dados/datajud_tjsp_classe7_G1_2022-01-01_2022-12-31_sorteio200pormes_semente2026_eventos.csv` e o `.jsonl` dos processos. Com a API respondendo 429 e 504, a coleta leva cerca de 2 horas; o script grava cada mês em disco e retoma de onde parou |
| 2. prazos do juiz | `python -X utf8 scripts/medir_prazos_do_juiz.py LOG` | Tabela 1 |
| 3. figuras dos prazos | `python -X utf8 scripts/gerar_resultados.py LOG figuras` | os gráficos dos prazos (`atos_acima_do_prazo.png` e `sentencas_dias_uteis.png`, fora do artigo) e os números da seção 4.1 |
| 4. fluxo descoberto | `python -X utf8 scripts/descobrir_fluxo.py LOG figuras/fluxo_descoberto_amostra_final.png 0.2 2000` | Figura 1 (atividades em pelo menos 20% dos processos, ligações com pelo menos 2.000 passagens) |
| 5. tempos do fluxo | `python -X utf8 scripts/medir_tempos_do_fluxo.py LOG 0.2 500` | tempos medianos da seção 4.2 |
| 6. remessa dos autos | `python -X utf8 scripts/medir_remessa_dos_autos_conclusos.py LOG` | prazo do art. 228, seção 4.3 |
| 7. comarcas | `python -X utf8 scripts/medir_sentencas_por_comarca.py LOG` | Tabela 2 |
| 8. conformidade | `python -X utf8 scripts/conformidade_com_o_rito.py LOG modelo` | Tabela 3 e seção 4.6 |
| 9. Discussão | `python -X utf8 scripts/medir_numeros_da_discussao.py LOG modelo/log_do_rito.csv` | números da seção 5 |

`LOG` é o arquivo de eventos gerado no passo 1.

A tabela da TPU em `dados/tpu/` pode ser refeita com o download oficial (`https://gateway.cloud.pje.jus.br/tpu/api/v1/publico/download/movimentos`) e `python -X utf8 scripts/classificar_pela_tpu.py tpu_movimentos.json dados/tpu/tpu_classificacao.csv`.

A Figura 2 é desenhada com o bpmn-js a partir de `modelo_normativo_leitura.bpmn`:

```bash
python -X utf8 scripts/montar_pagina_do_bpmn.py modelo/modelo_normativo_leitura.bpmn modelo/visualizar_modelo.html
```

```bash
python -X utf8 scripts/servidor_do_modelo.py modelo figuras 4321
```

Depois abra `http://localhost:4321/visualizar_modelo.html` no navegador; a página grava o PNG e o SVG em `figuras/`.
