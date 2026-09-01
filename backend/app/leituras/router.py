from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dispositivos.exceptions import DispositivoNaoEncontrado
from app.leituras import service
from app.leituras.schemas import LeituraOut

router = APIRouter(prefix="/api/leituras", tags=["leituras"])


@router.get("/{codigo}", response_model=list[LeituraOut])
def historico_por_dispositivo(
    codigo: str,
    minutos: int = Query(default=60, ge=1, le=1440),
    db: Session = Depends(get_db),
):
    """Serie temporal de um dispositivo nos ultimos N minutos."""
    try:
        return service.listar_historico(db, codigo, minutos)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
