"""A conexao da API com o RabbitMQ.

A API publica comandos, jobs e eventos, e consome a fila q.websocket para
entregar tudo ao navegador. A conexao abre em segundo plano no lifespan:
se o broker ainda nao subiu, a API responde normalmente e so as rotas que
publicam devolvem 503 ate a conexao ficar pronta.
"""

import logging

from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from fastapi import HTTPException

from app.mensageria.conexao import Publicador, conectar
from app.mensageria.envelope import Envelope

log = logging.getLogger(__name__)


class Barramento:
    def __init__(self) -> None:
        self.conexao: AbstractRobustConnection | None = None
        self.canal: AbstractChannel | None = None
        self.publicador: Publicador | None = None

    async def iniciar(self) -> None:
        self.conexao = await conectar("api")
        self.canal = await self.conexao.channel()
        self.publicador = Publicador(self.canal)

    @property
    def pronto(self) -> bool:
        return self.conexao is not None and not self.conexao.is_closed

    async def publicar(self, exchange: str, routing_key: str, mensagem: Envelope) -> None:
        if self.publicador is None or not self.pronto:
            raise HTTPException(
                status_code=503, detail="Barramento (RabbitMQ) indisponível no momento"
            )
        await self.publicador.publicar(exchange, routing_key, mensagem)

    async def fechar(self) -> None:
        if self.conexao is not None:
            await self.conexao.close()


barramento = Barramento()
