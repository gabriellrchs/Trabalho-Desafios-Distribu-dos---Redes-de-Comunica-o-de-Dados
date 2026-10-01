# Pfitscher Coin

Sistema distribuído com sockets TCP. Um **orquestrador** envia uma série de números para vários
**trabalhadores**. Cada trabalhador pergunta a um LLM qual é o próximo número e responde. Vence quem
respondeu primeiro a resposta que a maioria deu, e o vencedor ganha Pfitscher Coins.

- Comunicação: sockets TCP (`socket`)
- Segurança: TLS 1.3 (`ssl`)
- LLM: Groq, modelo `openai/gpt-oss-20b` (plano gratuito)

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `config.py` | configurações (porta, senha, prêmio, prazo, TLS, LLM) |
| `rede.py` | classe `Conexao` (envia e recebe mensagens) e funções que ligam o TLS |
| `orquestrador.py` | classe `Orquestrador` (servidor) |
| `trabalhador.py` | classe `Trabalhador` (cliente) |
| `llm.py` | pergunta ao LLM o próximo número |
| `teste_dos.py` | teste de DoS (abre várias conexões sem enviar nada) |
| `.env.exemplo` | modelo do `.env`, onde fica a chave da API do Groq (o `.env` não vai para o GitHub) |
| `certificados/` | certificados do TLS |
| `dados/` | criada ao rodar: `carteira.json` (saldos) e `medicoes.csv` (tempos) |
| `docs/` | explicação do projeto e RFC do protocolo |

## Como rodar

1. Instalar a biblioteca do LLM:
   ```
   pip install groq
   ```
2. Copiar o arquivo `.env.exemplo` para `.env` e colocar a chave do Groq nele:
   ```
   GROQ_API_KEY=sua-chave
   ```
   Para criar uma chave gratuita: https://console.groq.com → **API Keys → Create API Key**.
3. Abrir 4 terminais na pasta do projeto, um comando em cada:
   ```
   python orquestrador.py
   python trabalhador.py t1 analitico
   python trabalhador.py t2 apressado
   python trabalhador.py t3 chutador
   ```

O orquestrador espera 3 trabalhadores, roda 5 rodadas e mostra o ranking e os tempos medidos.

Para testar sem internet ou sem chave: `USAR_LLM = False` em `config.py`.

### Em computadores diferentes
Na máquina do orquestrador, descubra o IP com `ipconfig`. Nas outras máquinas, passe esse IP no final:
`python trabalhador.py t1 analitico 192.168.0.10`. A pasta `certificados/` precisa estar em todas.

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
