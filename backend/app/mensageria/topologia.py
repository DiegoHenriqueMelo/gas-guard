"""Nomes das exchanges e filas, e como se montam as routing keys.

A topologia em si (quem esta ligado em quem) e declarada no RabbitMQ pelo
arquivo infra/rabbitmq/topologia.json, carregado quando o broker sobe. Os
servicos NAO declaram filas: cada usuario do RabbitMQ so tem permissao de
ler e escrever, nao de configurar. Este modulo so guarda os nomes, para nao
haver "q.gravador" escrito a mao em seis lugares.

Routing keys (exchange do tipo topic, segmentos separados por ponto):

    telemetry.<zona>.<tipo>.<dispositivo>   ex.: telemetry.cozinha.gas.GAS-01
    cmd.<zona>.<tipo>.<dispositivo>         ex.: cmd.cozinha.valvula.VALVULA-01
    insight.<zona>.<tipo>.<dispositivo>     ex.: insight.cozinha.exaustor.EXAUSTOR-01
    alerta.<zona>.<tipo>.<dispositivo>
    acionamento.<zona>.<tipo>.<dispositivo>
    job.<tipo>.<id>                          ex.: job.gerar.12 (progresso)
    modelo.<evento>                          ex.: modelo.publicado
"""

import re

VHOST = "gasguard"

# ---------- exchanges ----------
EX_TELEMETRIA = "gg.telemetria"  # topic: leituras que chegam do MQTT
EX_COMANDOS = "gg.comandos"      # topic: comandos que voltam para o MQTT
EX_EVENTOS = "gg.eventos"        # topic: IA, alertas, regras, progresso
EX_JOBS = "gg.jobs"              # direct: jobs demorados (gerar, treinar)
EX_DLX = "gg.dlx"                # fanout: destino das mensagens mortas

# ---------- filas ----------
Q_GRAVADOR = "q.gravador"        # -> InfluxDB
Q_INFERENCIA = "q.inferencia"    # -> modelos de regressao
Q_REGRAS = "q.regras"            # -> regras de negocio (atuador automatico)
Q_WEBSOCKET = "q.websocket"      # -> navegador, ao vivo
Q_ALERTAS = "q.alertas"          # -> tabela de alertas no PostgreSQL
Q_COMANDOS = "q.comandos"        # -> gateway -> MQTT -> simulador
Q_JOBS_GERAR = "q.jobs.gerar"    # -> laboratorio (geracao de dados)
Q_JOBS_TREINAR = "q.jobs.treinar"  # -> laboratorio (treino)
Q_DLQ = "q.dlq"                  # mensagens mortas, preservadas

TODAS_AS_FILAS = [
    Q_GRAVADOR,
    Q_INFERENCIA,
    Q_REGRAS,
    Q_WEBSOCKET,
    Q_ALERTAS,
    Q_COMANDOS,
    Q_JOBS_GERAR,
    Q_JOBS_TREINAR,
    Q_DLQ,
]

# Para a pagina Mensageria: quem consome cada fila.
CONSUMIDOR_DA_FILA = {
    Q_GRAVADOR: "gravador",
    Q_INFERENCIA: "inferencia",
    Q_REGRAS: "regras",
    Q_WEBSOCKET: "api",
    Q_ALERTAS: "regras",
    Q_COMANDOS: "gateway",
    Q_JOBS_GERAR: "lab",
    Q_JOBS_TREINAR: "lab",
    Q_DLQ: "(ninguem: inspecionada pela pagina)",
}

# A zona e o tipo viram segmento de routing key. Ponto, asterisco e
# cerquilha tem significado no topic exchange, entao so passa o seguro.
_SEGMENTO = re.compile(r"[^a-zA-Z0-9_-]")


def segmento(texto: str) -> str:
    limpo = _SEGMENTO.sub("-", texto.strip())
    return limpo or "desconhecido"


def rk(prefixo: str, zona: str, tipo: str, dispositivo: str) -> str:
    return ".".join([prefixo, segmento(zona), segmento(tipo), segmento(dispositivo)])


def rk_telemetria(zona: str, tipo: str, dispositivo: str) -> str:
    return rk("telemetry", zona, tipo, dispositivo)


def rk_comando(zona: str, tipo: str, dispositivo: str) -> str:
    return rk("cmd", zona, tipo, dispositivo)


def partes(routing_key: str) -> tuple[str, str, str, str]:
    """telemetry.cozinha.gas.GAS-01 -> ("telemetry", "cozinha", "gas", "GAS-01")"""
    pedacos = routing_key.split(".")
    if len(pedacos) != 4:
        return (pedacos[0] if pedacos else "", "", "", "")
    return pedacos[0], pedacos[1], pedacos[2], pedacos[3]
