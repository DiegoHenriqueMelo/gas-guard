from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# A zona vira um segmento da routing key do RabbitMQ, entao so letras
# minusculas, numeros e hifen (ponto, * e # tem significado no topic).
PADRAO_ZONA = r"^[a-z0-9-]{2,40}$"


class AmbienteRead(BaseModel):
    id: int
    nome: str
    zona: str
    descricao: str | None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class AmbienteCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    # opcional: se nao vier, e gerada a partir do nome
    zona: str | None = Field(default=None, pattern=PADRAO_ZONA)
    descricao: str | None = Field(default=None, max_length=255)


class AmbienteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    zona: str | None = Field(default=None, pattern=PADRAO_ZONA)
    descricao: str | None = Field(default=None, max_length=255)
