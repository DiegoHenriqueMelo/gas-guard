"""Pagina Mensageria: o que esta acontecendo dentro do RabbitMQ.

Quem consulta o broker e o BACKEND, pela API HTTP de gerenciamento do
RabbitMQ (porta 15672, so na rede interna do compose). O navegador fala so
com a nossa API: nunca recebe credencial do broker nem fala com ele.

O usuario gg_api tem a tag "monitoring" no RabbitMQ: pode LER filas,
conexoes e taxas, mas nao pode criar, apagar nem configurar nada. Ler e
esvaziar a DLQ usa a permissao de leitura que ele tem so nela.
"""

from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.auditoria.service import registrar_fora_de_request
from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core import config
from app.mensageria import envelope, topologia
from app.tempo_real.barramento import barramento
from app.tempo_real.hub import hub

router = APIRouter(prefix="/api/mensageria", tags=["mensageria"], dependencies=[Depends(usuario_atual)])

VHOST = quote(topologia.VHOST, safe="")

# usuario do RabbitMQ -> servico (cada servico entra com o seu)
SERVICO_DO_USUARIO = {
    "gg_api": "api",
    "gg_gateway": "gateway",
    "gg_gravador": "gravador",
    "gg_regras": "regras",
    "gg_inferencia": "inferencia",
    "gg_lab": "lab",
    "gg_admin": "administrador (interface)",
}


def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.RABBIT_GESTAO_URL,
        auth=(config.obrigatoria("RABBIT_USUARIO"), config.obrigatoria("RABBIT_SENHA")),
        timeout=5.0,
    )


def _taxa(estatisticas: dict | None, chave: str) -> float:
    return round(float(((estatisticas or {}).get(chave) or {}).get("rate", 0.0)), 2)


async def _get(cliente: httpx.AsyncClient, caminho: str):
    try:
        resposta = await cliente.get(caminho)
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise HTTPException(status_code=503, detail=f"RabbitMQ indisponível: {erro}") from erro
    return resposta.json()


@router.get("/visao")
async def visao_geral():
    """Filas, consumidores, taxas e ultimas mensagens - a pagina consulta a cada 2 s."""
    async with _cliente() as cliente:
        geral = await _get(cliente, "/api/overview")
        filas = await _get(cliente, f"/api/queues/{VHOST}")
        consumidores = await _get(cliente, f"/api/consumers/{VHOST}")
        exchanges = await _get(cliente, f"/api/exchanges/{VHOST}")

    por_fila: dict[str, list[dict]] = {}
    for consumidor in consumidores:
        canal = consumidor.get("channel_details") or {}
        usuario = canal.get("user", "?")
        por_fila.setdefault(consumidor["queue"]["name"], []).append({
            "tag": consumidor.get("consumer_tag"),
            "servico": SERVICO_DO_USUARIO.get(usuario, usuario),
            "usuario": usuario,
            "origem": canal.get("peer_host"),
            "prefetch": consumidor.get("prefetch_count"),
            "ativo": consumidor.get("active", True),
        })

    lista_filas = []
    for fila in sorted(filas, key=lambda f: topologia.TODAS_AS_FILAS.index(f["name"])
                       if f["name"] in topologia.TODAS_AS_FILAS else 99):
        estatisticas = fila.get("message_stats")
        argumentos = fila.get("arguments") or {}
        lista_filas.append({
            "nome": fila["name"],
            "mensagens": fila.get("messages", 0),
            "prontas": fila.get("messages_ready", 0),
            "sem_ack": fila.get("messages_unacknowledged", 0),
            "consumidores": fila.get("consumers", 0),
            "consumidor_esperado": topologia.CONSUMIDOR_DA_FILA.get(fila["name"]),
            "taxa_entrada": _taxa(estatisticas, "publish_details"),
            "taxa_entrega": _taxa(estatisticas, "deliver_get_details"),
            "taxa_ack": _taxa(estatisticas, "ack_details"),
            "estado": fila.get("state"),
            "dlx": argumentos.get("x-dead-letter-exchange"),
            "ttl_ms": argumentos.get("x-message-ttl"),
            "max": argumentos.get("x-max-length"),
            "lista_consumidores": por_fila.get(fila["name"], []),
        })

    lista_exchanges = [
        {
            "nome": ex["name"],
            "tipo": ex["type"],
            "taxa_entrada": _taxa(ex.get("message_stats"), "publish_in_details"),
            "taxa_saida": _taxa(ex.get("message_stats"), "publish_out_details"),
        }
        for ex in exchanges
        if ex["name"].startswith("gg.")
    ]

    totais = geral.get("queue_totals") or {}
    estatisticas = geral.get("message_stats")
    return {
        "broker": {
            "versao": geral.get("rabbitmq_version"),
            "no": geral.get("node"),
            "mensagens": totais.get("messages", 0),
            "taxa_publicacao": _taxa(estatisticas, "publish_details"),
            "taxa_entrega": _taxa(estatisticas, "deliver_get_details"),
            "conexoes": (geral.get("object_totals") or {}).get("connections", 0),
            "consumidores": (geral.get("object_totals") or {}).get("consumers", 0),
        },
        "filas": lista_filas,
        "exchanges": lista_exchanges,
        "ultimas_mensagens": list(hub.recentes)[:30],
    }


