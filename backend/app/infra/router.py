from fastapi import APIRouter, Depends

from app.assistente import ollama
from app.auth.deps import usuario_atual
from app.core import config
from app.tempo_real.barramento import barramento
from app.tempo_real.hub import hub

router = APIRouter(prefix="/api/infra", tags=["infraestrutura"], dependencies=[Depends(usuario_atual)])


@router.get("")
async def infraestrutura():
    """Links das interfaces de administracao e um retrato rapido da saude.

    As interfaces do RabbitMQ, InfluxDB e Adminer (PostgreSQL) so escutam em
    127.0.0.1: abrem na maquina da apresentacao, nao na rede da sala.
    """
    sem_dados = hub.segundos_sem_telemetria()
    return {
        "interfaces": [
            {"nome": "RabbitMQ (gerenciamento)", "url": config.LINK_RABBITMQ,
             "uso": "filas, exchanges, consumidores; usuário gg_admin"},
            {"nome": "InfluxDB", "url": config.LINK_INFLUX,
             "uso": "Data Explorer: buckets sensores (ao vivo) e lab (sintético)"},
            {"nome": "Adminer (PostgreSQL)", "url": config.LINK_ADMINER,
             "uso": "servidor postgres, banco gasguard: cadastro, regras, alertas, auditoria"},
            {"nome": "Documentação da API (Swagger)", "url": "/api/docs",
             "uso": "todas as rotas REST; botão Authorize para testar logado"},
        ],
        "situacao": {
            "rabbitmq": barramento.pronto,
            "websocket_clientes": len(hub.clientes),
            "mensagens_recebidas": hub.recebidas,
            "segundos_sem_telemetria": None if sem_dados is None else round(sem_dados, 1),
            "llm": await ollama.situacao(),
        },
    }
