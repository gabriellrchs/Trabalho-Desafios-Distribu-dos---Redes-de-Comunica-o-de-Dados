# Explicação do projeto

## 1. Funcionamento geral

1. O orquestrador abre a porta 12000 e espera os trabalhadores.
2. Cada trabalhador:
   - sobe um servidor HTTP(S) numa porta livre;
   - se conecta ao broker MQTT e assina o tópico de tarefas;
   - conecta no orquestrador por socket e se registra com nome, senha, perfil e a porta HTTP.
3. O orquestrador gera 5 séries (ex.: `2, 6, 18, 54, 162, 486`). **Cada série é enviada uma vez em
   cada protocolo**: Sockets, HTTP e MQTT.
4. Cada trabalhador pergunta ao LLM qual é o próximo número. O perfil muda o prompt:
   - `analitico`: descobre o padrão e responde;
   - `apressado`: responde sem fazer contas;
   - `chutador`: responde um número aleatório entre 1 e 100.
5. O orquestrador guarda as respostas na ordem de chegada, elege o vencedor, paga o prêmio e avisa
   todos pelo mesmo protocolo.
6. No final, compara a latência e a segurança dos três protocolos e indica o melhor.

```
 Orquestrador                              Trabalhadores
     | <---- REGISTRO (socket) ---------------- |   (uma vez)
     | ----- REGISTRO (aceito) ---------------> |
     |                                          |
     |  para cada tarefa, em cada protocolo:    |
     | ----- TAREFA (para todos) -------------> |
     |                                          |   pergunta ao LLM
     | <---- RESPOSTA ------------------------- |
     |  elege o vencedor e paga o prêmio        |
     | ----- RESULTADO (para todos) ----------> |
```

## 2. Como cada protocolo foi implementado

As mensagens (TAREFA, RESPOSTA, RESULTADO) são as mesmas nos três. Só muda o transporte.
No trabalhador, os três caminhos chamam a mesma função, `tratar_mensagem()`.

| | Sockets | HTTP | MQTT |
|---|---|---|---|
| Biblioteca | `socket` + `ssl` | `http.server` e `http.client` | `paho-mqtt` + broker Mosquitto |
| Quem é servidor | orquestrador | cada trabalhador | o broker |
| Envio da TAREFA | `sendall` para cada trabalhador | um `POST` para cada trabalhador | um `publish` no tópico `pfitscher/tarefas`; o broker entrega a todos |
| Volta da RESPOSTA | pela mesma conexão | na resposta do próprio `POST` | `publish` no tópico `pfitscher/respostas` |
| Caminho | direto | direto | passa pelo broker (2 trechos) |
| Sem TLS (padrão) | texto puro | texto puro | texto puro |
| Com TLS (`USAR_TLS = True`) | ponta a ponta | ponta a ponta (HTTPS) | só entre cada cliente e o broker |
| Bytes extras por mensagem | 1 (o `\n`) | ~150 a 400 (cabeçalhos HTTP) | 2 a 4 + nome do tópico |

Nos três protocolos a conexão é aberta **antes** das tarefas e fica aberta. Assim a medição não inclui
o handshake TCP/TLS e a comparação é justa.

### Por que uma mensagem por linha (Sockets)
O TCP entrega um fluxo de bytes, não mensagens separadas. Um `recv(1024)` pode trazer meia mensagem,
ou duas juntas. Por isso cada mensagem termina com `\n`, e `Conexao.receber` junta o que chega até
encontrar esse caractere. HTTP e MQTT já separam as mensagens sozinhos.

## 3. Relação com os exemplos de aula (Sockets)

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

```
{"tipo": "REGISTRO", "nome": "t1", "senha": "...", "perfil": "analitico", "porta_http": 52011}
{"tipo": "REGISTRO", "aceito": true}
{"tipo": "TAREFA", "protocolo": "mqtt", "tarefa": 3, "serie": [2, 6, 18, 54, 162, 486], "premio": 10}
{"tipo": "RESPOSTA", "nome": "t1", "tarefa": 3, "valor": 1458.0, "tempo_llm": 312.5}
{"tipo": "RESULTADO", "tarefa": 3, "vencedor": "t1", "valor": 1458, "premio": 10, "votos": {"1458": 2, "42": 1}}
```

## 5. Threads

- **Sockets:** uma thread fica no `accept()`, e cada trabalhador tem a sua thread no `recv()`.
- **HTTP:** o orquestrador cria uma thread por `POST`, porque a resposta só volta quando o LLM termina.
  No trabalhador, o `ThreadingHTTPServer` atende cada conexão numa thread.
- **MQTT:** o `paho-mqtt` recebe as mensagens numa thread própria (`loop_start`).
- A thread principal do orquestrador roda as rodadas.

O acesso à lista de trabalhadores e à lista de respostas é feito dentro de `with self.trava:`
(`threading.Lock`), para duas threads não alterarem os dados ao mesmo tempo.

## 6. Eleição do vencedor (`Orquestrador.eleger_vencedor`)

1. As respostas ficam na ordem em que chegaram ao orquestrador.
2. Cada valor é arredondado para inteiro e os votos são contados.
3. O valor com mais votos é o da maioria. Ele precisa de pelo menos 2 votos; senão, ninguém vence.
4. Em caso de empate, fica o valor que chegou primeiro.
5. Vence o primeiro que respondeu o valor da maioria.

Exemplo: chegam `t3 → 57`, `t2 → 10`, `t1 → 10`. A maioria é 10, e t2 chegou antes de t1. Então **t2 vence**.

## 7. Segurança

