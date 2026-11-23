import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.alertas.router import router as alertas_router
from app.ambientes.router import router as ambientes_router
from app.assistente import ollama
from app.assistente.router import router as assistente_router
from app.auditoria.router import router as auditoria_router
from app.auth.router import router as auth_router
from app.dispositivos.router import router as dispositivos_router
from app.ia.router import router as ia_router
from app.infra.router import router as infra_router
from app.lab.router import router as lab_router
from app.leituras.router import router as leituras_router
from app.mensageria import topologia
from app.mensageria.conexao import consumir
from app.mensageria.router import router as mensageria_router
from app.regras.router import router as regras_router
from app.simulador.router import router as simulador_router
from app.tempo_real.barramento import barramento
from app.tempo_real.hub import hub
from app.tempo_real.router import router as tempo_real_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [api] %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
logging.getLogger("aiormq").setLevel(logging.WARNING)
logging.getLogger("aio_pika").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("api")


async def ligar_barramento() -> None:
    """Conecta no RabbitMQ e passa a consumir q.websocket (em segundo plano)."""
    await barramento.iniciar()
    canal = await barramento.conexao.channel()
    await canal.set_qos(prefetch_count=200)
    await consumir(canal, topologia.Q_WEBSOCKET, hub.ao_receber)
    log.info("barramento pronto: publicando e consumindo %s", topologia.Q_WEBSOCKET)


async def manter_modelo_carregado() -> None:
    """Deixa o LLM na memoria assim que ele estiver baixado.

    O container ollama-init baixa o modelo na primeira subida (alguns
    minutos); ate la, a pagina Assistente mostra "baixando o modelo".
    """
    while True:
        situacao = await ollama.situacao()
        if situacao["baixado"] and not situacao["carregado"]:
            log.info("pre-carregando o modelo %s na memoria", situacao["modelo"])
            await ollama.pre_carregar()
        await asyncio.sleep(30 if situacao["carregado"] else 10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Tarefas de fundo da API. Nenhuma trava a subida: se o RabbitMQ ou o
    Ollama ainda nao estiverem prontos, a API ja responde e elas insistem."""
    tarefas = [
        asyncio.create_task(ligar_barramento()),
        asyncio.create_task(hub.gravar_contatos()),
        asyncio.create_task(manter_modelo_carregado()),
    ]
    yield
    for tarefa in tarefas:
        tarefa.cancel()
    with contextlib.suppress(Exception):
        await barramento.fechar()


# A documentacao fica em /api/docs (e nao /docs) porque o nginx do frontend
# so repassa /api e /ws para este container: e a unica porta publicada.
app = FastAPI(
    title="Gas-Guard API",
    description="AIoT de vazamento de gás e manutenção preditiva do exaustor da coifa.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.get("/api/saude", tags=["infraestrutura"])
def saude():
    """Healthcheck do container (nao exige login)."""
    return {"api": "ok", "rabbitmq": barramento.pronto}


for rota in (
    auth_router,
    ambientes_router,
    dispositivos_router,
    leituras_router,
    regras_router,
    alertas_router,
    ia_router,
    lab_router,
    simulador_router,
    mensageria_router,
    assistente_router,
    auditoria_router,
    infra_router,
    tempo_real_router,
):
    app.include_router(rota)
