from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auditoria import service
from app.auth.deps import exige
from app.core.database import get_db

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])


class AuditoriaRead(BaseModel):
    id: int
    instante: datetime
    usuario: str | None
    papel: str | None
    acao: str
    detalhe: dict
    ip: str | None
    sucesso: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[AuditoriaRead], dependencies=[Depends(exige("administrador"))])
def listar_auditoria(
    limite: int = Query(default=100, ge=1, le=500),
    acao: str | None = Query(default=None, max_length=60),
    usuario: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
):
    """Ultimos registros de auditoria. `acao` filtra por prefixo (ex.: "login")."""
    return service.listar(db, limite, acao, usuario)
