from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.dispositivos.router import router as dispositivos_router
from app.mqtt.subscriber import criar_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = criar_client()
    client.loop_start()
    yield
    client.loop_stop()
    client.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return "Minha API está no ar"


app.include_router(dispositivos_router)
