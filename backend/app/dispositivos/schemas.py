from pydantic import BaseModel, ConfigDict


class DispositivoRead(BaseModel):
    id: int
    codigo: str
    nome: str
    ativo: bool
    ambiente_id: int

    model_config = ConfigDict(from_attributes=True)

class DispositivoCreate(BaseModel):
    codigo: str
    nome: str
    ambiente_id: int
    
class DispositivoUpdate(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    ambiente_id: int | None = None
