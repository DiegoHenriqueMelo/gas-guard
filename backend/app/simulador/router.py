"""Comandos para o proprio simulador (o "dispositivo" da 2a entrega).

Fazem o mesmo caminho de um comando de atuador:
    API -> gg.comandos -> gateway -> MQTT gasguard/SIMULADOR/comando -> simulador

E assim que se injeta uma falha no exaustor, um vazamento de gas ou se
pausa o simulador durante a apresentacao.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.auditoria.service import registrar_fora_de_request
from app.auth.deps import exige, ip_do_cliente
from app.auth.schemas import UsuarioToken
from app.mensageria import envelope, topologia
from app.tempo_real.barramento import barramento
from comum.fisica import MODOS_FALHA

router = APIRouter(prefix="/api/simulador", tags=["simulador"])

DISPOSITIVO = "SIMULADOR"


class InjetarFalha(BaseModel):
    acao: Literal["injetar_falha"]
    equipamento: str = "EXAUSTOR-01"
    modo: Literal[MODOS_FALHA] = "rolamento"  # type: ignore[valid-type]
    # horas de OPERACAO ate a falha (1 leitura ao vivo = 5 min de operacao,
    # entao 20 h passam em ~5 min de apresentacao). Fica dentro do que o
    # Laboratorio gera (1 a 4 dias de degradacao), senao o modelo ve ao vivo
    # um desgaste mais rapido do que qualquer um que estudou.
    horas_ate_falha: float = Field(default=20.0, ge=1, le=96)
    # quanto da degradacao ja "aconteceu" quando a falha e injetada
    progresso_inicial: float = Field(default=0.35, ge=0, le=0.9)


class Reparar(BaseModel):
    acao: Literal["reparar"]
    equipamento: str = "EXAUSTOR-01"


class Vazamento(BaseModel):
    acao: Literal["vazamento"]
    intensidade: float = Field(ge=0, le=1, description="0 para o vazamento, 1 e o maximo")


class Relogio(BaseModel):
    acao: Literal["relogio"]
    fator: float = Field(ge=1, le=1440, description="1 = tempo real; 120 = um dia em 12 min")


class Pausa(BaseModel):
    acao: Literal["pausar", "retomar"]


ComandoSimulador = InjetarFalha | Reparar | Vazamento | Relogio | Pausa


class ComandoSimuladorIn(BaseModel):
    comando: ComandoSimulador = Field(discriminator="acao")


@router.post("/comandos", status_code=202)
async def comandar_simulador(
    dados: ComandoSimuladorIn,
    request: Request,
    usuario: UsuarioToken = Depends(exige("operador")),
):
    parametros = dados.comando.model_dump()
    acao = parametros.pop("acao")
    mensagem = envelope.novo(
        "comando",
        DISPOSITIVO,
        {"zona": "sistema", "tipo": "simulador", "acao": acao, "parametros": parametros,
         "origem": "web", "usuario": usuario.usuario},
    )
    rk = topologia.rk_comando("sistema", "simulador", DISPOSITIVO)
    await barramento.publicar(topologia.EX_COMANDOS, rk, mensagem)
    await run_in_threadpool(
        registrar_fora_de_request, f"simulador.{acao}", usuario=usuario.usuario,
        papel=usuario.papel, detalhe=parametros, ip=ip_do_cliente(request),
    )
    return {"id": mensagem.id, "acao": acao, "parametros": parametros, "routing_key": rk}
