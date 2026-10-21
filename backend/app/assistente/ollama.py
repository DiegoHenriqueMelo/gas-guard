"""Cliente do Ollama, o servidor que roda o LLM dentro do docker compose.

Nada sai da maquina: o modelo (llama3.2:3b por padrao) roda em CPU no
container `ollama`, sem chave de API e sem nuvem.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core import config

log = logging.getLogger(__name__)

# Contexto de 4096 tokens: cabe o resumo dos dados (~1400 tokens), algumas
# trocas da conversa e a resposta. Mais que isso so deixaria a CPU lenta.
# Em CPU o modelo gera ~5 tokens/s: uma resposta de 400 tokens levaria mais
# de um minuto. num_predict e o teto de seguranca; o pedido de resposta curta
# esta nas instrucoes (contexto.py).
OPCOES = {"num_ctx": 4096, "temperature": 0.3, "num_predict": 320}


def _url(caminho: str) -> str:
    return f"{config.OLLAMA_URL.rstrip('/')}{caminho}"


async def situacao() -> dict:
    """baixando? carregado na memoria? A interface mostra "carregando o modelo"."""
    modelo = config.OLLAMA_MODELO
    try:
        async with httpx.AsyncClient(timeout=3.0) as cliente:
            baixados = (await cliente.get(_url("/api/tags"))).json().get("models", [])
            carregados = (await cliente.get(_url("/api/ps"))).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return {"modelo": modelo, "servidor": False, "baixado": False, "carregado": False}

    def mesmo(item: dict) -> bool:
        return item.get("name") == modelo or item.get("model") == modelo

    return {
        "modelo": modelo,
        "servidor": True,
        "baixado": any(mesmo(m) for m in baixados),
        "carregado": any(mesmo(m) for m in carregados),
    }


async def pre_carregar() -> bool:
    """Carrega o modelo na memoria sem gerar nada (prompt vazio).

    keep_alive = -1: fica carregado para sempre. Em CPU, carregar leva de
    10 a 30 s; sem isto, a PRIMEIRA pergunta da apresentacao pagaria esse
    tempo inteiro.
    """
    try:
        async with httpx.AsyncClient(timeout=180.0) as cliente:
            resposta = await cliente.post(
                _url("/api/generate"),
                # o mesmo num_ctx das perguntas: tamanho de contexto diferente
                # faz o Ollama recarregar o modelo na primeira pergunta
                json={"model": config.OLLAMA_MODELO, "keep_alive": -1,
                      "options": {"num_ctx": OPCOES["num_ctx"]}},
            )
            return resposta.status_code == 200
    except httpx.HTTPError as erro:
        log.warning("pre-carga do modelo falhou: %s", erro)
        return False


async def conversar(mensagens: list[dict]) -> AsyncIterator[str]:
    """Manda a conversa e devolve a resposta em pedacos, conforme o modelo gera.

    O Ollama responde em NDJSON: uma linha JSON por pedaco de texto, e uma
    ultima com "done": true.
    """
    corpo = {
        "model": config.OLLAMA_MODELO,
        "messages": mensagens,
        "stream": True,
        "keep_alive": -1,
        "options": OPCOES,
    }
    tempo = httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=tempo) as cliente:
        async with cliente.stream("POST", _url("/api/chat"), json=corpo) as resposta:
            if resposta.status_code != 200:
                detalhe = (await resposta.aread()).decode(errors="replace")[:200]
                raise RuntimeError(f"Ollama respondeu {resposta.status_code}: {detalhe}")
            async for linha in resposta.aiter_lines():
                if not linha.strip():
                    continue
                pedaco = json.loads(linha)
                if pedaco.get("error"):
                    raise RuntimeError(pedaco["error"])
                texto = (pedaco.get("message") or {}).get("content")
                if texto:
                    yield texto
                if pedaco.get("done"):
                    break
