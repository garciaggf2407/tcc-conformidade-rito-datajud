import argparse
import calendar
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDERECO_DA_API = "https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
NOME_DA_VARIAVEL_DA_CHAVE = "DATAJUD_API_KEY"
COLUNAS_DO_LOG_DE_EVENTOS = [
    "numero_processo",
    "tribunal",
    "classe_codigo",
    "classe_nome",
    "grau",
    "orgao_julgador_codigo",
    "orgao_julgador_nome",
    "data_ajuizamento",
    "nivel_sigilo",
    "movimento_codigo",
    "movimento_nome",
    "movimento_data_hora",
    "complementos",
]


def ler_chave_gravada_no_usuario_do_windows():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as chave_do_registro:
            valor, _ = winreg.QueryValueEx(chave_do_registro, NOME_DA_VARIAVEL_DA_CHAVE)
            return str(valor)
    except (ImportError, OSError):
        return ""


def ler_chave_da_variavel_de_ambiente():
    candidatas = [os.environ.get(NOME_DA_VARIAVEL_DA_CHAVE, "").strip(), ler_chave_gravada_no_usuario_do_windows().strip()]
    chaves_validas = [candidata for candidata in candidatas if candidata and candidata != "cole-a-chave-aqui"]
    chave = chaves_validas[0] if chaves_validas else next((candidata for candidata in candidatas if candidata), "")
    if not chave:
        print(
            f"A variável de ambiente {NOME_DA_VARIAVEL_DA_CHAVE} não está definida.\n"
            "Copie a chave pública na página oficial do CNJ (datajud-wiki.cnj.jus.br > API Pública > Acesso)\n"
            "e grave no seu usuário do Windows com:\n"
            f'  setx {NOME_DA_VARIAVEL_DA_CHAVE} "a-chave-copiada"',
            file=sys.stderr,
        )
        sys.exit(2)
    if chave == "cole-a-chave-aqui":
        print(
            f"A variável {NOME_DA_VARIAVEL_DA_CHAVE} está com o texto de exemplo, não com a chave.\n"
            "Rode o setx de novo trocando o texto pela chave copiada da página do CNJ.",
            file=sys.stderr,
        )
        sys.exit(2)
    for prefixo in ("APIKey ", "ApiKey ", "apikey "):
        if chave.startswith(prefixo):
            chave = chave[len(prefixo):].strip()
    return chave


def montar_filtros(argumentos, ajuizados_de, ajuizados_ate):
    filtros = [
        {"match": {"classe.codigo": argumentos.classe}},
        {"match": {"grau": argumentos.grau}},
    ]
    if ajuizados_de or ajuizados_ate:
        intervalo = {}
        if ajuizados_de:
            intervalo["gte"] = ajuizados_de
        if ajuizados_ate:
            intervalo["lte"] = ajuizados_ate
        filtros.append({"range": {"dataAjuizamento": intervalo}})
    return filtros


def montar_consulta(argumentos, tamanho_da_pagina, ultimo_valor_de_ordenacao):
    consulta = {
        "size": tamanho_da_pagina,
        "query": {"bool": {"filter": montar_filtros(argumentos, argumentos.ajuizados_de, argumentos.ajuizados_ate)}},
        "sort": [{"@timestamp": {"order": "asc"}}],
    }
    if ultimo_valor_de_ordenacao is not None:
        consulta["search_after"] = ultimo_valor_de_ordenacao
    return consulta


def montar_consulta_sorteada(argumentos, primeiro_dia, ultimo_dia, posicao_inicial, tamanho_da_pagina):
    return {
        "from": posicao_inicial,
        "size": tamanho_da_pagina,
        "query": {
            "function_score": {
                "query": {"bool": {"filter": montar_filtros(argumentos, primeiro_dia, ultimo_dia)}},
                "random_score": {"seed": argumentos.semente, "field": "_seq_no"},
                "boost_mode": "replace",
            }
        },
    }


