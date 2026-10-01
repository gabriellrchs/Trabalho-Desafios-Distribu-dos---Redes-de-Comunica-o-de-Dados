# Explicação do projeto

## 1. Funcionamento geral

1. O orquestrador abre a porta 12000 e espera os trabalhadores.
2. Cada trabalhador conecta e se registra com nome, senha e perfil.
3. A cada rodada o orquestrador gera uma série (ex.: `2, 6, 18, 54, 162, 486`) e envia para todos.
4. Cada trabalhador pergunta ao LLM qual é o próximo número. O perfil muda a pergunta:
   - `analitico`: descobre o padrão e responde;
   - `apressado`: responde sem fazer contas;
   - `chutador`: responde um número aleatório entre 1 e 100.
5. As respostas chegam ao orquestrador, que guarda a ordem de chegada.
6. O orquestrador elege o vencedor, paga o prêmio e avisa todos.

```
 Orquestrador                              Trabalhadores
     | <---- REGISTRO ------------------------- |   (uma vez)
     | ----- REGISTRO (aceito) ---------------> |
     |                                          |
     | ----- TAREFA (para todos) -------------> |   (cada rodada)
     |                                          |   pergunta ao LLM
     | <---- RESPOSTA ------------------------- |
     |  elege o vencedor e paga o prêmio        |
     | ----- RESULTADO (para todos) ----------> |
```

## 2. Por que sockets TCP

| | Sockets TCP | WebSocket | MQTT | HTTP |
|---|---|---|---|---|
| Bytes extras por mensagem | 1 (o `\n`) | 2 a 14 | 2 + nome do tópico | 150 a 400 (cabeçalhos) |
| Servidor envia sem ser chamado | sim | sim | sim | não |
| Intermediário | não | não | broker | não |
| Cifragem de ponta a ponta com TLS | sim | sim | não (o broker vê os dados) | sim |

- **Atraso**: a mensagem vai direto, e a conexão fica aberta entre as rodadas, então o handshake
  TCP + TLS acontece uma vez só.
- **Overhead**: só 1 byte além do conteúdo.
- **Segurança**: TLS de ponta a ponta.

**Por que não UDP:** o UDP não garante entrega nem ordem. Uma resposta perdida mudaria a votação.
Além disso, o TLS do Python funciona sobre TCP.

## 3. Relação com os exemplos de aula

| Exemplo de aula | No projeto |
|---|---|
| `socket(AF_INET, SOCK_STREAM)` | `Orquestrador.iniciar`, `Trabalhador.conectar` |
| `bind(('', porta))` + `listen` | `Orquestrador.iniciar` |
| `while True: accept()` | `Orquestrador.aceitar_conexoes` |
| uma thread por cliente (`server-threaded.py`) | `Orquestrador.atender` |
| `connect((host, porta))` | `Trabalhador.conectar` |
| `recv(1024)` / `if not dados` | `Conexao.receber` |
| `send(...encode())` | `Conexao.enviar` (usa `sendall`) |

## 4. Mensagens

Cada mensagem é um JSON em uma linha, terminado em `\n`:

```
{"tipo": "REGISTRO", "nome": "t1", "senha": "...", "perfil": "analitico"}
{"tipo": "REGISTRO", "aceito": true}
{"tipo": "TAREFA", "tarefa": 1, "serie": [2, 6, 18, 54, 162, 486], "premio": 10}
{"tipo": "RESPOSTA", "tarefa": 1, "valor": 1458.0, "tempo_llm": 312.5}
{"tipo": "RESULTADO", "tarefa": 1, "vencedor": "t1", "valor": 1458, "premio": 10, "votos": {"1458": 2, "57": 1}}
```

**Por que uma mensagem por linha:** o TCP entrega um fluxo de bytes, não mensagens separadas. Um
`recv(1024)` pode trazer meia mensagem, ou duas juntas. Por isso `Conexao.receber` junta o que chega
até encontrar o `\n`.

## 5. Threads

- Uma thread fica no `accept()` esperando conexões novas.
- Cada trabalhador tem a sua thread, que fica no `recv()` esperando as respostas dele.
- A thread principal roda as rodadas.

Como várias threads mexem na lista de trabalhadores e na lista de respostas, o acesso a elas é feito
dentro de `with self.trava:` (um `threading.Lock`), para duas threads não alterarem ao mesmo tempo.

## 6. Eleição do vencedor (`Orquestrador.eleger_vencedor`)

1. As respostas ficam na lista na ordem em que chegaram ao orquestrador.
2. Cada valor é arredondado para inteiro e os votos são contados.
3. O valor com mais votos é o da maioria. Ele precisa de pelo menos 2 votos; senão, ninguém vence.
4. Em caso de empate, fica o valor que chegou primeiro.
5. Vence o primeiro da lista que respondeu o valor da maioria.

