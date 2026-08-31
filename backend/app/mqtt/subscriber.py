import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    print(f"MQTT: conectado ({reason_code})")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, message):
    print(message.payload.decode())


def criar_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gasguard-backend")

    # ➍ pendurar as duas funcoes acima no client (repare: sem parenteses)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT)
    return client


if __name__ == "__main__":
    client = criar_client()
    client.loop_forever()
