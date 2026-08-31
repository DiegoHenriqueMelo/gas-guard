import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from app.leituras.schemas import LeituraIn
from app.leituras.service import processar_leitura
from pydantic import ValidationError

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    print(f"MQTT: conectado ({reason_code})")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, message):
    texto = message.payload.decode()
    
    try:
        leitura = LeituraIn.model_validate_json(texto)
    except ValidationError as erro:
        print(f"payload invalido em {message.topic}: {erro}")
        return

    
    print(f"{leitura.codigo} -> {leitura.ppm} ppm")
    
    processar_leitura(leitura)

def criar_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gasguard-backend")
    client.enable_logger()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT)
    return client


if __name__ == "__main__":
    client = criar_client()
    client.loop_forever()
