from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.assistente import contexto, ollama
from app.auditoria.service import registrar_fora_de_request
from app.auth.deps import ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core import config
from app.core.limitador import Limitador

router = APIRouter(prefix="/api/assistente", tags=["assistente"])

limitador = Limitador(maximo=config.ASSISTENTE_PERGUNTAS_POR_MINUTO, janela_segundos=60)


class Mensagem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)
    # as ultimas trocas, para o assistente entender "e o que eu faço?"
    historico: list[Mensagem] = Field(default_factory=list, max_length=6)


@router.get("/status", dependencies=[Depends(usuario_atual)])
async def situacao_do_modelo():
    return await ollama.situacao()


@router.get("/contexto", dependencies=[Depends(usuario_atual)])
async def ver_contexto():
    """O texto exato que vai para o LLM junto com a pergunta. Util para
    mostrar na apresentacao que o assistente so sabe o que esta aqui."""
    return {"contexto": await run_in_threadpool(contexto.montar)}


@router.post("/perguntar")
async def perguntar(
    dados: PerguntaIn,
    request: Request,
    usuario: UsuarioToken = Depends(usuario_atual),
):
    """Resposta em streaming: o texto chega pedaco a pedaco, conforme o
    modelo gera. O frontend le com fetch() + ReadableStream."""
    permitido, espera = limitador.permitir(usuario.usuario)
    if not permitido:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {limitador.maximo} perguntas por minuto. Tente em {int(espera) + 1} s",
        )

    await run_in_threadpool(
        registrar_fora_de_request, "assistente.pergunta", usuario=usuario.usuario,
        papel=usuario.papel, detalhe={"pergunta": dados.pergunta[:500]}, ip=ip_do_cliente(request),
    )

    texto_contexto = await run_in_threadpool(contexto.montar)
    mensagens = [{"role": "system", "content": texto_contexto}]
    mensagens += [m.model_dump() for m in dados.historico]
    mensagens.append({"role": "user", "content": dados.pergunta})

    async def gerar():
        try:
            async for pedaco in ollama.conversar(mensagens):
                yield pedaco
        except Exception as erro:
            yield f"\n\n_(o assistente falhou: {erro})_"

    return StreamingResponse(
        gerar(),
        media_type="text/plain; charset=utf-8",
        # X-Accel-Buffering: sem isto o nginx do frontend junta a resposta
        # inteira antes de repassar, e o streaming vira uma espera longa
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
