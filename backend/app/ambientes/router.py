from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ambientes import service
from app.ambientes.exceptions import (
    AmbienteNaoEncontrado,
    AmbientePossuiDispositivos,
    NomeJaCadastrado,
    ZonaJaCadastrada,
)
from app.ambientes.schemas import AmbienteCreate, AmbienteRead, AmbienteUpdate
from app.auditoria.service import registrar
from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core.database import get_db

# Ler: qualquer usuario logado. Criar, editar e excluir: administrador.
router = APIRouter(
    prefix="/api/ambientes", tags=["ambientes"], dependencies=[Depends(usuario_atual)]
)


@router.post("", response_model=AmbienteRead, status_code=201)
def criar_ambiente(
    dados: AmbienteCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        ambiente = service.criar_ambiente(db, dados)
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Já existe um ambiente com esse nome")
    except ZonaJaCadastrada:
        raise HTTPException(status_code=409, detail="Já existe um ambiente com essa zona")

    registrar(
        db, "ambiente.criado", usuario.usuario, usuario.papel,
        {"id": ambiente.id, "nome": ambiente.nome}, ip_do_cliente(request),
    )
    return ambiente


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
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        ambiente = service.editar_ambiente(db, ambiente_id, dados)
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Já existe um ambiente com esse nome")
    except ZonaJaCadastrada:
        raise HTTPException(status_code=409, detail="Já existe um ambiente com essa zona")

    registrar(
        db, "ambiente.editado", usuario.usuario, usuario.papel,
        {"id": ambiente_id, "campos": dados.model_dump(exclude_unset=True)},
        ip_do_cliente(request),
    )
    return ambiente


@router.delete("/{ambiente_id}", response_model=AmbienteRead)
def excluir_ambiente(
    ambiente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        resposta = service.excluir_ambiente(db, ambiente_id)
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    except AmbientePossuiDispositivos:
        raise HTTPException(
            status_code=409,
            detail="Ambiente possui dispositivos e não pode ser excluído",
        )

    registrar(
        db, "ambiente.excluido", usuario.usuario, usuario.papel,
        {"id": ambiente_id}, ip_do_cliente(request),
    )
    return resposta
