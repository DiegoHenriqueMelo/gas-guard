from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria.service import registrar
from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core.database import get_db
from app.dispositivos.catalogo import ACOES_POR_TIPO
from app.dispositivos.repository import buscar_por_codigo
from app.regras.models import OPERADORES, Regra

# Regras sao lidas por qualquer um e editadas pelo administrador. O servico
# `regras` rele a tabela a cada 10 s: nao precisa reiniciar nada.
router = APIRouter(prefix="/api/regras", tags=["regras"], dependencies=[Depends(usuario_atual)])


class RegraBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    ativa: bool = True
    dispositivo_codigo: str
    campo: str = Field(min_length=1, max_length=30)
    operador: str
    limite: float
    alvo_codigo: str
    acao: str


class RegraRead(RegraBase):
    id: int
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class RegraUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    ativa: bool | None = None
    campo: str | None = None
    operador: str | None = None
    limite: float | None = None
    acao: str | None = None


def _validar(db: Session, dados: dict) -> None:
    if dados["operador"] not in OPERADORES:
        raise HTTPException(status_code=422, detail=f"Operador deve ser um de {', '.join(OPERADORES)}")
    if buscar_por_codigo(db, dados["dispositivo_codigo"]) is None:
        raise HTTPException(status_code=422, detail="Dispositivo de origem não existe")
    alvo = buscar_por_codigo(db, dados["alvo_codigo"])
    if alvo is None:
        raise HTTPException(status_code=422, detail="Atuador alvo não existe")
    permitidas = ACOES_POR_TIPO.get(alvo.tipo, ())
    if dados["acao"] not in permitidas:
        raise HTTPException(
            status_code=422,
            detail=f"{alvo.codigo} aceita: {', '.join(permitidas) or 'nenhuma ação'}",
        )


@router.get("", response_model=list[RegraRead])
def listar_regras(db: Session = Depends(get_db)):
    return list(db.scalars(select(Regra).order_by(Regra.id)).all())


@router.post("", response_model=RegraRead, status_code=201)
def criar_regra(
    dados: RegraBase,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    _validar(db, dados.model_dump())
    regra = Regra(**dados.model_dump())
    db.add(regra)
    db.commit()
    registrar(db, "regra.criada", usuario.usuario, usuario.papel,
              {"id": regra.id, **dados.model_dump()}, ip_do_cliente(request))
    db.refresh(regra)
    return regra


@router.patch("/{regra_id}", response_model=RegraRead)
def editar_regra(
    regra_id: int,
    dados: RegraUpdate,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    regra = db.get(Regra, regra_id)
    if regra is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")

    campos = dados.model_dump(exclude_unset=True)
    atual = {c: getattr(regra, c) for c in RegraBase.model_fields}
    _validar(db, {**atual, **campos})
    for campo, valor in campos.items():
        setattr(regra, campo, valor)
    db.commit()
    registrar(db, "regra.editada", usuario.usuario, usuario.papel,
              {"id": regra_id, "campos": campos}, ip_do_cliente(request))
    db.refresh(regra)
    return regra


@router.delete("/{regra_id}", status_code=204)
def excluir_regra(
    regra_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    regra = db.get(Regra, regra_id)
    if regra is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    db.delete(regra)
    db.commit()
    registrar(db, "regra.excluida", usuario.usuario, usuario.papel, {"id": regra_id},
              ip_do_cliente(request))
