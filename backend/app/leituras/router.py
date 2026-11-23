from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import usuario_atual
from app.core.database import get_db
from app.dispositivos.exceptions import DispositivoNaoEncontrado
from app.leituras import service

router = APIRouter(
    prefix="/api/leituras", tags=["leituras"], dependencies=[Depends(usuario_atual)]
)


@router.get("/{codigo}", response_model=list[dict[str, Any]])
def historico_por_dispositivo(
    codigo: str,
    minutos: int = Query(default=60, ge=1, le=10080),
    db: Session = Depends(get_db),
):
    """Serie temporal de um dispositivo nos ultimos N minutos, lida do InfluxDB.

    Cada ponto traz todos os campos daquele dispositivo:
    `{"horario": "...", "ppm": 312.5}` ou
    `{"horario": "...", "vibracao": 1.9, "corrente": 3.8, ...}`.
    Acima de 15 minutos os pontos sao medias por janela (no maximo ~400).
    """
    try:
        return service.listar_historico(db, codigo, minutos)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
