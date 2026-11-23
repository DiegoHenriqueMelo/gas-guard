from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.alertas import service
from app.auth.deps import usuario_atual
from app.core.database import get_db

router = APIRouter(prefix="/api/alertas", tags=["alertas"], dependencies=[Depends(usuario_atual)])


class AlertaRead(BaseModel):
    id: int
    dispositivo_codigo: str
    chave: str
    origem: str
    severidade: str
    mensagem: str
    valor: float | None
    ativo: bool
    aberto_em: datetime
    atualizado_em: datetime
    fechado_em: datetime | None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[AlertaRead])
def listar_alertas(
    ativos: bool = Query(default=False, description="só os que ainda estão abertos"),
    limite: int = Query(default=50, ge=1, le=500),
    dispositivo: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
):
    return service.listar(db, ativos, limite, dispositivo)
