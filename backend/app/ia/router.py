from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria.service import registrar
from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core import influx
from app.core.database import get_db
from app.dispositivos.exceptions import DispositivoNaoEncontrado
from app.ia.models import Configuracao, Modelo
from app.lab import service as jobs
from app.lab.models import Job
from app.lab.schemas import JobRead, ParametrosTreino
from app.leituras.service import listar_historico
from app.mensageria import envelope, topologia
from app.tempo_real.barramento import barramento
from app.tempo_real.hub import hub

router = APIRouter(tags=["inteligência artificial"], dependencies=[Depends(usuario_atual)])


class ModeloResumo(BaseModel):
    id: int
    versao: str
    job_id: int | None
    dataset_job_id: int | None
    venceu_base: bool
    ativo: bool
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ModeloDetalhe(ModeloResumo):
    metricas: dict[str, Any]


class ConfiguracaoRead(BaseModel):
    chave: str
    valor: float
    descricao: str
    atualizado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfiguracaoUpdate(BaseModel):
    valor: float


# ---------- treinamento ----------


@router.post("/api/treino/jobs", response_model=JobRead, status_code=202)
async def treinar(
    parametros: ParametrosTreino,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    dataset = db.get(Job, parametros.dataset_job_id)
    if dataset is None or dataset.tipo != "gerar" or dataset.status != "concluido":
        raise HTTPException(status_code=422, detail="Escolha um dataset gerado com sucesso")
    return await jobs.enfileirar("treinar", parametros.model_dump(), usuario, ip_do_cliente(request))


@router.get("/api/modelos", response_model=list[ModeloResumo])
def listar_modelos(db: Session = Depends(get_db)):
    return list(db.scalars(select(Modelo).order_by(Modelo.id.desc())).all())


@router.get("/api/modelos/{versao}", response_model=ModeloDetalhe)
def detalhar_modelo(versao: str, db: Session = Depends(get_db)):
    modelo = db.scalars(select(Modelo).where(Modelo.versao == versao)).first()
    if modelo is None:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return modelo


@router.post("/api/modelos/{versao}/ativar", response_model=ModeloResumo)
async def ativar_modelo(
    versao: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    """Coloca outra versao em uso. A inferencia percebe em ate 5 s, sem reiniciar."""
    modelo = db.scalars(select(Modelo).where(Modelo.versao == versao)).first()
    if modelo is None:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")

    db.query(Modelo).filter(Modelo.ativo.is_(True)).update({"ativo": False})
    modelo.ativo = True
    db.commit()
    registrar(db, "modelo.ativado", usuario.usuario, usuario.papel, {"versao": versao},
              ip_do_cliente(request))

    await barramento.publicar(
        topologia.EX_EVENTOS, "modelo.ativado",
        envelope.novo("modelo", None, {"versao": versao, "ativado": True, "por": usuario.usuario}),
    )
    db.refresh(modelo)
    return modelo


# ---------- insights ----------


@router.get("/api/insights")
def insights_atuais():
    """Ultima previsao de cada equipamento (a mesma que vai pelo WebSocket)."""
    return hub.insights


@router.get("/api/insights/{codigo}/historico", response_model=list[dict[str, Any]])
def historico_insights(
    codigo: str,
    minutos: int = Query(default=60, ge=1, le=10080),
    db: Session = Depends(get_db),
):
    try:
        return listar_historico(db, codigo, minutos, medida=influx.MEDIDA_INSIGHTS)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")


# ---------- limites da IA ----------


@router.get("/api/configuracoes", response_model=list[ConfiguracaoRead])
def listar_configuracoes(db: Session = Depends(get_db)):
    return list(db.scalars(select(Configuracao).order_by(Configuracao.chave)).all())


@router.put("/api/configuracoes/{chave}", response_model=ConfiguracaoRead)
def editar_configuracao(
    chave: str,
    dados: ConfiguracaoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    configuracao = db.get(Configuracao, chave)
    if configuracao is None:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    anterior = configuracao.valor
    configuracao.valor = dados.valor
    db.commit()
    registrar(db, "configuracao.editada", usuario.usuario, usuario.papel,
              {"chave": chave, "de": anterior, "para": dados.valor}, ip_do_cliente(request))
    db.refresh(configuracao)
    return configuracao
