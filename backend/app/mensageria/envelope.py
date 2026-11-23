"""O formato unico de toda mensagem que passa pelo RabbitMQ.

Telemetria, comando, previsao da IA, alerta, progresso de job: tudo viaja
dentro do mesmo envelope de cinco campos. Quem consome sempre sabe ler o
cabecalho, e so o `conteudo` muda conforme o `tipo`.

    {
      "id": "6f1c...",                      identificador unico (uuid4)
      "instante": "2026-11-16T19:02:11Z",   quando aconteceu, em UTC
      "tipo": "telemetria",                 o que e esta mensagem
      "dispositivo": "GAS-01",              de quem e (ou null)
      "conteudo": {...}                     o resto, depende do tipo
    }
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# Os tipos que existem no sistema. Envelope com outro tipo e rejeitado.
TIPOS = {
    "telemetria",   # leitura de sensor, estado de atuador (gateway)
    "comando",      # pedido para um atuador ou para o simulador (api, regras)
    "insight",      # saude e vida util prevista (inferencia)
    "alerta",       # abertura ou fechamento de alerta (inferencia, regras)
    "acionamento",  # uma regra disparou (regras)
    "job",          # pedido de geracao de dados ou treino (api)
    "progresso",    # andamento de um job (lab)
    "modelo",       # modelo novo publicado ou ativado (lab, api)
}


class MensagemInvalida(Exception):
    """A mensagem nao tem o formato esperado. Vai para a DLQ, sem retentar:
    reprocessar uma mensagem mal formada daria o mesmo erro para sempre."""


class Envelope(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    instante: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tipo: str
    dispositivo: str | None = None
    conteudo: dict[str, Any] = Field(default_factory=dict)

    def para_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    def para_dict(self) -> dict:
        return json.loads(self.model_dump_json())


def novo(tipo: str, dispositivo: str | None, conteudo: dict) -> Envelope:
    if tipo not in TIPOS:
        raise ValueError(f"tipo de envelope desconhecido: {tipo}")
    return Envelope(tipo=tipo, dispositivo=dispositivo, conteudo=conteudo)


def ler(corpo: bytes, tipo_esperado: str | set[str] | None = None) -> Envelope:
    """Valida os bytes que chegaram da fila. Levanta MensagemInvalida."""
    try:
        envelope = Envelope.model_validate_json(corpo)
    except ValidationError as erro:
        raise MensagemInvalida(f"envelope mal formado: {erro.errors()[:2]}") from erro

    if envelope.tipo not in TIPOS:
        raise MensagemInvalida(f"tipo desconhecido: {envelope.tipo}")

    if tipo_esperado is not None:
        esperados = {tipo_esperado} if isinstance(tipo_esperado, str) else tipo_esperado
        if envelope.tipo not in esperados:
            raise MensagemInvalida(
                f"esperava {sorted(esperados)}, chegou {envelope.tipo}"
            )

    return envelope
