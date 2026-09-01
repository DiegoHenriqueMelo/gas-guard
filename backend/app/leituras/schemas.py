from datetime import datetime

from pydantic import BaseModel


class LeituraIn(BaseModel):
    """Payload que chega do ESP32 pelo MQTT."""

    codigo: str
    ppm: float


class LeituraOut(BaseModel):
    """Um ponto da serie temporal, como sai na API."""

    horario: datetime
    ppm: float
