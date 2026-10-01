```
INE/UFSC - Redes de Comunicacao de Dados                               <Nome 1>
Request for Comments: XXXX                                             <Nome 2>
Categoria: Experimental                                                UFSC
                                                                       Outubro 2026

            PCP - Pfitscher Coin Protocol, Versao 1
```

## Status deste Memorando

Este documento especifica um protocolo experimental para fins academicos.
A distribuicao deste memorando e ilimitada.

## Resumo

O Pfitscher Coin Protocol (PCP) define a comunicacao entre um orquestrador e um conjunto de
trabalhadores. O orquestrador publica uma serie numerica e um premio; cada trabalhador estima o
proximo valor e responde; o orquestrador elege como vencedor quem respondeu primeiro o valor
escolhido pela maioria e o premia em Pfitscher Coins. O PCP opera sobre TCP, protegido por
TCP, com mensagens JSON separadas por quebra de linha, opcionalmente protegidas por TLS 1.3.

## Sumario

1. Terminologia
2. Visao Geral
3. Transporte
4. Mensagens
5. Procedimentos
6. Regra de Eleicao
7. Consideracoes de Seguranca
8. Consideracoes de Desempenho
9. Referencias
Apendice A. Exemplo de Rodada
Apendice B. Mapeamento para HTTP e MQTT

---

## 1. Terminologia

As palavras "DEVE", "NAO DEVE", "DEVERIA" e "PODE" seguem a RFC 2119.

- **Orquestrador**: no central que mantem a lista de trabalhadores, publica tarefas, elege
  vencedores e guarda os saldos.
- **Trabalhador**: no que resolve as tarefas e envia respostas.
- **Tarefa**: serie numerica cujo proximo valor deve ser estimado.
- **Perfil**: estrategia usada pelo trabalhador (`analitico`, `apressado` ou `chutador`).
- **Pfitscher Coin**: unidade de premio creditada ao vencedor de uma rodada.

## 2. Visao Geral

```
 Orquestrador                              Trabalhadores
     | <---- REGISTRO ------------------------- |   (uma vez)
     | ----- REGISTRO (aceito) ---------------> |
     | ----- TAREFA (para todos) -------------> |   (cada rodada)
     | <---- RESPOSTA ------------------------- |
     | ----- RESULTADO (para todos) ----------> |
```

## 3. Transporte

O PCP DEVE usar TCP. A porta padrao e 12000. Cada trabalhador mantem uma unica conexao com o
orquestrador durante toda a sessao.

Na forma basica, as mensagens trafegam sem cifragem. A conexao PODE ser protegida por TLS 1.3; nesse
caso o trabalhador DEVE validar o certificado do orquestrador com a autoridade certificadora configurada.

Cada mensagem DEVE ser um objeto JSON (RFC 8259) em uma unica linha, terminado pelo caractere LF
(0x0A). O receptor DEVE acumular os bytes recebidos ate encontrar um LF.

```
+--------------------------------------------+------+
| objeto JSON (sem quebras de linha)         |  LF  |
+--------------------------------------------+------+
```

A escolha do TCP resultou da avaliacao da secao 8, na qual as mesmas mensagens foram transportadas
tambem sobre HTTP e MQTT (Apendice B). O registro sempre ocorre pela conexao TCP.

## 4. Mensagens

Toda mensagem DEVE ter o campo `tipo`.

| Tipo      | Sentido    | Campos                                                                   |
|-----------|------------|--------------------------------------------------------------------------|
| REGISTRO  | T -> O     | `nome` (texto), `senha` (texto), `perfil` (texto), `porta_http` (inteiro) |
| REGISTRO  | O -> T     | `aceito` (booleano)                                                      |
| TAREFA    | O -> todos | `protocolo` (texto), `tarefa` (inteiro), `serie` (lista de numeros), `premio` (numero) |
| RESPOSTA  | T -> O     | `nome` (texto), `tarefa` (inteiro), `valor` (numero), `tempo_llm` (numero, ms) |
| RESULTADO | O -> todos | `tarefa` (inteiro), `vencedor` (texto ou null), `valor` (numero ou null), `premio` (numero), `votos` (objeto valor -> quantidade) |

(O = orquestrador, T = trabalhador)

## 5. Procedimentos

### 5.1 Registro
1. O trabalhador abre a conexao TCP (e faz o handshake TLS, se usado).
2. O trabalhador DEVE enviar REGISTRO como primeira mensagem.
3. O orquestrador DEVE responder REGISTRO com `aceito` falso, e fechar a conexao, se a senha for
   invalida, se o nome for vazio ou se o nome ja estiver em uso.
4. O orquestrador DEVE fechar conexoes que nao enviarem REGISTRO em ate 10 segundos.

### 5.2 Rodada
1. O orquestrador envia TAREFA para todos os trabalhadores registrados.
2. O orquestrador DEVE guardar as respostas na ordem em que chegam.
3. O orquestrador DEVE ignorar uma RESPOSTA quando:
   - `tarefa` for diferente da tarefa atual;
   - chegar depois do prazo (15 segundos);
   - o trabalhador ja tiver respondido a tarefa;
   - `valor` nao for numerico.
4. A resposta e atribuida ao trabalhador registrado naquela conexao.
5. A coleta termina quando todos responderem ou quando o prazo acabar.
6. O orquestrador elege o vencedor (secao 6), credita o premio e envia RESULTADO para todos.

