"""Configuracao lida das variaveis de ambiente, num lugar so.

No docker compose cada servico recebe as suas variaveis pelo bloco
`environment` do docker-compose.yml. Rodando na maquina host, o .env da raiz
completa o que faltar (load_dotenv nao sobrescreve variavel que ja existe).

Cada servico so precisa das variaveis que usa: por isso nada aqui levanta
erro na importacao. Quem precisa de um valor chama obrigatoria().
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# o .env fica na raiz do projeto, tres niveis acima deste arquivo
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def obrigatoria(nome: str) -> str:
    valor = os.getenv(nome)
    if not valor:
        raise RuntimeError(f"variavel de ambiente {nome} nao definida")
    return valor


def opcional(nome: str, padrao: str = "") -> str:
    return os.getenv(nome) or padrao


# ---------- PostgreSQL ----------
DATABASE_URL = opcional("DATABASE_URL")
SQL_ECHO = opcional("SQL_ECHO", "false").lower() == "true"

# ---------- InfluxDB ----------
INFLUX_URL = opcional("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = opcional("INFLUX_TOKEN")
INFLUX_ORG = opcional("INFLUX_ORG", "gasguard")
INFLUX_BUCKET = opcional("INFLUX_BUCKET", "sensores")       # telemetria ao vivo
INFLUX_BUCKET_LAB = opcional("INFLUX_BUCKET_LAB", "lab")    # amostra sintetica

# ---------- RabbitMQ ----------
RABBIT_HOST = opcional("RABBIT_HOST", "localhost")
RABBIT_PORT = int(opcional("RABBIT_PORT", "5672"))
RABBIT_VHOST = opcional("RABBIT_VHOST", "gasguard")
# Cada servico entra com o PROPRIO usuario (definido no docker-compose).
RABBIT_USUARIO = opcional("RABBIT_USUARIO")
RABBIT_SENHA = opcional("RABBIT_SENHA")
RABBIT_GESTAO_URL = opcional("RABBIT_GESTAO_URL", "http://localhost:15672")

# ---------- MQTT (so o gateway fala MQTT) ----------
MQTT_HOST = opcional("MQTT_HOST", "localhost")
MQTT_PORT = int(opcional("MQTT_PORT", "1883"))
MQTT_USUARIO = opcional("MQTT_USUARIO")
MQTT_SENHA = opcional("MQTT_SENHA")

# ---------- autenticacao ----------
JWT_SEGREDO = opcional("JWT_SEGREDO")
JWT_MINUTOS = int(opcional("JWT_MINUTOS", "480"))

# ---------- IA e laboratorio ----------
DIR_DADOS = Path(opcional("DIR_DADOS", "/dados"))
DIR_MODELOS = Path(opcional("DIR_MODELOS", "/modelos"))
# Teto do gerador: acima disso a maquina da apresentacao trava.
LAB_MAX_LEITURAS = int(opcional("LAB_MAX_LEITURAS", "30000000"))

# ---------- LLM local ----------
OLLAMA_URL = opcional("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODELO = opcional("OLLAMA_MODELO", "llama3.2:3b")
ASSISTENTE_PERGUNTAS_POR_MINUTO = int(opcional("ASSISTENTE_PERGUNTAS_POR_MINUTO", "5"))

# ---------- links das interfaces de administracao (pagina Infraestrutura) ----------
LINK_RABBITMQ = opcional("LINK_RABBITMQ", "http://127.0.0.1:15672")
LINK_INFLUX = opcional("LINK_INFLUX", "http://127.0.0.1:8086")
LINK_ADMINER = opcional("LINK_ADMINER", "http://127.0.0.1:8081")
