import http.client
import json
import ssl

import paho.mqtt.client as mqtt

import config


class Conexao:
    """Envia e recebe mensagens JSON pelo socket, uma mensagem por linha."""

    def __init__(self, sock):
        self.sock = sock
        self.buffer = ""

    def enviar(self, mensagem):
        texto = json.dumps(mensagem) + "\n"
        self.sock.sendall(texto.encode())

    def receber(self):
        # o TCP pode entregar uma mensagem em pedacos ou varias juntas,
        # entao juntamos o que chega ate encontrar o "\n"
        while "\n" not in self.buffer:
            try:
                dados = self.sock.recv(config.BUFFER)
            except (ConnectionResetError, ConnectionAbortedError):
                return None
            if not dados:
                return None
            self.buffer += dados.decode()

        linha, self.buffer = self.buffer.split("\n", 1)
        return json.loads(linha)

    def fechar(self):
        try:
            self.sock.close()
        except OSError:
            pass


def tls_servidor(sock):
    if not config.USAR_TLS:
        return sock
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_3
    contexto.load_cert_chain(config.CERTIFICADO_SERVIDOR, config.CHAVE_SERVIDOR)
    return contexto.wrap_socket(sock, server_side=True)


def tls_cliente(sock):
    if not config.USAR_TLS:
        return sock
    contexto = ssl.create_default_context(cafile=config.CERTIFICADO_CA)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_3
    return contexto.wrap_socket(sock, server_hostname="localhost")


def conexao_http(ip, porta):
    """Abre uma conexao HTTP (ou HTTPS) com o servidor HTTP de um trabalhador."""
    if not config.USAR_TLS:
        return http.client.HTTPConnection(ip, porta, timeout=config.TEMPO_LIMITE)
    contexto = ssl.create_default_context(cafile=config.CERTIFICADO_CA)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_3
    # o certificado e conferido pela CA, mas nao pelo nome, porque cada trabalhador tem um IP diferente
    contexto.check_hostname = False
    return http.client.HTTPSConnection(ip, porta, timeout=config.TEMPO_LIMITE, context=contexto)


def cliente_mqtt(nome):
    """Cria um cliente MQTT ja conectado ao broker."""
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=nome)
    porta = config.MQTT_PORTA
    if config.USAR_TLS:
        cliente.tls_set(ca_certs=config.CERTIFICADO_CA)
        porta = config.MQTT_PORTA_TLS
    cliente.connect(config.MQTT_HOST, porta)
    return cliente
