import os
import random
import re
import sys

import config

PROMPTS = {
    "analitico": "Descubra o padrao da sequencia e responda apenas com o proximo numero.",
    "apressado": "Sem fazer contas, responda apenas com o numero que parece vir depois na sequencia.",
    "chutador": "Nao analise a sequencia. Responda apenas um numero inteiro aleatorio entre 1 e 100.",
}


def carregar_env():
    """Le o arquivo .env (linhas NOME=valor) e coloca os valores nas variaveis de ambiente."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho) as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                nome, valor = linha.split("=", 1)
                os.environ.setdefault(nome.strip(), valor.strip().strip('"'))


cliente = None
if config.USAR_LLM:
    carregar_env()
    if not os.environ.get("GROQ_API_KEY"):
        sys.exit("Chave do Groq nao encontrada. Coloque GROQ_API_KEY=sua-chave no arquivo .env")
    from groq import Groq
    cliente = Groq()  # usa a chave GROQ_API_KEY


def estimar_proximo(serie, perfil):
    """Devolve o proximo numero da serie segundo o LLM, ou None se der erro."""
    if not config.USAR_LLM:
        return simular(serie, perfil)

    pergunta = PROMPTS[perfil] + "\nSequencia: " + ", ".join(str(n) for n in serie)
    try:
        resposta = cliente.chat.completions.create(
            model=config.MODELO,
            messages=[{"role": "user", "content": pergunta}],
            max_tokens=1000,
            reasoning_effort="low",
        )
    except Exception as erro:
        print("Erro no LLM:", erro)
        return None

    texto = resposta.choices[0].message.content or ""
    numero = re.search(r"-?\d+(\.\d+)?", texto)
    if numero is None:
        return None
    return float(numero.group())


def simular(serie, perfil):
    """Resposta sem LLM, para testar sem internet."""
    if perfil == "chutador":
        return float(random.randint(1, 100))
    return float(serie[-1] + (serie[-1] - serie[-2]))
