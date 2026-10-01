# Rede
HOST = "127.0.0.1"          # IP do orquestrador
PORTA = 12000
BUFFER = 1024

# Seguranca
USAR_TLS = True
CERTIFICADO_CA = "certificados/ca.crt"
CERTIFICADO_SERVIDOR = "certificados/servidor.crt"
CHAVE_SERVIDOR = "certificados/servidor.key"
SENHA = "daleinter"
TEMPO_PARA_REGISTRO = 10    # segundos que uma conexao nova tem para se registrar

# Jogo
PREMIO = 10
TEMPO_LIMITE = 15           # segundos para responder cada tarefa
MIN_TRABALHADORES = 3
RODADAS = 5
PAUSA_ENTRE_RODADAS = 2
ARQUIVO_CARTEIRA = "dados/carteira.json"
ARQUIVO_MEDICOES = "dados/medicoes.csv"

# LLM (Groq)
USAR_LLM = True             # False = respostas simuladas, sem internet
MODELO = "openai/gpt-oss-20b"