Os protocolos são avaliados **crus**, como especificados, sem nenhuma camada de criptografia adicionada.
Nessa forma, **nenhum dos três cifra os dados**: tudo trafega em texto puro, inclusive a senha do
registro, as séries e as respostas. Isso pode ser comprovado no Wireshark (seção 9).

Mesmo sem cifragem, os três não têm a mesma exposição:

| | Sockets | HTTP | MQTT |
|---|---|---|---|
| Cifragem (cru) | não | não | não |
| Quem participa da comunicação | só orquestrador e trabalhador | só orquestrador e trabalhador | orquestrador, trabalhador **e o broker** |
| Quem consegue ler as tarefas | quem capturar o tráfego | quem capturar o tráfego | quem capturar o tráfego **ou qualquer cliente que assine o tópico no broker** |
| Quem enviou a resposta | a conexão que se registrou | a conexão aberta com aquele trabalhador | o nome escrito na mensagem (dá para falsificar publicando no tópico) |
| Como cifrar, se necessário | TLS em volta do socket | HTTPS (padrão da web) | TLS até o broker; o broker continua lendo tudo |

Com `USAR_TLS = True` o sistema liga essas proteções (Sockets + TLS, HTTPS e MQTT + TLS) e mede quanto
elas custam em latência.

Outras proteções do sistema:
- **Senha:** o registro exige a senha (em texto puro no modo cru).
- **Resposta única:** só vale a primeira resposta de cada trabalhador por tarefa.
- **DoS:** quem conecta por socket e não se registra em 10 s é desconectado. O `teste_dos.py` repete o
  ataque do exemplo de aula (10 conexões paradas). As 10 foram derrubadas e as rodadas continuaram.
- **Chave do LLM:** fica no `.env`, fora do código e fora do GitHub.

## 8. LLM

- Groq, plano gratuito, modelo `openai/gpt-oss-20b` (`MODELO` em `config.py`).
- `reasoning_effort="low"` deixa o raciocínio do modelo curto.
- O primeiro número do texto da resposta é usado como valor. Se o LLM falhar, o trabalhador não responde.
- `USAR_LLM = False` usa respostas simuladas, sem internet.
- Observação: o perfil `chutador` respondeu **42** em todas as rodadas. LLMs não geram números
  aleatórios de verdade.

## 9. Avaliação de desempenho

### O que é medido (no orquestrador)

| Coluna do CSV | Significado |
|---|---|
| `protocolo` | sockets, http ou mqtt |
| `tempo_resposta_ms` | do envio da TAREFA até a RESPOSTA chegar |
| `tempo_llm_ms` | tempo que o trabalhador levou com o LLM (ele mesmo informa) |
| `tempo_rede_ms` | `tempo_resposta - tempo_llm`: o custo da comunicação |
| `tempo_total_ms` | do envio da TAREFA até o envio do RESULTADO |

O `tempo_rede_ms` é o que compara os protocolos, porque tira o tempo do LLM, que é muito maior e varia.

### Resultados
Um computador (localhost), 3 trabalhadores, LLM simulado, 20 tarefas por protocolo (60 respostas em
cada). Média do tempo de rede por resposta, faixa de 3 execuções:

| Protocolo | Cru (padrão) | Com TLS |
|---|---|---|
| Sockets | 1,9 – 2,4 ms | 2,6 – 2,8 ms |
| HTTP | 7,3 – 9,6 ms | 6,0 – 8,8 ms |
| MQTT | 4,4 – 5,7 ms | 6,2 – 7,0 ms |

Com o LLM de verdade (2 tarefas por protocolo, com TLS), a ordem se manteve: Sockets 3,5 ms, MQTT
7,9 ms e HTTP 9,7 ms de rede, contra ~360 a 610 ms do LLM por resposta.

### Interpretação
- **Sockets foi o mais rápido em todos os casos.** A mensagem vai direto, com 1 byte extra.
- **MQTT ficou em segundo no modo cru.** O broker acrescenta um trecho a mais, mas o cabeçalho é pequeno.
  Com TLS ele fica mais lento, porque a mensagem é cifrada e decifrada **duas vezes**
  (trabalhador → broker → orquestrador).
- **HTTP foi o mais lento.** Cada mensagem leva cabeçalhos e passa pelo processamento de uma requisição
  completa. Esse custo é tão maior que a diferença do TLS (~0,5 ms) ficou dentro da variação entre execuções.
- **O LLM (centenas de ms) é muito mais lento que a rede (poucos ms)** em qualquer protocolo.

### Decisão (`Orquestrador.comparar_protocolos`)
1. **Segurança primeiro:** sai o protocolo que expõe as mensagens a um terceiro. O MQTT sai, porque todo
   o tráfego passa pelo broker, qualquer cliente do broker pode ler as tarefas e publicar respostas com
   nome falso, e mesmo com TLS o broker lê tudo.
2. **Entre os que sobram, ganha a menor latência.**

**Resultado: Sockets TCP**, nos dois modos. Foi o mais rápido, tem o menor overhead e não depende de
intermediário. Para cifrar os dados, basta colocar TLS em volta do socket, com custo de ~0,7 ms por
resposta e um handshake na conexão.

### Wireshark
Capture na interface *Adapter for loopback traffic capture*:
- filtros: `tcp.port == 12000` (sockets), `http` (HTTP) e `tcp.port == 1884` (MQTT);
- **no modo cru, o JSON das mensagens e a senha aparecem legíveis nos três protocolos**
  (botão direito → *Follow → TCP Stream*). É a evidência de que nenhum deles cifra os dados;
- com `USAR_TLS = True` (MQTT na porta 8883), aparece só *Application Data*;
- o tamanho dos pacotes mostra o overhead real de cada protocolo.

Os números variam de acordo com o computador e a rede usados.
