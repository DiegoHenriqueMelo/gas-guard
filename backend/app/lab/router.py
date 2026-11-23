from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core import config
from app.core.database import get_db
from app.lab import service
from app.lab.models import Job
from app.lab.schemas import JobRead, ParametrosGeracao
from comum.fisica import AMOSTRA_MINUTOS, MODOS_EQUIPAMENTO, MODOS_SENSOR

router = APIRouter(prefix="/api/lab", tags=["laboratório de dados"], dependencies=[Depends(usuario_atual)])


@router.get("/opcoes")
def opcoes():
    """O que o formulario do Laboratorio precisa: padroes, modos e o teto."""
    return {
        "padrao": ParametrosGeracao().model_dump(),
        "modos_equipamento": list(MODOS_EQUIPAMENTO),
        "modos_sensor": list(MODOS_SENSOR),
        "max_leituras": config.LAB_MAX_LEITURAS,
        "amostra_minutos": AMOSTRA_MINUTOS,
    }


@router.post("/estimativa")
def estimar(parametros: ParametrosGeracao):
    estimadas = parametros.leituras_estimadas()
    return {
        "leituras": estimadas,
        "max_leituras": config.LAB_MAX_LEITURAS,
        "cabe": estimadas <= config.LAB_MAX_LEITURAS,
    }


@router.post("/jobs", response_model=JobRead, status_code=202)
async def gerar_dados(
    parametros: ParametrosGeracao,
    request: Request,
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    """Enfileira a geracao. Responde na hora; o progresso chega pelo WebSocket."""
    estimadas = parametros.leituras_estimadas()
    if estimadas > config.LAB_MAX_LEITURAS:
        raise HTTPException(
            status_code=422,
            detail=f"{estimadas:,} leituras passam do teto de {config.LAB_MAX_LEITURAS:,}".replace(",", "."),
        )
    return await service.enfileirar("gerar", parametros.model_dump(), usuario, ip_do_cliente(request))


@router.get("/jobs", response_model=list[JobRead])
def listar_jobs(
    tipo: str | None = Query(default=None, pattern="^(gerar|treinar)$"),
    limite: int = Query(default=30, ge=1, le=200),
):
    return service.listar(tipo, limite)


@router.get("/jobs/{job_id}", response_model=JobRead)
def buscar_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return job
