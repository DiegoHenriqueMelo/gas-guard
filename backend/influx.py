import os
from pathlib import Path

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

if not all([INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
    raise RuntimeError("Variaveis INFLUX_* incompletas no .env")

# nome do measurement em UM lugar so - evita "leituras" vs "Leituras"
MEASUREMENT = "leituras"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

# SYNCHRONOUS: cada write vai na hora e levanta excecao se falhar.
# O padrao da lib e em lote (batching), que engole erros silenciosamente.
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

def gravar_leitura(device_id:str, ppm:float):
    point = Point(MEASUREMENT).tag("device_id", device_id).field("ppm", float(ppm))
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=  point)


def ler_ultimas_leituras(device_id: str, minutos: int = 60) -> list[tuple]:
    """Devolve [(horario, ppm), ...] das ultimas N leituras de um dispositivo."""
    consulta = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -{minutos}m)
      |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
      |> filter(fn: (r) => r.device_id == "{device_id}")
    '''

    tabelas = query_api.query(consulta, org=INFLUX_ORG)

    return [
        (registro.get_time(), registro.get_value())
        for tabela in tabelas
        for registro in tabela.records
    ]