@router.get("/dlq")
async def mensagens_mortas(limite: int = Query(default=20, ge=1, le=100)):
    """Espia a DLQ sem consumir: o RabbitMQ entrega e devolve na mesma
    posicao (ackmode ack_requeue_true). A mensagem continua preservada."""
    async with _cliente() as cliente:
        try:
            resposta = await cliente.post(
                f"/api/queues/{VHOST}/{topologia.Q_DLQ}/get",
                json={"count": limite, "ackmode": "ack_requeue_true", "encoding": "auto",
                      "truncate": 4000},
            )
            resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise HTTPException(status_code=503, detail=f"RabbitMQ indisponível: {erro}") from erro

    saida = []
    for item in resposta.json():
        cabecalhos = (item.get("properties") or {}).get("headers") or {}
        mortes = cabecalhos.get("x-death") or []
        primeira = mortes[0] if mortes else {}
        saida.append({
            "routing_key": item.get("routing_key"),
            "exchange": item.get("exchange"),
            "corpo": item.get("payload"),
            "motivo": cabecalhos.get("x-motivo") or primeira.get("reason"),
            "fila_de_origem": primeira.get("queue") or cabecalhos.get("x-origem"),
            "quantas_vezes": primeira.get("count"),
            "morreu_em": primeira.get("time"),
            "topico_mqtt": cabecalhos.get("x-topico"),
        })
    return saida


@router.delete("/dlq", status_code=204)
async def esvaziar_dlq(request: Request, usuario: UsuarioToken = Depends(exige("administrador"))):
    async with _cliente() as cliente:
        resposta = await cliente.delete(f"/api/queues/{VHOST}/{topologia.Q_DLQ}/contents")
        if resposta.status_code >= 400:
            raise HTTPException(status_code=503, detail="Não consegui esvaziar a DLQ")
    await run_in_threadpool(
        registrar_fora_de_request, "dlq.esvaziada", usuario=usuario.usuario,
        papel=usuario.papel, ip=ip_do_cliente(request),
    )


@router.post("/dlq/demonstracao", status_code=202)
async def demonstrar_dlq(request: Request, usuario: UsuarioToken = Depends(exige("administrador"))):
    """Publica de proposito um alerta mal formado (sem "chave" nem "acao").

    O servico regras tenta ler, rejeita (MensagemInvalida) e o RabbitMQ move
    a mensagem para gg.dlx -> q.dlq, com o cabecalho x-death dizendo de que
    fila ela veio. Serve para mostrar a DLQ funcionando na apresentacao.
    """
    mensagem = envelope.novo("alerta", "DEMO-DLQ", {"isto": "nao e um alerta valido"})
    await barramento.publicar(topologia.EX_EVENTOS, "alerta.demo.teste.DEMO-DLQ", mensagem)
    await run_in_threadpool(
        registrar_fora_de_request, "dlq.demonstracao", usuario=usuario.usuario,
        papel=usuario.papel, detalhe={"id": mensagem.id}, ip=ip_do_cliente(request),
    )
    return {"id": mensagem.id}
