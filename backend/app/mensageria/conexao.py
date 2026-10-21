"""Conexao com o RabbitMQ, publicacao e consumo, iguais para todo servico.

Usamos aio-pika (asyncio). O `connect_robust` reconecta sozinho quando o
broker cai e volta, e refaz os consumidores - importante na apresentacao,
quando alguem reinicia um container no meio da demonstracao.

A regra de erro e a mesma em todas as filas, e esta toda em consumir():

- deu certo                     -> ack: a mensagem sai da fila
- MensagemInvalida              -> reject sem requeue: vai direto para a DLQ
                                   (tentar de novo daria o mesmo erro)
- outro erro, primeira vez      -> espera um pouco e devolve para a fila
                                   (pode ser o banco reiniciando)
- outro erro, ja era reentrega  -> reject sem requeue: vai para a DLQ

"Ir para a DLQ" nao e codigo nosso: cada fila tem o argumento
x-dead-letter-exchange = gg.dlx, e o proprio broker move a mensagem rejeitada
para la, com o cabecalho x-death contando de onde ela veio e por que morreu.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractRobustConnection,
)

from app.core import config
from app.mensageria.envelope import Envelope, MensagemInvalida, ler

log = logging.getLogger(__name__)

Tratador = Callable[[Envelope, AbstractIncomingMessage], Awaitable[None]]


async def conectar(nome_servico: str) -> AbstractRobustConnection:
    """Conecta com o usuario do servico, insistindo ate o broker aceitar.

    O connection_name aparece na interface do RabbitMQ e na pagina
    Mensageria: e assim que se sabe qual servico e cada consumidor.
    """
    usuario = config.obrigatoria("RABBIT_USUARIO")
    senha = config.obrigatoria("RABBIT_SENHA")
    tentativa = 0

    while True:
        try:
            conexao = await aio_pika.connect_robust(
                host=config.RABBIT_HOST,
                port=config.RABBIT_PORT,
                login=usuario,
                password=senha,
                virtualhost=config.RABBIT_VHOST,
                client_properties={"connection_name": f"gasguard-{nome_servico}"},
            )
            log.info("RabbitMQ: conectado como %s", usuario)
            return conexao
        except (aio_pika.exceptions.AMQPConnectionError, OSError) as erro:
            tentativa += 1
            espera = min(2**tentativa, 30)
            log.warning("RabbitMQ indisponivel (%s), nova tentativa em %ss", erro, espera)
            await asyncio.sleep(espera)


class Publicador:
    """Publica envelopes. Guarda as exchanges para nao buscar a cada mensagem."""

    def __init__(self, canal: AbstractChannel):
        self.canal = canal
        self._exchanges: dict[str, AbstractExchange] = {}

    async def _exchange(self, nome: str) -> AbstractExchange:
        if nome not in self._exchanges:
            # ensure=False: nao declara nada, so monta o objeto. Os usuarios
            # dos servicos nao tem permissao de configure, e a exchange ja
            # existe (veio do topologia.json).
            self._exchanges[nome] = await self.canal.get_exchange(nome, ensure=False)
        return self._exchanges[nome]

    async def publicar(
        self,
        exchange: str,
        routing_key: str,
        envelope: Envelope,
        cabecalhos: dict | None = None,
        persistente: bool = True,
    ) -> None:
        mensagem = aio_pika.Message(
            body=envelope.para_bytes(),
            content_type="application/json",
            delivery_mode=(
                aio_pika.DeliveryMode.PERSISTENT
                if persistente
                else aio_pika.DeliveryMode.NOT_PERSISTENT
            ),
            message_id=envelope.id,
            timestamp=envelope.instante,
            type=envelope.tipo,
            headers=cabecalhos,
        )
        alvo = await self._exchange(exchange)
        # O canal abre com publisher confirms (padrao do aio-pika): este
        # await so volta depois que o broker confirmou que recebeu.
        await alvo.publish(mensagem, routing_key=routing_key, mandatory=False)

    async def publicar_bruto(
        self, exchange: str, routing_key: str, corpo: bytes, cabecalhos: dict
    ) -> None:
        """Para o que nem chegou a virar envelope (payload MQTT invalido)."""
        mensagem = aio_pika.Message(
            body=corpo,
            content_type="application/octet-stream",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=cabecalhos,
        )
        alvo = await self._exchange(exchange)
        await alvo.publish(mensagem, routing_key=routing_key, mandatory=False)


async def consumir(
    canal: AbstractChannel,
    fila: str,
    tratar: Tratador,
    tipo_esperado: str | set[str] | None = None,
) -> None:
    """Liga `tratar` na fila, com a politica de erro descrita no topo."""
    queue = await canal.get_queue(fila, ensure=False)

    async def ao_chegar(mensagem: AbstractIncomingMessage) -> None:
        try:
            envelope = ler(mensagem.body, tipo_esperado)
            await tratar(envelope, mensagem)
        except MensagemInvalida as erro:
            log.warning("%s: mensagem invalida, vai para a DLQ: %s", fila, erro)
            await mensagem.reject(requeue=False)
            return
        except Exception:
            if mensagem.redelivered:
                log.exception("%s: falhou de novo, vai para a DLQ", fila)
                await mensagem.reject(requeue=False)
            else:
                log.exception("%s: falhou, devolvendo para a fila uma vez", fila)
                await asyncio.sleep(2)
                await mensagem.nack(requeue=True)
            return

        await mensagem.ack()

    await queue.consume(ao_chegar)
    log.info("consumindo %s", fila)
