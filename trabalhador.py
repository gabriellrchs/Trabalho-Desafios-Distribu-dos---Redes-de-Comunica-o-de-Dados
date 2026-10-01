import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
from llm import PROMPTS, estimar_proximo
from rede import Conexao, cliente_mqtt, tls_cliente, tls_servidor


class Trabalhador:
    """Recebe tarefas pelos tres protocolos. Todas passam por tratar_mensagem()."""

    def __init__(self, nome, perfil):
        self.nome = nome
        self.perfil = perfil
        self.moedas = 0
        self.conexao = None

    # ---------------- logica (igual para todos os protocolos) ----------------

    def tratar_mensagem(self, mensagem):
        """Recebe TAREFA ou RESULTADO. Devolve a RESPOSTA (no caso de TAREFA) ou None."""
        if mensagem["tipo"] == "TAREFA":
            return self.resolver(mensagem)
        if mensagem["tipo"] == "RESULTADO":
            self.ver_resultado(mensagem)
        return None

    def resolver(self, tarefa):
        print(f"\n[{tarefa['protocolo']}] Tarefa {tarefa['tarefa']}: {tarefa['serie']}")
        inicio = time.perf_counter()
        valor = estimar_proximo(tarefa["serie"], self.perfil)
        tempo_llm = (time.perf_counter() - inicio) * 1000

        if valor is None:
            print("Sem resposta do LLM")
            return None
        print(f"Respondi {valor} ({tempo_llm:.0f} ms)")
        return {"tipo": "RESPOSTA", "nome": self.nome, "tarefa": tarefa["tarefa"],
                "valor": valor, "tempo_llm": tempo_llm}

    def ver_resultado(self, resultado):
        print(f"Vencedor: {resultado['vencedor']} | votos: {resultado['votos']}")
        if resultado["vencedor"] == self.nome:
            self.moedas += resultado["premio"]
            print(f"Ganhei! Total: {self.moedas} Pfitscher Coins")

    # ---------------- sockets ----------------

    def conectar(self, host):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, config.PORTA))
        self.conexao = Conexao(tls_cliente(sock))

    def registrar(self, porta_http):
        self.conexao.enviar({"tipo": "REGISTRO", "nome": self.nome, "senha": config.SENHA,
                             "perfil": self.perfil, "porta_http": porta_http})
        resposta = self.conexao.receber()
        return resposta is not None and resposta["aceito"]

    def ouvir_socket(self):
        while True:
            mensagem = self.conexao.receber()
            if mensagem is None:
                break
            resposta = self.tratar_mensagem(mensagem)
            if resposta:
                self.conexao.enviar(resposta)

    # ---------------- HTTP ----------------

    def iniciar_http(self):
        """Sobe um servidor HTTP(S) numa porta livre. O orquestrador manda as tarefas por POST."""
        trabalhador = self

        class Requisicao(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"   # mantem a conexao aberta entre as tarefas
            disable_nagle_algorithm = True  # envia a resposta na hora, sem esperar juntar mais dados

            def do_POST(self):
                tamanho = int(self.headers["Content-Length"])
                mensagem = json.loads(self.rfile.read(tamanho))
                resposta = trabalhador.tratar_mensagem(mensagem) or {}
                corpo = json.dumps(resposta).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *args):
                pass  # nao imprime cada requisicao

        servidor = ThreadingHTTPServer(("", 0), Requisicao)   # porta 0 = o sistema escolhe uma livre
        servidor.socket = tls_servidor(servidor.socket)
        servidor.handle_error = lambda *args: None   # ignora o erro quando o orquestrador fecha a conexao
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        return servidor.server_address[1]

    # ---------------- MQTT ----------------

    def iniciar_mqtt(self):
        cliente = cliente_mqtt(self.nome)

        def ao_receber(cliente, dados, mensagem_mqtt):
            resposta = self.tratar_mensagem(json.loads(mensagem_mqtt.payload))
            if resposta:
                cliente.publish(config.TOPICO_RESPOSTAS, json.dumps(resposta))

        cliente.on_message = ao_receber
        cliente.subscribe(config.TOPICO_TAREFAS)
        cliente.loop_start()   # recebe as mensagens em segundo plano


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[2] not in PROMPTS:
        print("Uso: python trabalhador.py <nome> <perfil> [ip do orquestrador]")
        print("Perfis:", ", ".join(PROMPTS))
        sys.exit()

    host = sys.argv[3] if len(sys.argv) > 3 else config.HOST
    trabalhador = Trabalhador(sys.argv[1], sys.argv[2])

    porta_http = trabalhador.iniciar_http()
    if "mqtt" in config.PROTOCOLOS:
        trabalhador.iniciar_mqtt()
    trabalhador.conectar(host)

    if trabalhador.registrar(porta_http):
        print(f"Registrado (HTTP na porta {porta_http}). Aguardando tarefas...")
        trabalhador.ouvir_socket()
    else:
        print("Registro recusado")
    trabalhador.conexao.fechar()
