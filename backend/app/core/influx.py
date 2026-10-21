"""InfluxDB: leituras dos sensores e previsoes da IA (series temporais).

Dois buckets, para nao misturar o que e real com o que e sintetico:
  sensores -- telemetria ao vivo e insights da IA
  lab      -- amostra dos dados gerados no Laboratorio

Modelo dos pontos:
  measurement "telemetria"
    tags   dispositivo, tipo, zona      (indexadas, poucos valores)
    fields ppm, temperatura, vibracao... e "estado"/"acionado" nos atuadores
  measurement "insights"
    tags   dispositivo, zona
    fields saude, rul_horas, inclinacao_saude
"""

import logging
from datetime import datetime

from influxdb_client import BucketRetentionRules, InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from app.core import config

log = logging.getLogger(__name__)

MEDIDA_TELEMETRIA = "telemetria"
MEDIDA_INSIGHTS = "insights"
MEDIDA_LAB_EXAUSTOR = "sintetico_exaustor"
MEDIDA_LAB_AMBIENTE = "sintetico_ambiente"

# Estados de atuador que contam como "acionado" (vira 1 no grafico).
ESTADOS_ACIONADOS = {"ligado", "aberta", "manutencao"}

_cliente: InfluxDBClient | None = None


def cliente() -> InfluxDBClient:
    """Cliente unico por processo, criado no primeiro uso."""
    global _cliente
    if _cliente is None:
        _cliente = InfluxDBClient(
            url=config.INFLUX_URL,
            token=config.obrigatoria("INFLUX_TOKEN"),
            org=config.INFLUX_ORG,
            timeout=15_000,
        )
    return _cliente


def gravar(pontos: list[Point], bucket: str | None = None) -> None:
    """Escrita SINCRONA: volta so depois de gravar, e levanta excecao se
    falhar. O modo padrao da biblioteca (em lote) engole erros calado - e o
    consumidor daria ack numa mensagem que nunca chegou ao banco."""
    if not pontos:
        return
    api = cliente().write_api(write_options=SYNCHRONOUS)
    api.write(bucket=bucket or config.INFLUX_BUCKET, org=config.INFLUX_ORG, record=pontos)


def ponto_telemetria(
    dispositivo: str, zona: str, tipo: str, instante: datetime,
    leituras: dict, estado: str | None,
) -> Point | None:
    ponto = (
        Point(MEDIDA_TELEMETRIA)
        .tag("dispositivo", dispositivo)
        .tag("tipo", tipo)
        .tag("zona", zona)
        .time(instante)
    )
    tem_campo = False
    for campo, valor in leituras.items():
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            ponto.field(campo, float(valor))
            tem_campo = True
    if estado:
        ponto.field("estado", str(estado))
        ponto.field("acionado", 1.0 if estado in ESTADOS_ACIONADOS else 0.0)
        tem_campo = True
    return ponto if tem_campo else None


def ponto_insight(dispositivo: str, zona: str, instante: datetime, conteudo: dict) -> Point | None:
    if conteudo.get("saude") is None:
        return None
    ponto = (
        Point(MEDIDA_INSIGHTS)
        .tag("dispositivo", dispositivo)
        .tag("zona", zona)
        .time(instante)
        .field("saude", float(conteudo["saude"]))
    )
    for campo in ("rul_horas", "inclinacao_saude"):
        if conteudo.get(campo) is not None:
            ponto.field(campo, float(conteudo[campo]))
    return ponto


def _janela(minutos: int) -> str:
    """Agrega em janelas para devolver no maximo ~400 pontos por periodo.
    Sem isso, 24 h de leituras a cada 2 s seriam 43 mil pontos no grafico."""
    if minutos <= 15:
        return ""
    segundos = max(5, int(minutos * 60 / 400))
    return f'|> aggregateWindow(every: {segundos}s, fn: mean, createEmpty: false)'


def historico(codigo: str, minutos: int, medida: str = MEDIDA_TELEMETRIA) -> list[dict]:
    """Serie de um dispositivo: [{"horario": ..., "ppm": ..., ...}, ...].

    O Flux e montado por interpolacao de texto. Quem chama TEM de ter
    validado o `codigo` contra o cadastro antes (e o que o service faz) -
    assim um texto arbitrario nunca chega na consulta.
    """
    consulta = f'''
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -{int(minutos)}m)
  |> filter(fn: (r) => r._measurement == "{medida}" and r.dispositivo == "{codigo}")
  |> filter(fn: (r) => r._field != "estado")
  {_janela(minutos)}
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
    tabelas = cliente().query_api().query(consulta, org=config.INFLUX_ORG)

    ignorar = {"result", "table", "_start", "_stop", "_time", "_measurement",
               "dispositivo", "tipo", "zona"}
    pontos: list[dict] = []
    for tabela in tabelas:
        for registro in tabela.records:
            linha = {"horario": registro.get_time()}
            for chave, valor in registro.values.items():
                if chave not in ignorar and isinstance(valor, (int, float)):
                    linha[chave] = valor
            pontos.append(linha)
    pontos.sort(key=lambda linha: linha["horario"])
    return pontos


def garantir_bucket(nome: str) -> None:
    """Cria o bucket se nao existir, sem prazo de retencao.

    O init do Influx so cria o primeiro bucket, e so num volume vazio; o
    "lab" nasce aqui. Sem prazo porque o dataset sintetico cobre ate um ano
    para tras: com retencao de 30 dias o Influx recusaria os pontos antigos.
    """
    sem_prazo = [BucketRetentionRules(type="expire", every_seconds=0)]  # 0 = infinito
    api = cliente().buckets_api()
    bucket = api.find_bucket_by_name(nome)
    if bucket is None:
        api.create_bucket(bucket_name=nome, retention_rules=sem_prazo, org=config.INFLUX_ORG)
        log.info("bucket %s criado no InfluxDB", nome)
    elif any(regra.every_seconds for regra in bucket.retention_rules or []):
        bucket.retention_rules = sem_prazo
        api.update_bucket(bucket)
        log.info("bucket %s agora sem prazo de retencao", nome)


def apagar_serie_lab(dataset: str) -> None:
    """Remove a amostra anterior de um dataset antes de gravar de novo."""
    api = cliente().delete_api()
    api.delete(
        start="1970-01-01T00:00:00Z",
        stop="2100-01-01T00:00:00Z",
        predicate=f'dataset="{dataset}"',
        bucket=config.INFLUX_BUCKET_LAB,
        org=config.INFLUX_ORG,
    )
