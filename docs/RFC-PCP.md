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
TLS 1.3, com mensagens JSON separadas por quebra de linha.

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

A conexao DEVERIA ser protegida por TLS 1.3. O trabalhador DEVE validar o certificado do
orquestrador com a autoridade certificadora configurada.

Cada mensagem DEVE ser um objeto JSON (RFC 8259) em uma unica linha, terminado pelo caractere LF
(0x0A). O receptor DEVE acumular os bytes recebidos ate encontrar um LF.

```
+--------------------------------------------+------+
| objeto JSON (sem quebras de linha)         |  LF  |
+--------------------------------------------+------+
```

## 4. Mensagens

Toda mensagem DEVE ter o campo `tipo`.

| Tipo      | Sentido    | Campos                                                                   |
|-----------|------------|--------------------------------------------------------------------------|
| REGISTRO  | T -> O     | `nome` (texto), `senha` (texto), `perfil` (texto)                        |
| REGISTRO  | O -> T     | `aceito` (booleano)                                                      |
| TAREFA    | O -> todos | `tarefa` (inteiro), `serie` (lista de numeros), `premio` (numero)        |
| RESPOSTA  | T -> O     | `tarefa` (inteiro), `valor` (numero), `tempo_llm` (numero, ms)           |
| RESULTADO | O -> todos | `tarefa` (inteiro), `vencedor` (texto ou null), `valor` (numero ou null), `premio` (numero), `votos` (objeto valor -> quantidade) |

(O = orquestrador, T = trabalhador)

## 5. Procedimentos

### 5.1 Registro
1. O trabalhador abre a conexao TCP e faz o handshake TLS.
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

- TLS 1.3 garante confidencialidade e integridade das mensagens, incluindo a senha.
- A validacao do certificado impede que um servidor falso se passe pelo orquestrador.
- A senha impede a entrada de trabalhadores nao autorizados.
- A resposta e ligada a conexao, e nao ao conteudo da mensagem, o que impede responder em nome
  de outro trabalhador.
- O prazo de registro limita ataques de negacao de servico com conexoes ociosas.
- A ordem de chegada e definida pelo orquestrador.
- Limitacoes: trabalhadores combinados podem forjar uma maioria; a senha e compartilhada.

## 8. Consideracoes de Desempenho

| Protocolo | Bytes extras por mensagem | Intermediario | Servidor envia sem ser chamado |
|-----------|---------------------------|---------------|--------------------------------|
| TCP (PCP) | 1                         | nao           | sim                            |
| WebSocket | 2 a 14                    | nao           | sim                            |
| MQTT      | 2 + nome do topico        | broker        | sim                            |
| HTTP/1.1  | ~150 a 400                | nao           | nao                            |

Medicoes (127.0.0.1, 3 trabalhadores, 20 rodadas, LLM simulado):

| Medida                       | Com TLS   | Sem TLS |
|------------------------------|-----------|---------|
| Tempo para conectar          | ~11-15 ms | ~2 ms   |
| Tempo de rede medio          | 1,97 ms   | 1,49 ms |
| Tempo total medio da rodada  | 9,2 ms    | 7,9 ms  |
| Tamanho da RESPOSTA          | ~85 bytes | ~85 bytes |

O principal custo do TLS e o handshake, feito uma vez por conexao. Cada registro TLS 1.3
acrescenta 22 bytes (5 de cabecalho, 1 de tipo e 16 de autenticacao).

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
T->O {"tipo": "REGISTRO", "nome": "t1", "senha": "...", "perfil": "analitico"}
O->T {"tipo": "REGISTRO", "aceito": true}
O->T {"tipo": "TAREFA", "tarefa": 1, "serie": [2, 6, 18, 54, 162, 486], "premio": 10}
T->O {"tipo": "RESPOSTA", "tarefa": 1, "valor": 1458.0, "tempo_llm": 312.5}
O->T {"tipo": "RESULTADO", "tarefa": 1, "vencedor": "t1", "valor": 1458, "premio": 10, "votos": {"1458": 2, "57": 1}}
```
