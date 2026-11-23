"""O que todo servico de fundo repete: log, batimento e desligamento limpo."""

import asyncio
import contextlib
import logging
import signal
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

# O healthcheck do docker-compose olha a data deste arquivo (ver saude.py).
ARQUIVO_BATIMENTO = Path("/tmp/vivo")


def configurar_log(nome: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{nome}] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    # o aiormq loga cada reconexao em nivel INFO; deixamos so os avisos
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    return logging.getLogger(nome)


async def batimento(esta_vivo: Callable[[], bool], intervalo: float = 5.0) -> None:
    """Toca o arquivo de batimento enquanto o servico estiver saudavel.

    "Saudavel" e o servico quem diz: em geral, conexao com o RabbitMQ aberta.
    Se a conexao cair e nao voltar, o arquivo envelhece e o Docker marca o
    container como unhealthy.
    """
    while True:
        try:
            if esta_vivo():
                ARQUIVO_BATIMENTO.touch()
        except OSError:
            pass
        await asyncio.sleep(intervalo)


def rodar(principal: Callable[[asyncio.Event], Awaitable[None]]) -> None:
    """Roda o servico ate o Docker mandar SIGTERM (docker compose stop).

    `principal` recebe um Event que e acionado no desligamento; ele deve
    montar tudo e esperar esse evento.
    """

    async def _main() -> None:
        parar = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sinal in (signal.SIGTERM, signal.SIGINT):
            # add_signal_handler nao existe no Windows; la o Ctrl+C ainda
            # levanta KeyboardInterrupt, o que basta para desenvolver.
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sinal, parar.set)
        await principal(parar)

    inicio = time.monotonic()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())
    logging.getLogger(__name__).info(
        "encerrado depois de %.0fs", time.monotonic() - inicio
    )
