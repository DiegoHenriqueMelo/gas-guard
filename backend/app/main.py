from fastapi import FastAPI

from app.dispositivos.router import router as dispositivos_router

app = FastAPI()


@app.get("/")
def home():
    return "Minha API está no ar"


app.include_router(dispositivos_router)
