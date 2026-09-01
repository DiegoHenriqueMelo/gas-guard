from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ambientes import service
from app.ambientes.exceptions import (
    AmbienteNaoEncontrado,
    AmbientePossuiDispositivos,
    NomeJaCadastrado,
)
from app.ambientes.schemas import AmbienteCreate, AmbienteRead, AmbienteUpdate
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
        raise HTTPException(status_code=409, detail="Já existe um ambiente com esse nome")


@router.get("", response_model=list[AmbienteRead])
def listar_ambientes(db: Session = Depends(get_db)):
    return service.listar_ambientes(db)


@router.get("/{ambiente_id}", response_model=AmbienteRead)
def buscar_ambiente(ambiente_id: int, db: Session = Depends(get_db)):
    try:
        return service.buscar_ambiente(db, ambiente_id)
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")


@router.patch("/{ambiente_id}", response_model=AmbienteRead)
def editar_ambiente(
    ambiente_id: int,
    dados: AmbienteUpdate,
    db: Session = Depends(get_db),
):
    try:
        return service.editar_ambiente(db, ambiente_id, dados)
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Já existe um ambiente com esse nome")


@router.delete("/{ambiente_id}", response_model=AmbienteRead)
def excluir_ambiente(ambiente_id: int, db: Session = Depends(get_db)):
    try:
        return service.excluir_ambiente(db, ambiente_id)
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    except AmbientePossuiDispositivos:
        raise HTTPException(
            status_code=409,
            detail="Ambiente possui dispositivos e não pode ser excluído",
        )
