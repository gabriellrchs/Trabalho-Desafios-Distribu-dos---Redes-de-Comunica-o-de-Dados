# Rede
HOST = "127.0.0.1"          # IP do orquestrador
PORTA = 12000               # sockets (registro dos trabalhadores e protocolo "sockets")
BUFFER = 1024
MQTT_HOST = "localhost"     # broker Mosquitto
MQTT_PORTA = 1884           # sem TLS (a 1883 pode estar ocupada pelo servico do Mosquitto)
MQTT_PORTA_TLS = 8883       # com TLS
TOPICO_TAREFAS = "pfitscher/tarefas"
TOPICO_RESPOSTAS = "pfitscher/respostas"
PROTOCOLOS = ["sockets", "http", "mqtt"]

# Seguranca
USAR_TLS = False            # True = Sockets com TLS, HTTPS e MQTT com TLS (para medir o custo da cifragem)
CERTIFICADO_CA = "certificados/ca.crt"
CERTIFICADO_SERVIDOR = "certificados/servidor.crt"
CHAVE_SERVIDOR = "certificados/servidor.key"
SENHA = "daleinter"
TEMPO_PARA_REGISTRO = 10    # segundos que uma conexao nova tem para se registrar

# Jogo
PREMIO = 10
TEMPO_LIMITE = 15           # segundos para responder cada tarefa
MIN_TRABALHADORES = 3
TAREFAS = 5                 # cada tarefa e executada uma vez em cada protocolo
PAUSA_ENTRE_RODADAS = 6     # o plano gratuito do LLM limita as perguntas por minuto
ARQUIVO_CARTEIRA = "dados/carteira.json"
ARQUIVO_MEDICOES = "dados/medicoes.csv"

# LLM (Groq)
USAR_LLM = True             # False = respostas simuladas, sem internet
MODELO = "openai/gpt-oss-20b"
