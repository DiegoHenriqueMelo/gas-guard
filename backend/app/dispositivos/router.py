from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dispositivos import service
from app.dispositivos.exceptions import (
    AmbienteNaoEncontrado,
    CodigoJaCadastrado,
    DispositivoNaoEncontrado,
    NomeJaCadastrado,
)
from app.dispositivos.schemas import (
    DispositivoCreate,
    DispositivoRead,
    DispositivoUpdate,
)

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

@router.get("", response_model=list[DispositivoRead])
def listar_dispositivos(    
    db: Session = Depends(get_db)
):
    return service.listar_dispositivos(db)

@router.get("/{codigo}", response_model=DispositivoRead)
def buscar_por_codigo(codigo: str,db: Session = Depends(get_db) ):
    try:
        return service.buscar_por_codigo(codigo, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
@router.patch("/{codigo}", response_model=DispositivoRead)
def editar_dispositivo(codigo:str, dados: DispositivoUpdate, db:Session = Depends(get_db)):
    try:
        return service.editar_dispositivo(codigo, dados, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=400, detail="Ambiente não encontrado")
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Nome ja Cadastrado")
    except CodigoJaCadastrado:
        raise HTTPException(status_code=409, detail="Código já cadastrado")
    
@router.delete("/{codigo}", response_model=DispositivoRead)
def excluir_dispositivo(codigo:str, db:Session = Depends(get_db)):
    try:
        return service.excluir_dispositivo(codigo, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")