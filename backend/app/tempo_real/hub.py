"""O hub do WebSocket: recebe da fila q.websocket e repassa aos navegadores.

    gg.telemetria / gg.eventos / gg.comandos -> q.websocket -> HUB -> navegadores

Tambem guarda em memoria o "estado atual" (ultima leitura de cada
dispositivo, ultima previsao de cada exaustor). Assim, quem abre a pagina
recebe tudo de uma vez num "snapshot", sem esperar a proxima leitura, e o
assistente monta o resumo dos dados sem consultar banco nenhum.
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import UTC, datetime

from fastapi import WebSocket
from sqlalchemy import update

from app.auth.schemas import UsuarioToken
from app.core.database import SessionLocal
from app.dispositivos.models import Dispositivo
from app.mensageria.envelope import Envelope

log = logging.getLogger(__name__)

ENVIO_TIMEOUT = 2.0  # segundos; cliente mais lento que isso e desconectado


class Hub:
    def __init__(self) -> None:
        self.clientes: dict[WebSocket, UsuarioToken] = {}
        self.telemetria: dict[str, dict] = {}   # codigo -> ultimo envelope
        self.insights: dict[str, dict] = {}     # codigo -> ultimo envelope
        self.acionamentos: deque[dict] = deque(maxlen=20)
        # ultimas mensagens de qualquer tipo, para a pagina Mensageria
        self.recentes: deque[dict] = deque(maxlen=60)
        self.ultima_telemetria_em: float | None = None
        self.recebidas = 0
        self._contatos: dict[str, datetime] = {}

    # ---------- navegadores ----------

    async def entrar(self, ws: WebSocket, usuario: UsuarioToken) -> None:
        self.clientes[ws] = usuario
        await ws.send_text(json.dumps(self.snapshot(), default=str))

    def sair(self, ws: WebSocket) -> None:
        self.clientes.pop(ws, None)

    def snapshot(self) -> dict:
        return {
            "tipo": "snapshot",
            "instante": datetime.now(UTC).isoformat(),
            "conteudo": {
                "telemetria": self.telemetria,
                "insights": self.insights,
                "acionamentos": list(self.acionamentos),
            },
        }

    async def _enviar(self, ws: WebSocket, texto: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(texto), timeout=ENVIO_TIMEOUT)
        except Exception:
            self.sair(ws)

    async def transmitir(self, mensagem: dict) -> None:
        if not self.clientes:
            return
        texto = json.dumps(mensagem, default=str)
        await asyncio.gather(*(self._enviar(ws, texto) for ws in list(self.clientes)))

    # ---------- fila ----------

    async def ao_receber(self, envelope: Envelope, bruta) -> None:
        mensagem = {"rk": bruta.routing_key, **envelope.para_dict()}
        self.recebidas += 1

        if envelope.tipo == "telemetria" and envelope.dispositivo:
            self.telemetria[envelope.dispositivo] = mensagem
            self.ultima_telemetria_em = time.monotonic()
            self._contatos[envelope.dispositivo] = envelope.instante
        elif envelope.tipo == "insight" and envelope.dispositivo:
            self.insights[envelope.dispositivo] = mensagem
        elif envelope.tipo == "acionamento":
            self.acionamentos.appendleft(mensagem)

        self.recentes.appendleft({
            "rk": bruta.routing_key,
            "exchange": bruta.exchange,
            "id": envelope.id,
            "instante": mensagem["instante"],
            "tipo": envelope.tipo,
            "dispositivo": envelope.dispositivo,
            "conteudo": envelope.conteudo,
        })

        await self.transmitir(mensagem)

    # ---------- ultimo contato no cadastro ----------

    async def gravar_contatos(self) -> None:
        """A cada 30 s, grava o `ultimo_contato` de quem mandou leitura.

        Fazer um UPDATE por leitura seria um UPDATE a cada 2 s por
        dispositivo; em lote, e um por dispositivo a cada 30 s.
        """
        while True:
            await asyncio.sleep(30)
            if not self._contatos:
                continue
            contatos, self._contatos = self._contatos, {}

            def gravar(contatos: dict[str, datetime]) -> None:
                with SessionLocal() as db:
                    for codigo, instante in contatos.items():
                        db.execute(
                            update(Dispositivo)
                            .where(Dispositivo.codigo == codigo)
                            .values(ultimo_contato=instante)
                        )
                    db.commit()

            try:
                await asyncio.to_thread(gravar, contatos)
            except Exception:
                log.exception("nao consegui gravar ultimo_contato")

    def segundos_sem_telemetria(self) -> float | None:
        if self.ultima_telemetria_em is None:
            return None
        return time.monotonic() - self.ultima_telemetria_em


hub = Hub()
