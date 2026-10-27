import base64
import functools
import http.server
import json
import sys
from pathlib import Path

pasta_servida = Path(sys.argv[1])
pasta_das_figuras = Path(sys.argv[2])
porta = int(sys.argv[3])
NOMES_PERMITIDOS = {"modelo_normativo_bpmn.png", "modelo_normativo_bpmn.svg"}


class TratadorDoModelo(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/salvar":
            self.send_error(404)
            return
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        nome = corpo["nome"]
        if nome not in NOMES_PERMITIDOS:
            self.send_error(400, "nome não permitido")
            return
        conteudo = corpo["conteudo"]
        destino = pasta_das_figuras / nome
        if conteudo.startswith("data:image/png;base64,"):
            destino.write_bytes(base64.b64decode(conteudo.split(",", 1)[1]))
        else:
            destino.write_text(conteudo, encoding="utf-8")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"gravado": str(destino), "bytes": destino.stat().st_size}).encode("utf-8"))


servidor = http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(TratadorDoModelo, directory=str(pasta_servida)))
servidor.serve_forever()