### 5.3 Saida
O fechamento da conexao TCP indica a saida do trabalhador, que e removido da lista.

## 6. Regra de Eleicao

1. Cada `valor` e arredondado para inteiro.
2. Os votos sao contados por valor, na ordem de chegada.
3. O valor da maioria e o que tem mais votos. Em empate, prevalece o valor que chegou primeiro.
4. Se o valor da maioria tiver menos de 2 votos, nao ha vencedor.
5. O vencedor e o primeiro trabalhador a responder o valor da maioria.

## 7. Consideracoes de Seguranca

- Sem TLS, o PCP nao oferece confidencialidade nem integridade: senha, tarefas e respostas trafegam em
  texto puro e podem ser lidas ou alteradas por quem tiver acesso a rede. O mesmo vale para HTTP e
  MQTT em sua forma basica.
- Com TLS 1.3, as mensagens sao cifradas e autenticadas, e a validacao do certificado impede que um
  servidor falso se passe pelo orquestrador.
- A senha impede a entrada de trabalhadores nao autorizados (em texto puro sem TLS).
- A resposta e ligada a conexao, e nao ao conteudo da mensagem, o que impede responder em nome de
  outro trabalhador. No mapeamento MQTT (Apendice B) essa garantia nao existe: a identidade vem do
  campo `nome` e qualquer cliente do broker pode publicar no topico de respostas.
- O prazo de registro limita ataques de negacao de servico com conexoes ociosas.
- A ordem de chegada e definida pelo orquestrador.
- Limitacoes: trabalhadores combinados podem forjar uma maioria; a senha e compartilhada.

## 8. Consideracoes de Desempenho

As mesmas tarefas, com os mesmos tres trabalhadores, foram executadas sobre TCP, HTTP e MQTT. Para cada
resposta mediu-se o tempo de rede: o tempo entre o envio da TAREFA e a chegada da RESPOSTA, menos o
tempo de processamento informado pelo trabalhador. As conexoes foram abertas antes das medicoes.

| Protocolo | Bytes extras por mensagem | Intermediario | Cifragem com TLS     |
|-----------|---------------------------|---------------|----------------------|
| TCP (PCP) | 1                         | nao           | ponta a ponta        |
| HTTP/1.1  | ~150 a 400 (cabecalhos)   | nao           | ponta a ponta        |
| MQTT      | 2 a 4 + nome do topico    | broker        | apenas ate o broker  |

Tempo de rede medio por resposta (localhost, 3 trabalhadores, 60 respostas por protocolo, faixa de
tres execucoes):

| Protocolo | Cru (sem TLS) | Com TLS 1.3   |
|-----------|---------------|---------------|
| TCP       | 1,9 - 2,4 ms  | 2,6 - 2,8 ms  |
| HTTP      | 7,3 - 9,6 ms  | 6,0 - 8,8 ms  |
| MQTT      | 4,4 - 5,7 ms  | 6,2 - 7,0 ms  |

Na forma crua, nenhum dos tres protocolos cifra os dados. Criterio de escolha: e eliminado o protocolo
que expoe as mensagens a um terceiro (o MQTT, cujo broker recebe todo o trafego e aceita publicacoes
de qualquer cliente); entre os restantes, prevalece a menor latencia. O TCP apresentou a menor
latencia e o menor overhead, e foi adotado como transporte do PCP. A cifragem, quando necessaria, e
obtida com TLS sobre o TCP.

Cada registro TLS 1.3 acrescenta 22 bytes (5 de cabecalho, 1 de tipo e 16 de autenticacao).

## 9. Referencias

- RFC 9293 - Transmission Control Protocol
- RFC 2119 - Key words for use in RFCs to Indicate Requirement Levels
- RFC 8259 - The JSON Data Interchange Format
- RFC 8446 - The Transport Layer Security (TLS) Protocol Version 1.3
- RFC 6455 - The WebSocket Protocol
- RFC 9112 - HTTP/1.1
- OASIS - MQTT Version 3.1.1

## Apendice A. Exemplo de Rodada

```
T->O {"tipo": "REGISTRO", "nome": "t1", "senha": "...", "perfil": "analitico", "porta_http": 52011}
O->T {"tipo": "REGISTRO", "aceito": true}
O->T {"tipo": "TAREFA", "protocolo": "sockets", "tarefa": 1, "serie": [2, 6, 18, 54, 162, 486], "premio": 10}
T->O {"tipo": "RESPOSTA", "nome": "t1", "tarefa": 1, "valor": 1458.0, "tempo_llm": 312.5}
O->T {"tipo": "RESULTADO", "tarefa": 1, "vencedor": "t1", "valor": 1458, "premio": 10, "votos": {"1458": 2, "57": 1}}
```

## Apendice B. Mapeamento para HTTP e MQTT (usado na avaliacao)

HTTP: cada trabalhador mantem um servidor HTTP(S) na porta informada em `porta_http`. O orquestrador
envia TAREFA e RESULTADO no corpo de um `POST /` (application/json). A RESPOSTA volta no corpo da
resposta HTTP 200 da TAREFA.

MQTT: orquestrador e trabalhadores se conectam a um broker (porta 1884 sem TLS, 8883 com TLS). O
orquestrador publica TAREFA e RESULTADO no topico `pfitscher/tarefas`; os trabalhadores publicam
RESPOSTA no topico `pfitscher/respostas`, identificando-se pelo campo `nome`.

