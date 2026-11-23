"""Gravador: consome q.gravador e escreve no InfluxDB.

Recebe dois tipos de mensagem (veja as ligacoes em topologia.json):
  telemetry.#  -> measurement "telemetria"
  insight.#    -> measurement "insights" (a saude prevista vira serie
                  temporal, e o painel desenha a tendencia)

E o consumidor ideal para a demonstracao do "consumidor parado":
`docker compose stop gravador` e a fila q.gravador cresce na pagina
Mensageria; `docker compose start gravador` e ela esvazia. Nada se perde,
porque a fila e duravel e as mensagens sao persistentes.

Escrita em lote: o gravador junta ate 200 mensagens (ou 0,5 s) e grava
tudo numa escrita so no Influx - e o que faz a fila esvaziar rapido quando
ele volta depois de parado. So depois da escrita confirmada ele da ack nas
mensagens do lote. Se o Influx falhar, nenhuma recebe ack e todas voltam
para a fila.
"""

import asyncio

from aio_pika.abc import AbstractIncomingMessage

from app.core import influx
from app.mensageria import envelope, topologia
from app.mensageria.conexao import conectar
from app.servicos.base import batimento, configurar_log, rodar

log = configurar_log("gravador")

LOTE = 200
ESPERA_LOTE = 0.5  # segundos


def ponto_de(mensagem: envelope.Envelope):
    c = mensagem.conteudo
    if mensagem.tipo == "telemetria":
        return influx.ponto_telemetria(
            mensagem.dispositivo or "?", c.get("zona", "?"), c.get("tipo", "?"),
            mensagem.instante, c.get("leituras") or {}, c.get("estado"),
        )
    if mensagem.tipo == "insight":
        return influx.ponto_insight(
            mensagem.dispositivo or "?", c.get("zona", "?"), mensagem.instante, c
        )
    raise envelope.MensagemInvalida(f"gravador nao grava {mensagem.tipo}")


async def principal(parar: asyncio.Event) -> None:
    conexao = await conectar("gravador")
    canal = await conexao.channel()
    # o prefetch precisa ser >= ao lote, senao o broker nunca entrega 200
    await canal.set_qos(prefetch_count=LOTE * 2)
    fila = await canal.get_queue(topologia.Q_GRAVADOR, ensure=False)

    pendentes: asyncio.Queue[AbstractIncomingMessage] = asyncio.Queue()

    async def ao_chegar(mensagem: AbstractIncomingMessage) -> None:
        await pendentes.put(mensagem)

    async def escrever_lotes() -> None:
        while True:
            lote = [await pendentes.get()]
            limite = asyncio.get_running_loop().time() + ESPERA_LOTE
            while len(lote) < LOTE:
                falta = limite - asyncio.get_running_loop().time()
                if falta <= 0:
                    break
                try:
                    lote.append(await asyncio.wait_for(pendentes.get(), timeout=falta))
                except TimeoutError:
                    break

            pontos, validas = [], []
            for bruta in lote:
                try:
                    ponto = ponto_de(envelope.ler(bruta.body, {"telemetria", "insight"}))
                except envelope.MensagemInvalida as erro:
                    log.warning("mensagem invalida, vai para a DLQ: %s", erro)
                    await bruta.reject(requeue=False)
                    continue
                if ponto is not None:
                    pontos.append(ponto)
                validas.append(bruta)

            if not validas:
                continue

            try:
                await asyncio.to_thread(influx.gravar, pontos)
            except Exception:
                log.exception("InfluxDB falhou; %d mensagens voltam para a fila", len(validas))
                await asyncio.sleep(2)
                for bruta in validas:
                    await bruta.nack(requeue=True)
                continue

            # ack individual: o lote pode ter tido rejeitadas no meio, e o
            # multiple=True confirmaria tambem as ja rejeitadas
            for bruta in validas:
                await bruta.ack()

            # so loga quando esta esvaziando uma fila acumulada
            if len(validas) >= 50:
                log.info("gravadas %d mensagens de uma vez (esvaziando a fila)", len(validas))

    tarefa_escrita = asyncio.create_task(escrever_lotes())
    tarefa_batimento = asyncio.create_task(batimento(lambda: not conexao.is_closed))
    await fila.consume(ao_chegar)
    log.info("consumindo %s", topologia.Q_GRAVADOR)

    await parar.wait()
    tarefa_escrita.cancel()
    tarefa_batimento.cancel()
    await conexao.close()


if __name__ == "__main__":
    rodar(principal)
