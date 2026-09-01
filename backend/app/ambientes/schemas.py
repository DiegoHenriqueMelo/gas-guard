from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AmbienteRead(BaseModel):
    id: int
    nome: str
    descricao: str | None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class AmbienteCreate(BaseModel):
    nome: str
    descricao: str | None = None


class AmbienteUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
