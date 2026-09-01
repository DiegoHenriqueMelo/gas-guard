from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ambientes.router import router as ambientes_router
from app.dispositivos.router import router as dispositivos_router
from app.leituras.router import router as leituras_router
from app.mqtt.subscriber import criar_client

# O Vue roda noutra origem (porta 5173). Sem estes cabecalhos o navegador
# bloqueia a chamada antes mesmo dela sair. Em producao, troque pela
# origem real do frontend em vez de liberar tudo.
ORIGENS_PERMITIDAS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sobe o subscriber MQTT junto da API e o derruba junto tambem.

    loop_start() roda o cliente numa thread separada; loop_forever()
    prenderia a thread principal e o uvicorn nunca comecaria a servir.
    """
    client = criar_client()
    client.loop_start()

    yield

    client.loop_stop()
    client.disconnect()


app = FastAPI(title="Gas-Guard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return "Minha API está no ar"


app.include_router(ambientes_router)
app.include_router(dispositivos_router)
app.include_router(leituras_router)
