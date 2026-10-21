"""Lab: executa os jobs demorados que a API so enfileira.

    POST /api/lab/jobs    -> gg.jobs "gerar"   -> q.jobs.gerar   -> aqui
    POST /api/treino/jobs -> gg.jobs "treinar" -> q.jobs.treinar -> aqui

Por que fila e nao rodar dentro da API? Gerar milhoes de leituras e treinar
modelos leva de segundos a minutos de CPU. Dentro da API, a request ficaria
pendurada e o processo deixaria de atender todo o resto. Com a fila, a API
responde 202 na hora e a interface acompanha o progresso pelo WebSocket.

Um job por vez (trava): os dois tipos disputam a mesma CPU, e um treino
rodando junto de uma geracao so deixaria os dois mais lentos.

O ack so sai quando o job termina. Se o container cair no meio, a mensagem
volta para a fila; na reentrega o job e marcado como falho e vai para a DLQ
(rodar de novo derrubaria o servico de novo, em loop).
"""

import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy import func, select

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.auditoria.service import registrar_fora_de_request
from app.core.database import SessionLocal
from app.ia.models import Modelo
from app.ia.treino import treinar
from app.lab.gerador import gerar
from app.lab.models import Job
from app.lab.schemas import ParametrosGeracao, ParametrosTreino
from app.mensageria import envelope, topologia
from app.mensageria.conexao import Publicador, conectar, consumir
from app.servicos.base import batimento, configurar_log, rodar

log = configurar_log("lab")


def _atualizar_job(job_id: int, **campos) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        for campo, valor in campos.items():
            setattr(job, campo, valor)
        db.commit()


def _registrar_modelo(job: Job, resultado: dict) -> bool:
    """Grava a versao nova. Ativa sozinha so se vencer a base nos dois alvos."""
    with SessionLocal() as db:
        modelo = Modelo(
            versao=resultado["versao"],
            job_id=job.id,
            dataset_job_id=job.parametros["dataset_job_id"],
            caminho=resultado["caminho"],
            metricas=resultado,
            venceu_base=resultado["venceu_base"],
        )
        db.add(modelo)
        ativar = resultado["venceu_base"]
        if ativar:
            db.query(Modelo).filter(Modelo.ativo.is_(True)).update({"ativo": False})
            modelo.ativo = True
        db.commit()
        return ativar


def _proxima_versao() -> str:
    with SessionLocal() as db:
        quantos = db.scalar(select(func.count()).select_from(Modelo)) or 0
    return f"v{quantos + 1}"


