from datetime import UTC, datetime

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.auditoria.service import registrar
from app.auth.schemas import UsuarioToken
from app.core.database import SessionLocal
from app.lab.models import Job
from app.lab.schemas import JobRead
from app.mensageria import envelope, topologia
from app.tempo_real.barramento import barramento


async def enfileirar(tipo: str, parametros: dict, usuario: UsuarioToken, ip: str | None) -> JobRead:
    """Cria o job no Postgres e publica o pedido em gg.jobs.

    A API NAO executa o job: so registra e enfileira. Quem executa e o
    servico lab, que consome q.jobs.<tipo>.
    """

    def criar() -> JobRead:
        with SessionLocal() as db:
            job = Job(tipo=tipo, parametros=parametros, usuario=usuario.usuario)
            db.add(job)
            db.commit()
            db.refresh(job)
            registrar(
                db, f"job.{tipo}", usuario.usuario, usuario.papel,
                {"job_id": job.id, "parametros": parametros}, ip,
            )
            return JobRead.model_validate(job)

    job = await run_in_threadpool(criar)
    pedido = envelope.novo("job", None, {"job_id": job.id, "tipo": tipo})
    try:
        await barramento.publicar(topologia.EX_JOBS, tipo, pedido)
    except Exception:
        # sem barramento o job nunca andaria; melhor marcar como falho do
        # que deixar "na fila" para sempre
        def falhar():
            with SessionLocal() as db:
                registro = db.get(Job, job.id)
                registro.status = "falhou"
                registro.erro = "RabbitMQ indisponível ao enfileirar"
                registro.concluido_em = datetime.now(UTC)
                db.commit()

        await run_in_threadpool(falhar)
        raise
    return job


def listar(tipo: str | None, limite: int) -> list[Job]:
    with SessionLocal() as db:
        consulta = select(Job).order_by(Job.id.desc()).limit(limite)
        if tipo:
            consulta = consulta.where(Job.tipo == tipo)
        return list(db.scalars(consulta).all())
