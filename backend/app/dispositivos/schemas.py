from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dispositivos.catalogo import TIPOS

PADRAO_CODIGO = r"^[A-Za-z0-9_-]{2,50}$"


class DispositivoRead(BaseModel):
    id: int
    codigo: str
    nome: str
    ativo: bool
    ambiente_id: int
    categoria: str
    tipo: str
    campo_principal: str | None
    unidade: str | None
    controlavel: bool
    normal_min: float | None
    normal_max: float | None
    critico_min: float | None
    critico_max: float | None
    ultimo_contato: datetime | None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class DispositivoCreate(BaseModel):
    # O codigo vira parte do topico MQTT e da routing key: sem espacos,
    # pontos, barras ou coringas.
    codigo: str = Field(pattern=PADRAO_CODIGO)
    nome: str = Field(min_length=1, max_length=100)
    ambiente_id: int
    tipo: str = "gas"
    # Os campos abaixo, se nao vierem, saem do catalogo do tipo.
    categoria: str | None = None
    campo_principal: str | None = None
    unidade: str | None = None
    controlavel: bool | None = None
    normal_min: float | None = None
    normal_max: float | None = None
    critico_min: float | None = None
    critico_max: float | None = None

    @model_validator(mode="after")
    def tipo_conhecido(self):
        if self.tipo not in TIPOS:
            raise ValueError(f"tipo deve ser um de: {', '.join(TIPOS)}")
        return self


class DispositivoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    ativo: bool | None = None
    ambiente_id: int | None = None
    campo_principal: str | None = None
    unidade: str | None = None
    normal_min: float | None = None
    normal_max: float | None = None
    critico_min: float | None = None
    critico_max: float | None = None


class ComandoIn(BaseModel):
    acao: str = Field(min_length=1, max_length=20)


class ComandoOut(BaseModel):
    id: str
    dispositivo: str
    acao: str
    routing_key: str