async def principal(parar: asyncio.Event) -> None:
    conexao = await conectar("lab")
    canal = await conexao.channel()
    await canal.set_qos(prefetch_count=1)
    publicador = Publicador(canal)
    trava = asyncio.Lock()
    loop = asyncio.get_running_loop()

    async def avisar(job: Job, status: str, progresso: float, etapa: str, extra: dict | None = None):
        conteudo = {"job_id": job.id, "tipo": job.tipo, "status": status,
                    "progresso": round(progresso, 3), "etapa": etapa, **(extra or {})}
        await publicador.publicar(
            topologia.EX_EVENTOS,
            f"job.{job.tipo}.{job.id}",
            envelope.novo("progresso", None, conteudo),
            persistente=False,
        )

    def acompanhante(job: Job):
        """Callback chamado DE DENTRO da thread do job. No maximo duas
        atualizacoes por segundo, para nao inundar o banco nem a fila."""
        ultimo = {"t": 0.0}

        def progresso(fracao: float, etapa: str) -> None:
            agora = time.monotonic()
            if agora - ultimo["t"] < 0.5 and fracao < 1.0:
                return
            ultimo["t"] = agora
            _atualizar_job(job.id, progresso=fracao, etapa=etapa)
            # a thread nao pode usar o loop do asyncio direto: entrega a
            # publicacao para ele com run_coroutine_threadsafe
            asyncio.run_coroutine_threadsafe(avisar(job, "executando", fracao, etapa), loop)

        return progresso

    async def ao_receber_job(mensagem: envelope.Envelope, bruta) -> None:
        job_id = mensagem.conteudo.get("job_id")
        if not isinstance(job_id, int):
            raise envelope.MensagemInvalida("job sem job_id")

        def carregar():
            with SessionLocal() as db:
                return db.get(Job, job_id)

        job = await asyncio.to_thread(carregar)
        if job is None:
            raise envelope.MensagemInvalida(f"job {job_id} nao existe")
        if job.status in ("concluido", "falhou"):
            log.info("job %s ja estava %s; ignorado", job_id, job.status)
            return

        if bruta.redelivered:
            await asyncio.to_thread(
                _atualizar_job, job_id, status="falhou", concluido_em=datetime.now(UTC),
                erro="o servico lab caiu durante o job; reentrega recusada",
            )
            await avisar(job, "falhou", job.progresso, "o servico caiu no meio do job")
            raise envelope.MensagemInvalida("job reentregue depois de queda")

        async with trava:
            await asyncio.to_thread(
                _atualizar_job, job_id, status="executando", iniciado_em=datetime.now(UTC),
                etapa="começando",
            )
            await avisar(job, "executando", 0.0, "começando")
            log.info("job %s (%s) comecou", job_id, job.tipo)

            try:
                if job.tipo == "gerar":
                    parametros = ParametrosGeracao.model_validate(job.parametros)
                    resultado = await asyncio.to_thread(gerar, job_id, parametros, acompanhante(job))
                else:
                    parametros = ParametrosTreino.model_validate(job.parametros)
                    versao = await asyncio.to_thread(_proxima_versao)
                    resultado = await asyncio.to_thread(
                        treinar, versao, parametros.dataset_job_id, parametros.max_linhas,
                        acompanhante(job),
                    )
            except Exception as erro:
                log.exception("job %s falhou", job_id)
                await asyncio.to_thread(
                    _atualizar_job, job_id, status="falhou", concluido_em=datetime.now(UTC),
                    erro=f"{type(erro).__name__}: {erro}"[:1000],
                )
                await avisar(job, "falhou", job.progresso, str(erro)[:200])
                # Erro de job e deterministico (parametro ruim, dataset que
                # nao existe): tentar de novo daria o mesmo erro. Vai para a
                # DLQ direto, com a mensagem original preservada.
                raise envelope.MensagemInvalida(f"job {job_id} falhou: {erro}") from erro

            extra = {}
            if job.tipo == "treinar":
                ativou = await asyncio.to_thread(_registrar_modelo, job, resultado)
                extra = {"versao": resultado["versao"], "ativado": ativou,
                         "venceu_base": resultado["venceu_base"]}
                resultado = {"versao": resultado["versao"], "venceu_base": resultado["venceu_base"],
                             "ativado": ativou, "segundos": resultado["segundos"]}
                await publicador.publicar(
                    topologia.EX_EVENTOS, "modelo.publicado",
                    envelope.novo("modelo", None, extra),
                )

            await asyncio.to_thread(
                _atualizar_job, job_id, status="concluido", progresso=1.0, etapa="concluído",
                resultado=resultado, concluido_em=datetime.now(UTC),
            )
            await avisar(job, "concluido", 1.0, "concluído", extra)
            await asyncio.to_thread(
                registrar_fora_de_request, f"job.{job.tipo}.concluido",
                usuario=job.usuario, detalhe={"job_id": job_id, **extra},
            )
            log.info("job %s concluido", job_id)

    await consumir(canal, topologia.Q_JOBS_GERAR, ao_receber_job, tipo_esperado="job")
    await consumir(canal, topologia.Q_JOBS_TREINAR, ao_receber_job, tipo_esperado="job")

    tarefa = asyncio.create_task(batimento(lambda: not conexao.is_closed))
    await parar.wait()
    tarefa.cancel()
    await conexao.close()


if __name__ == "__main__":
    rodar(principal)