def listar_meses(data_inicial, data_final):
    ano, mes = int(data_inicial[:4]), int(data_inicial[5:7])
    ano_final, mes_final = int(data_final[:4]), int(data_final[5:7])
    while (ano, mes) <= (ano_final, mes_final):
        ultimo_dia_do_mes = calendar.monthrange(ano, mes)[1]
        yield f"{ano:04d}-{mes:02d}-01", f"{ano:04d}-{mes:02d}-{ultimo_dia_do_mes:02d}"
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def enviar_consulta(endereco, chave, consulta, tentativas_maximas=5):
    corpo = json.dumps(consulta).encode("utf-8")
    for tentativa in range(1, tentativas_maximas + 1):
        requisicao = urllib.request.Request(
            endereco,
            data=corpo,
            method="POST",
            headers={"Authorization": f"APIKey {chave}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=180) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            if erro.code in (401, 403):
                print("A API recusou a chave (HTTP %d). Confira se copiou a chave pública inteira." % erro.code, file=sys.stderr)
                sys.exit(3)
            if erro.code in (429, 500, 502, 503, 504) and tentativa < tentativas_maximas:
                espera_em_segundos = (30 if erro.code == 429 else 15) * tentativa
                print(f"HTTP {erro.code}; nova tentativa em {espera_em_segundos}s...", file=sys.stderr)
                time.sleep(espera_em_segundos)
                continue
            detalhe = erro.read().decode("utf-8", errors="replace")[:500]
            print(f"Erro HTTP {erro.code}: {detalhe}", file=sys.stderr)
            sys.exit(4)
        except (urllib.error.URLError, TimeoutError) as erro:
            if tentativa < tentativas_maximas:
                espera_em_segundos = 5 * tentativa
                print(f"Falha de conexão ({erro}); nova tentativa em {espera_em_segundos}s...", file=sys.stderr)
                time.sleep(espera_em_segundos)
                continue
            print(f"Falha de conexão: {erro}", file=sys.stderr)
            sys.exit(5)


def converter_processo_em_eventos(processo):
    classe = processo.get("classe") or {}
    orgao_julgador = processo.get("orgaoJulgador") or {}
    for movimento in processo.get("movimentos") or []:
        complementos = movimento.get("complementosTabelados") or []
        yield {
            "numero_processo": processo.get("numeroProcesso"),
            "tribunal": processo.get("tribunal"),
            "classe_codigo": classe.get("codigo"),
            "classe_nome": classe.get("nome"),
            "grau": processo.get("grau"),
            "orgao_julgador_codigo": orgao_julgador.get("codigo"),
            "orgao_julgador_nome": orgao_julgador.get("nome"),
            "data_ajuizamento": processo.get("dataAjuizamento"),
            "nivel_sigilo": processo.get("nivelSigilo"),
            "movimento_codigo": movimento.get("codigo"),
            "movimento_nome": movimento.get("nome"),
            "movimento_data_hora": movimento.get("dataHora"),
            "complementos": " | ".join(
                f"{complemento.get('descricao')}={complemento.get('nome')}" for complemento in complementos
            ),
        }


def principal():
    leitor_de_argumentos = argparse.ArgumentParser(
        description="Baixa uma amostra de processos da API pública do DataJud e grava um log de eventos (um movimento por linha)."
    )
    leitor_de_argumentos.add_argument("--tribunal", default="tjsp", help="sigla do tribunal no endereço da API, ex.: tjsp, tjmg, trf1")
    leitor_de_argumentos.add_argument("--classe", type=int, default=7, help="código TPU da classe processual (7 = Procedimento Comum Cível)")
    leitor_de_argumentos.add_argument("--grau", default="G1", help="grau de jurisdição: G1, G2, JE...")
    leitor_de_argumentos.add_argument("--ajuizados-de", default="2022-01-01", help="data mínima de ajuizamento (AAAA-MM-DD); vazio para não filtrar")
    leitor_de_argumentos.add_argument("--ajuizados-ate", default="2022-12-31", help="data máxima de ajuizamento (AAAA-MM-DD); vazio para não filtrar")
    leitor_de_argumentos.add_argument("--quantidade", type=int, default=500, help="quantos processos baixar")
    leitor_de_argumentos.add_argument("--pagina", type=int, default=100, help="processos por requisição (até 10000)")
    leitor_de_argumentos.add_argument("--saida", default=r"D:\TCC\dados", help="pasta onde gravar os arquivos")
    leitor_de_argumentos.add_argument("--sorteio-por-mes", type=int, default=0, help="sorteia esta quantidade de processos por mês de ajuizamento, em vez de seguir a ordem do índice (0 = não sortear)")
    leitor_de_argumentos.add_argument("--semente", type=int, default=2026, help="semente do sorteio, para que ele possa ser repetido")
    argumentos = leitor_de_argumentos.parse_args()
    if argumentos.sorteio_por_mes and not (argumentos.ajuizados_de and argumentos.ajuizados_ate):
        leitor_de_argumentos.error("o sorteio por mês exige --ajuizados-de e --ajuizados-ate")

    chave = ler_chave_da_variavel_de_ambiente()
    endereco = ENDERECO_DA_API.format(tribunal=argumentos.tribunal.lower())
    pasta_de_saida = Path(argumentos.saida)
    pasta_de_saida.mkdir(parents=True, exist_ok=True)
    nome_base = (
        f"datajud_{argumentos.tribunal.lower()}_classe{argumentos.classe}_{argumentos.grau}"
        f"_{argumentos.ajuizados_de or 'inicio'}_{argumentos.ajuizados_ate or 'fim'}"
    )
    if argumentos.sorteio_por_mes:
        nome_base += f"_sorteio{argumentos.sorteio_por_mes}pormes_semente{argumentos.semente}"
    caminho_dos_processos = pasta_de_saida / f"{nome_base}_processos.jsonl"
    caminho_do_log_de_eventos = pasta_de_saida / f"{nome_base}_eventos.csv"

    processos_gravados = 0
    eventos_gravados = 0
    codigos_de_movimento_distintos = set()
    processos_com_conclusao = 0
    total_informado_pela_api = None
    ultimo_valor_de_ordenacao = None

    with open(caminho_dos_processos, "w", encoding="utf-8") as arquivo_de_processos, open(
        caminho_do_log_de_eventos, "w", encoding="utf-8", newline=""
    ) as arquivo_de_eventos:
        escritor_de_eventos = csv.DictWriter(arquivo_de_eventos, fieldnames=COLUNAS_DO_LOG_DE_EVENTOS)
        escritor_de_eventos.writeheader()

        def gravar_documentos(documentos):
            nonlocal processos_gravados, eventos_gravados, codigos_de_movimento_distintos, processos_com_conclusao
            for documento in documentos:
                processo = documento.get("_source") or {}
                arquivo_de_processos.write(json.dumps(processo, ensure_ascii=False) + "\n")
                processos_gravados += 1
                codigos_deste_processo = set()
                for evento in converter_processo_em_eventos(processo):
                    escritor_de_eventos.writerow(evento)
                    eventos_gravados += 1
                    codigos_deste_processo.add(evento["movimento_codigo"])
                codigos_de_movimento_distintos |= codigos_deste_processo
                if 51 in codigos_deste_processo:
                    processos_com_conclusao += 1

        if argumentos.sorteio_por_mes:
            pasta_dos_meses = pasta_de_saida / f"{nome_base}_meses"
            pasta_dos_meses.mkdir(exist_ok=True)
            endereco_do_sorteio = f"{endereco}?preference=sorteio-semente-{argumentos.semente}"
            for primeiro_dia, ultimo_dia in listar_meses(argumentos.ajuizados_de, argumentos.ajuizados_ate):
                caminho_do_mes = pasta_dos_meses / f"{primeiro_dia[:7]}.json"
                documentos_ja_baixados = json.loads(caminho_do_mes.read_text(encoding="utf-8")) if caminho_do_mes.exists() else []
                posicao_no_sorteio = len(documentos_ja_baixados)
                documentos = []
                numeros_ja_vistos = set()
                for documento in documentos_ja_baixados:
                    numero = (documento.get("_source") or {}).get("numeroProcesso")
                    if numero not in numeros_ja_vistos:
                        numeros_ja_vistos.add(numero)
                        documentos.append(documento)
                paginas_vazias_seguidas = 0
                baixados_agora = 0
                while len(documentos) < argumentos.sorteio_por_mes and paginas_vazias_seguidas < 3:
                    consulta = montar_consulta_sorteada(argumentos, primeiro_dia, ultimo_dia, posicao_no_sorteio, argumentos.pagina)
                    pagina = (enviar_consulta(endereco_do_sorteio, chave, consulta, tentativas_maximas=8).get("hits") or {}).get("hits") or []
                    if not pagina:
                        paginas_vazias_seguidas += 1
                        time.sleep(30)
                        continue
                    paginas_vazias_seguidas = 0
                    posicao_no_sorteio += len(pagina)
                    for documento in pagina:
                        numero = (documento.get("_source") or {}).get("numeroProcesso")
                        if numero not in numeros_ja_vistos and len(documentos) < argumentos.sorteio_por_mes:
                            numeros_ja_vistos.add(numero)
                            documentos.append(documento)
                            baixados_agora += 1
                    caminho_do_mes.write_text(json.dumps(documentos, ensure_ascii=False), encoding="utf-8")
                    time.sleep(2)
                if len(documentos) < argumentos.sorteio_por_mes:
                    print(f"{primeiro_dia[:7]}: só {len(documentos)} distintos depois de 3 páginas vazias; rode de novo para completar.", file=sys.stderr)
                    sys.exit(7)
                gravar_documentos(documentos)
                print(f"{primeiro_dia[:7]}: {len(documentos)} distintos ({baixados_agora} baixados agora); {processos_gravados} no total")
        else:
            while processos_gravados < argumentos.quantidade:
                tamanho_da_pagina = min(argumentos.pagina, argumentos.quantidade - processos_gravados)
                consulta = montar_consulta(argumentos, tamanho_da_pagina, ultimo_valor_de_ordenacao)
                resposta = enviar_consulta(endereco, chave, consulta)
                resultados = resposta.get("hits", {})
                if total_informado_pela_api is None:
                    total_informado_pela_api = (resultados.get("total") or {}).get("value")
                    relacao = (resultados.get("total") or {}).get("relation")
                    print(f"A API informa {total_informado_pela_api} processos ({relacao}) para este filtro.")
                documentos = resultados.get("hits") or []
                if not documentos:
                    break
                gravar_documentos(documentos)
                ultimo_valor_de_ordenacao = documentos[-1].get("sort")
                print(f"{processos_gravados} processos baixados...")
                if ultimo_valor_de_ordenacao is None:
                    break

    if processos_gravados == 0:
        print(
            "Nenhum processo veio. Se o total informado foi 0, tente sem o filtro de data:\n"
            '  --ajuizados-de "" --ajuizados-ate ""',
            file=sys.stderr,
        )
        sys.exit(6)

    print()
    print(f"Processos gravados:             {processos_gravados}")
    print(f"Movimentos (eventos) gravados:  {eventos_gravados}")
    print(f"Códigos de movimento distintos: {len(codigos_de_movimento_distintos)}")
    print(f"Processos com Conclusão (51):   {processos_com_conclusao}")
    print(f"Processos: {caminho_dos_processos}")
    print(f"Log de eventos: {caminho_do_log_de_eventos}")


if __name__ == "__main__":
    principal()
