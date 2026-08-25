from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dispositivos import service
from app.dispositivos.exceptions import AmbienteNaoEncontrado, CodigoJaCadastrado
from app.dispositivos.schemas import DispositivoCreate, DispositivoRead

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])


@router.post("", response_model=DispositivoRead, status_code=201)
def criar_dispositivo(
    dados: DispositivoCreate,
    db: Session = Depends(get_db),
):
    try:
        return service.criar_dispositivo(db, dados)
    except CodigoJaCadastrado:
        raise HTTPException(status_code=409, detail="Código já cadastrado")
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=400, detail="Ambiente não encontrado")
