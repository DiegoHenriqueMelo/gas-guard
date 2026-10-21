from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.auth.deps import usuario_atual
from app.auth.schemas import UsuarioToken
from app.tempo_real import tickets
from app.tempo_real.hub import hub

router = APIRouter(tags=["tempo real"])


class TicketOut(BaseModel):
    ticket: str
    validade_segundos: int


@router.post("/api/ws/ticket", response_model=TicketOut)
def emitir_ticket(usuario: UsuarioToken = Depends(usuario_atual)):
    """Primeiro passo para abrir o WebSocket (ver tempo_real/tickets.py)."""
    return TicketOut(ticket=tickets.emitir(usuario), validade_segundos=tickets.VALIDADE)


@router.get("/api/estado", dependencies=[Depends(usuario_atual)])
def estado_atual():
    """O mesmo snapshot que o WebSocket manda ao conectar."""
    return hub.snapshot()["conteudo"]


@router.websocket("/ws")
async def websocket(ws: WebSocket, ticket: str = Query(default="")):
    usuario = tickets.consumir(ticket)
    await ws.accept()
    if usuario is None:
        # 4401: codigo de aplicacao (4000-4999). O frontend entende como
        # "pegue um ticket novo", nao como queda de rede.
        await ws.close(code=4401, reason="ticket invalido ou vencido")
        return

    await hub.entrar(ws, usuario)
    try:
        while True:
            # o navegador nao manda nada alem de pings; ficar lendo e o
            # jeito de perceber quando ele fecha a aba
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.sair(ws)
