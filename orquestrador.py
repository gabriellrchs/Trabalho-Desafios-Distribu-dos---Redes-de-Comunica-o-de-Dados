import csv
import json
import os
import random
import socket
import threading
import time

import config
from rede import Conexao, tls_servidor


class Orquestrador:

    def __init__(self):
        self.trabalhadores = {}   # nome -> Conexao
        self.respostas = []       # (nome, valor), na ordem em que chegaram
        self.tarefa = 0
        self.inicio_tarefa = 0
        self.medicoes = []
        self.saldos = self.carregar_saldos()
        self.trava = threading.Lock()

    # ---------------- conexoes ----------------

    def iniciar(self):
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind(("", config.PORTA))
        servidor.listen(5)
        print(f"Orquestrador na porta {config.PORTA} (TLS: {config.USAR_TLS})")
        threading.Thread(target=self.aceitar_conexoes, args=(servidor,), daemon=True).start()

    def aceitar_conexoes(self, servidor):
        while True:
            sock, endereco = servidor.accept()
            threading.Thread(target=self.atender, args=(sock, endereco), daemon=True).start()

    def atender(self, sock, endereco):
        # quem conecta e nao se registra a tempo e desconectado
        sock.settimeout(config.TEMPO_PARA_REGISTRO)
        try:
            sock = tls_servidor(sock)
            conexao = Conexao(sock)
            mensagem = conexao.receber()
        except (OSError, ValueError):
            print(f"{endereco} nao se registrou")
            sock.close()
            return

        aceito = self.registro_valido(mensagem)
        if mensagem is not None:
            conexao.enviar({"tipo": "REGISTRO", "aceito": aceito})
        if not aceito:
            conexao.fechar()
            return

        nome = mensagem["nome"]
        sock.settimeout(None)
        with self.trava:
            self.trabalhadores[nome] = conexao
        print(f"{nome} entrou ({mensagem['perfil']}). Total: {len(self.trabalhadores)}")

        while True:
            try:
                mensagem = conexao.receber()
            except (OSError, ValueError):
                mensagem = None
            if mensagem is None:
                break
            if mensagem["tipo"] == "RESPOSTA":
                self.guardar_resposta(nome, mensagem)

        with self.trava:
            del self.trabalhadores[nome]
        conexao.fechar()
        print(f"{nome} saiu")

    def registro_valido(self, mensagem):
        return (mensagem is not None
                and mensagem.get("tipo") == "REGISTRO"
                and mensagem.get("senha") == config.SENHA
                and bool(mensagem.get("nome"))
                and mensagem["nome"] not in self.trabalhadores)

    def esperar_trabalhadores(self):
        while len(self.trabalhadores) < config.MIN_TRABALHADORES:
            time.sleep(0.5)

    def enviar_para_todos(self, mensagem):
        with self.trava:
            conexoes = list(self.trabalhadores.values())
        for conexao in conexoes:
            try:
                conexao.enviar(mensagem)
            except OSError:
                pass

    # ---------------- rodadas ----------------

    def executar_rodada(self):
        serie, correto = self.gerar_serie()
        with self.trava:
            self.tarefa += 1
            self.respostas = []
        print(f"\nTarefa {self.tarefa}: {serie}")

        self.inicio_tarefa = time.perf_counter()
        self.enviar_para_todos({"tipo": "TAREFA", "tarefa": self.tarefa, "serie": serie, "premio": config.PREMIO})
        self.esperar_respostas()

        vencedor, valor, votos = self.eleger_vencedor(list(self.respostas))
        if vencedor:
            self.saldos[vencedor] = self.saldos.get(vencedor, 0) + config.PREMIO
            self.salvar_saldos()

        votos = {str(v): quantidade for v, quantidade in votos.items()}
        self.enviar_para_todos({"tipo": "RESULTADO", "tarefa": self.tarefa, "vencedor": vencedor,
                                "valor": valor, "premio": config.PREMIO, "votos": votos})
        tempo_total = (time.perf_counter() - self.inicio_tarefa) * 1000
        for medicao in self.medicoes:
            if medicao["tarefa"] == self.tarefa:
                medicao["tempo_total_ms"] = round(tempo_total, 3)

        print(f"Votos: {votos} | correto: {correto}")
        print(f"Vencedor: {vencedor} | rodada em {tempo_total:.1f} ms")

    def esperar_respostas(self):
        # para quando todos responderem ou quando o tempo acabar
        prazo = time.perf_counter() + config.TEMPO_LIMITE
        while time.perf_counter() < prazo and len(self.respostas) < len(self.trabalhadores):
            time.sleep(0.001)

    def guardar_resposta(self, nome, mensagem):
        tempo_resposta = (time.perf_counter() - self.inicio_tarefa) * 1000
        try:
            valor = float(mensagem["valor"])
        except (KeyError, TypeError, ValueError):
            return

        with self.trava:
            if mensagem.get("tarefa") != self.tarefa or tempo_resposta > config.TEMPO_LIMITE * 1000:
                return  # resposta atrasada
            if any(n == nome for n, _ in self.respostas):
                return  # so vale a primeira resposta de cada um
            self.respostas.append((nome, valor))

        tempo_llm = float(mensagem.get("tempo_llm", 0))
        self.medicoes.append({
            "tarefa": self.tarefa,
            "trabalhador": nome,
            "tls": config.USAR_TLS,
            "tempo_resposta_ms": round(tempo_resposta, 3),
            "tempo_llm_ms": round(tempo_llm, 3),
            "tempo_rede_ms": round(tempo_resposta - tempo_llm, 3),
            "bytes": len(json.dumps(mensagem)) + 1,
            "tempo_total_ms": "",
        })
        print(f"  {nome} respondeu {valor}")

    def gerar_serie(self):
        """Devolve (serie de 6 numeros, proximo numero correto)."""
        tipo = random.choice(["soma", "multiplicacao", "quadrados", "fibonacci"])
        if tipo == "soma":
            inicio, passo = random.randint(1, 20), random.randint(2, 9)
            numeros = [inicio + passo * i for i in range(7)]
        elif tipo == "multiplicacao":
            inicio, razao = random.randint(1, 5), random.randint(2, 3)
            numeros = [inicio * razao ** i for i in range(7)]
        elif tipo == "quadrados":
            inicio = random.randint(1, 10)
            numeros = [(inicio + i) ** 2 for i in range(7)]
        else:
            numeros = [random.randint(1, 5), random.randint(1, 5)]
            while len(numeros) < 7:
                numeros.append(numeros[-1] + numeros[-2])
        return numeros[:6], numeros[6]

    def eleger_vencedor(self, respostas):
        """Vence quem respondeu primeiro o valor que a maioria respondeu."""
        votos = {}
        for nome, valor in respostas:
            valor = round(valor)
            votos[valor] = votos.get(valor, 0) + 1

        if not votos:
            return None, None, votos
        # em caso de empate, max() fica com o valor que chegou primeiro
        valor_maioria = max(votos, key=votos.get)
        if votos[valor_maioria] < 2:
            return None, None, votos  # ninguem concordou com ninguem

        for nome, valor in respostas:
            if round(valor) == valor_maioria:
                return nome, valor_maioria, votos

    # ---------------- carteira e medicoes ----------------

    def carregar_saldos(self):
        if os.path.exists(config.ARQUIVO_CARTEIRA):
            with open(config.ARQUIVO_CARTEIRA) as arquivo:
                return json.load(arquivo)
        return {}

    def salvar_saldos(self):
        os.makedirs(os.path.dirname(config.ARQUIVO_CARTEIRA), exist_ok=True)
        with open(config.ARQUIVO_CARTEIRA, "w") as arquivo:
            json.dump(self.saldos, arquivo, indent=2)

    def mostrar_ranking(self):
        print("\nRanking de Pfitscher Coins:")
        for nome, saldo in sorted(self.saldos.items(), key=lambda item: item[1], reverse=True):
            print(f"  {nome}: {saldo}")

    def mostrar_resumo(self):
        if not self.medicoes:
            return
        rede = [m["tempo_rede_ms"] for m in self.medicoes]
        llm = [m["tempo_llm_ms"] for m in self.medicoes]
        print(f"\nRespostas medidas: {len(self.medicoes)} (TLS: {config.USAR_TLS})")
        print(f"Tempo medio de rede: {sum(rede) / len(rede):.3f} ms")
        print(f"Tempo medio do LLM:  {sum(llm) / len(llm):.1f} ms")

    def salvar_medicoes(self):
        if not self.medicoes:
            return
        os.makedirs(os.path.dirname(config.ARQUIVO_MEDICOES), exist_ok=True)
        arquivo_novo = not os.path.exists(config.ARQUIVO_MEDICOES)
        with open(config.ARQUIVO_MEDICOES, "a", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=self.medicoes[0].keys(), delimiter=";")
            if arquivo_novo:
                escritor.writeheader()
            escritor.writerows(self.medicoes)


if __name__ == "__main__":
    orquestrador = Orquestrador()
    orquestrador.iniciar()

    print(f"Aguardando {config.MIN_TRABALHADORES} trabalhadores...")
    orquestrador.esperar_trabalhadores()

    for rodada in range(config.RODADAS):
        orquestrador.executar_rodada()
        time.sleep(config.PAUSA_ENTRE_RODADAS)

    orquestrador.mostrar_ranking()
    orquestrador.mostrar_resumo()
    orquestrador.salvar_medicoes()
