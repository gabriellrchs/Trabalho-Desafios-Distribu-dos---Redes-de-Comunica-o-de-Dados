# Abre varias conexoes sem enviar nada (mesmo ataque do exemplo de DoS visto em aula).
# Com o orquestrador rodando: python teste_dos.py

import socket
import threading
import time

import config

conexoes_ativas = []


def criar_conexao(numero):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((config.HOST, config.PORTA))
        conexoes_ativas.append(s)
        print(f"[+] Conexao #{numero} estabelecida")
    except socket.error:
        print(f"[-] Falha na conexao #{numero}")


threads = []
for i in range(10):
    t = threading.Thread(target=criar_conexao, args=(i,))
    threads.append(t)
    t.start()
    time.sleep(0.01)
for t in threads:
    t.join()

print(f"Segurando {len(conexoes_ativas)} conexoes abertas...")
time.sleep(config.TEMPO_PARA_REGISTRO + 2)

derrubadas = 0
for s in conexoes_ativas:
    s.settimeout(1)
    try:
        if s.recv(1) == b"":
            derrubadas += 1
    except (ConnectionResetError, ConnectionAbortedError):
        derrubadas += 1
    except socket.timeout:
        pass
print(f"O orquestrador derrubou {derrubadas} de {len(conexoes_ativas)} conexoes")
