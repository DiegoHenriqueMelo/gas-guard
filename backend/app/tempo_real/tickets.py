"""Ticket curto e de uso unico para abrir o WebSocket.

O navegador nao consegue mandar cabecalho Authorization ao abrir um
WebSocket, e a saida comum - pendurar o JWT na URL (?token=...) - vaza o
token para log de proxy, historico do navegador e cabecalho Referer.

Entao o fluxo e:
  1. POST /api/ws/ticket com o JWT no cabecalho, como qualquer rota;
  2. a API devolve um ticket aleatorio que vale 30 s e uma vez so;
  3. o navegador abre /ws?ticket=<ticket>; a API consome o ticket.
Se o ticket vazar, ja nao serve para nada.
"""

import secrets
import threading
import time

from app.auth.schemas import UsuarioToken

VALIDADE = 30  # segundos

_tickets: dict[str, tuple[UsuarioToken, float]] = {}
_trava = threading.Lock()


def emitir(usuario: UsuarioToken) -> str:
    ticket = secrets.token_urlsafe(32)
    agora = time.monotonic()
    with _trava:
        # aproveita para jogar fora os vencidos
        for chave in [k for k, (_, t) in _tickets.items() if agora - t > VALIDADE]:
            del _tickets[chave]
        _tickets[ticket] = (usuario, agora)
    return ticket


def consumir(ticket: str) -> UsuarioToken | None:
    with _trava:
        registro = _tickets.pop(ticket, None)  # pop: uso unico
    if registro is None:
        return None
    usuario, emitido_em = registro
    if time.monotonic() - emitido_em > VALIDADE:
        return None
    return usuario
