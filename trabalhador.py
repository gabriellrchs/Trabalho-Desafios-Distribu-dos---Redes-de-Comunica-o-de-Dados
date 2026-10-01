import socket
import sys
import time

import config
from llm import PROMPTS, estimar_proximo
from rede import Conexao, tls_cliente


class Trabalhador:

    def __init__(self, nome, perfil):
        self.nome = nome
        self.perfil = perfil
        self.moedas = 0
        self.conexao = None

    def conectar(self, host):
        inicio = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, config.PORTA))
        self.conexao = Conexao(tls_cliente(sock))
        tempo = (time.perf_counter() - inicio) * 1000
        print(f"Conectado em {tempo:.1f} ms (TLS: {config.USAR_TLS})")

    def registrar(self):
        self.conexao.enviar({"tipo": "REGISTRO", "nome": self.nome, "senha": config.SENHA, "perfil": self.perfil})
        resposta = self.conexao.receber()
        return resposta is not None and resposta["aceito"]

    def trabalhar(self):
        while True:
            mensagem = self.conexao.receber()
            if mensagem is None:
                break
            if mensagem["tipo"] == "TAREFA":
                self.resolver(mensagem)
            elif mensagem["tipo"] == "RESULTADO":
                self.ver_resultado(mensagem)

    def resolver(self, tarefa):
        print(f"\nTarefa {tarefa['tarefa']}: {tarefa['serie']}")
        inicio = time.perf_counter()
        valor = estimar_proximo(tarefa["serie"], self.perfil)
        tempo_llm = (time.perf_counter() - inicio) * 1000

        if valor is None:
            print("Sem resposta do LLM")
            return
        print(f"Respondi {valor} ({tempo_llm:.0f} ms)")
        self.conexao.enviar({"tipo": "RESPOSTA", "tarefa": tarefa["tarefa"], "valor": valor, "tempo_llm": tempo_llm})

    def ver_resultado(self, resultado):
        print(f"Vencedor: {resultado['vencedor']} | votos: {resultado['votos']}")
        if resultado["vencedor"] == self.nome:
            self.moedas += resultado["premio"]
            print(f"Ganhei! Total: {self.moedas} Pfitscher Coins")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[2] not in PROMPTS:
        print("Uso: python trabalhador.py <nome> <perfil> [ip do orquestrador]")
        print("Perfis:", ", ".join(PROMPTS))
        sys.exit()

    host = sys.argv[3] if len(sys.argv) > 3 else config.HOST
    trabalhador = Trabalhador(sys.argv[1], sys.argv[2])
    trabalhador.conectar(host)

    if trabalhador.registrar():
        print("Registrado. Aguardando tarefas...")
        trabalhador.trabalhar()
    else:
        print("Registro recusado")
    trabalhador.conexao.fechar()
