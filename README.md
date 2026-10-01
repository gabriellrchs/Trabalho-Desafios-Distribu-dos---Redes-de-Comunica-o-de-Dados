# Pfitscher Coin

Sistema distribuído para comparar protocolos de comunicação. Um **orquestrador** envia uma série de
números para três **trabalhadores**. Cada um pergunta a um LLM qual é o próximo número, com um prompt
diferente, e responde. Vence quem respondeu primeiro a resposta que a maioria deu, e o vencedor
ganha Pfitscher Coins.

As **mesmas tarefas** são executadas em três protocolos: **Sockets TCP**, **HTTP** e **MQTT**. No
final, o orquestrador compara a latência e a segurança de cada um e indica o melhor.

- Por padrão os protocolos rodam **crus** (sem criptografia). Com `USAR_TLS = True` rodam com TLS 1.3
  (Sockets + TLS, HTTPS e MQTT + TLS), para medir o custo da cifragem.
- LLM: Groq, modelo `openai/gpt-oss-20b` (plano gratuito)

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `config.py` | configurações (portas, protocolos, senha, prêmio, prazo, TLS, LLM) |
| `rede.py` | envio/recebimento por socket, TLS, conexão HTTP e cliente MQTT |
| `orquestrador.py` | classe `Orquestrador`: roda as tarefas nos 3 protocolos e compara |
| `trabalhador.py` | classe `Trabalhador`: atende pelos 3 protocolos ao mesmo tempo |
| `llm.py` | pergunta ao LLM o próximo número |
| `mosquitto.conf` | configuração do broker MQTT |
| `teste_dos.py` | teste de DoS (abre várias conexões sem enviar nada) |
| `.env.exemplo` | modelo do `.env`, onde fica a chave do Groq (o `.env` não vai para o GitHub) |
| `certificados/` | certificados do TLS (usados só com `USAR_TLS = True`) |
| `dados/` | criada ao rodar: `carteira.json` (saldos) e `medicoes.csv` (tempos) |
| `docs/` | explicação do projeto e RFC do protocolo |

## Como rodar

1. Instalar as bibliotecas:
   ```
   pip install -r requirements.txt
   ```
2. Instalar o broker MQTT **Mosquitto**: https://mosquitto.org/download (instalador Windows 64-bit).
3. Copiar `.env.exemplo` para `.env` e colocar a chave do Groq:
   ```
   GROQ_API_KEY=sua-chave
   ```
   Chave gratuita em https://console.groq.com → **API Keys → Create API Key**.
4. Abrir 5 terminais na pasta do projeto, um comando em cada, nesta ordem:
   ```
   & "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v
   python orquestrador.py
   python trabalhador.py t1 analitico
   python trabalhador.py t2 apressado
   python trabalhador.py t3 chutador
   ```

O orquestrador espera os 3 trabalhadores e executa 5 tarefas em cada protocolo (15 rodadas, cerca de
2 minutos). No final mostra o ranking, a comparação dos protocolos e o protocolo escolhido. As medições
ficam em `dados/medicoes.csv`.

Opções em `config.py`:
- `USAR_TLS = True`: liga o TLS nos três protocolos, para medir o custo da cifragem;
- `USAR_LLM = False`: respostas simuladas, sem internet e sem chave;
- `PROTOCOLOS = ["sockets", "http"]`: roda sem MQTT, sem precisar do Mosquitto.

### Em computadores diferentes
Na máquina do orquestrador (e do Mosquitto), descubra o IP com `ipconfig`. Nas outras, passe esse IP
no final do comando: `python trabalhador.py t1 analitico 192.168.0.10`. Ajuste também `MQTT_HOST`
em `config.py`. A pasta `certificados/` precisa estar em todas as máquinas.

### Teste de DoS
Com o orquestrador rodando: `python teste_dos.py`

### Gerar os certificados de novo (opcional, no Git Bash)
```
cd certificados
export MSYS_NO_PATHCONV=1
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 365 -keyout ca.key -out ca.crt -subj "/CN=PCP CA" -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout servidor.key -out servidor.csr -subj "/CN=localhost"
printf "subjectAltName=DNS:localhost\nauthorityKeyIdentifier=keyid\nextendedKeyUsage=serverAuth\n" > ext.txt
openssl x509 -req -in servidor.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 365 -out servidor.crt -extfile ext.txt
```