Exemplo: chegam `t3 → 57`, `t2 → 10`, `t1 → 10`. A maioria é 10, e t2 chegou antes de t1. Então **t2 vence**.

A ordem é a de chegada no orquestrador, e não um horário enviado pelo trabalhador, que poderia mentir.

## 7. Segurança

| Problema | Solução |
|---|---|
| Alguém ler as mensagens na rede | TLS 1.3 cifra tudo (`rede.py`) |
| Servidor falso | o trabalhador confere o certificado do orquestrador (`certificados/ca.crt`) |
| Alguém de fora entrar | senha no registro |
| Responder no nome de outro | a resposta é ligada à conexão de quem se registrou, não ao conteúdo da mensagem |
| Responder várias vezes | só vale a primeira resposta de cada um |
| DoS: conexões abertas sem enviar nada | quem não se registra em 10 s é desconectado (`settimeout`) |
| Vazar a chave do LLM | a chave fica no arquivo `.env`, fora do código |

**TLS.** O socket é criado e conectado normalmente e depois passa por `wrap_socket()`, que faz o
handshake. A partir daí `send` e `recv` funcionam igual, mas os dados vão cifrados. No orquestrador,
o handshake é feito dentro da thread de cada trabalhador, e não no `accept()`. Assim um cliente lento
não trava a entrada dos outros.

**DoS.** O `teste_dos.py` repete o ataque do exemplo de aula: abre 10 conexões e não envia nada. No
`server-threaded.py` essas conexões prenderiam threads para sempre. No orquestrador, as 10 foram
derrubadas depois de 10 s, e as rodadas continuaram normalmente.

**Limitações:**
- trabalhadores combinados podem forjar a maioria;
- a senha é a mesma para todos.

## 8. LLM

- Groq, plano gratuito, modelo `openai/gpt-oss-20b`. O `llama-3.1-8b-instant` foi descontinuado em
  agosto/2026. Se o modelo atual também for retirado, troque `MODELO` em `config.py` por um da lista em
  https://console.groq.com/docs/models.
- O modelo "pensa" antes de responder. `reasoning_effort="low"` deixa esse raciocínio curto.
- O primeiro número encontrado no texto da resposta é usado como valor.
- Se o LLM falhar, o trabalhador não responde aquela tarefa.
- `USAR_LLM = False` usa respostas simuladas: `chutador` sorteia um número e os outros dois perfis
  supõem que a série soma sempre o mesmo valor.

## 9. Desempenho

### O que é medido (no orquestrador)

| Coluna do CSV | Significado |
|---|---|
| `tempo_resposta_ms` | do envio da TAREFA até a RESPOSTA chegar |
| `tempo_llm_ms` | tempo que o trabalhador levou com o LLM (ele mesmo informa) |
| `tempo_rede_ms` | `tempo_resposta - tempo_llm`: ida e volta pela rede |
| `tempo_total_ms` | do envio da TAREFA até o envio do RESULTADO |
| `bytes` | tamanho da mensagem RESPOSTA |

O trabalhador também mostra quanto tempo levou para conectar (TCP + TLS).

### Como medir
1. Rode com `USAR_TLS = True`, depois com `USAR_TLS = False`.
2. As medições vão para `dados/medicoes.csv`, uma linha por resposta; a coluna `tls` separa os dois
   casos. O arquivo abre no Excel (separador `;`).
3. Com `USAR_LLM = False` se mede só a rede. Com `True`, o cenário real.

### Resultados obtidos
Um computador (127.0.0.1), LLM simulado, 3 trabalhadores, 20 rodadas, 60 respostas por caso:

| | Com TLS | Sem TLS |
|---|---|---|
| Tempo para conectar | ~11 a 15 ms | ~2 ms |
| Tempo de rede médio | 1,97 ms | 1,49 ms |
| Tempo de rede mediano | 1,93 ms | 1,38 ms |
| Tempo total médio da rodada | 9,2 ms | 7,9 ms |
| Tamanho da RESPOSTA | ~85 bytes | ~85 bytes |

- O custo maior do TLS está no handshake, ao conectar, e ele acontece uma vez por trabalhador.
- Depois disso, o TLS acrescenta cerca de 0,5 ms por resposta e 22 bytes por mensagem no fio.
- Com o LLM real, o tempo do LLM fica em centenas de milissegundos, muito maior que o da rede. Por
  isso os dois são medidos separadamente.

Os números variam de acordo com o computador e a rede usados.

### Wireshark
Capture na interface *Adapter for loopback traffic capture* com o filtro `tcp.port == 12000`:
- sem TLS, o JSON aparece legível (botão direito → *Follow → TCP Stream*);
- com TLS, aparece apenas *Application Data*.
