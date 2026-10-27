import html
import sys
from pathlib import Path

caminho_do_bpmn = Path(sys.argv[1])
caminho_da_pagina = Path(sys.argv[2])
conteudo_do_bpmn = caminho_do_bpmn.read_text(encoding="utf-8")

pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Modelo normativo</title>
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.11.1/dist/assets/bpmn-js.css">
<style>
  html, body {{ margin: 0; background: #ffffff; }}
  #tela {{ width: 1300px; height: 560px; }}
  #situacao {{ font: 13px sans-serif; padding: 6px; }}
</style>
</head>
<body>
<div id="situacao">carregando...</div>
<div id="tela"></div>
<textarea id="modelo" hidden>{html.escape(conteudo_do_bpmn)}</textarea>
<script src="https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-viewer.production.min.js"></script>
<script>
  const visualizador = new BpmnJS({{
    container: "#tela",
    textRenderer: {{ defaultStyle: {{ fontSize: 14, fontFamily: "Arial, sans-serif" }}, externalStyle: {{ fontSize: 13, fontFamily: "Arial, sans-serif" }} }}
  }});
  async function exportarPng(escala) {{
    const {{ svg }} = await visualizador.saveSVG();
    const imagem = new Image();
    const carregada = new Promise(resolver => {{ imagem.onload = resolver; }});
    imagem.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svg)));
    await carregada;
    const tela = document.createElement("canvas");
    tela.width = imagem.width * escala;
    tela.height = imagem.height * escala;
    const contexto = tela.getContext("2d");
    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, tela.width, tela.height);
    contexto.drawImage(imagem, 0, 0, tela.width, tela.height);
    window.svgExportado = svg;
    window.pngExportado = tela.toDataURL("image/png");
    return {{ largura: tela.width, altura: tela.height, tamanho: window.pngExportado.length }};
  }}
  visualizador.importXML(document.getElementById("modelo").value)
    .then(resultado => {{
      visualizador.get("canvas").zoom("fit-viewport");
      document.getElementById("situacao").textContent = "ok; avisos: " + resultado.warnings.length;
      window.avisosDaImportacao = resultado.warnings.map(aviso => aviso.message);
    }})
    .catch(erro => {{ document.getElementById("situacao").textContent = "erro: " + erro.message; }});
  window.exportarPng = exportarPng;
</script>
</body>
</html>
"""
caminho_da_pagina.write_text(pagina, encoding="utf-8")
print(f"Página gravada em {caminho_da_pagina}")
