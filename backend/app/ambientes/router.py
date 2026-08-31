from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ambientes import service
from app.ambientes.exceptions import NomeJaCadastrado
from app.ambientes.schemas import AmbienteCreate, AmbienteRead
from app.core.database import get_db

router = APIRouter(prefix="/api/ambientes", tags=["ambientes"])


@router.post("", response_model=AmbienteRead, status_code=201)
def criar_ambiente(
    dados: AmbienteCreate,
    db: Session = Depends(get_db),
):
    try:
        return service.criar_ambiente(db, dados)
    except NomeJaCadastrado:
        raise HTTPException(
            status_code=409,
            detail="Ja existe um ambiente com esse nome",
        )
