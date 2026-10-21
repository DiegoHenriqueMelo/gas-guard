"""Gateway: a ponte entre a borda (MQTT) e o barramento interno (RabbitMQ).

    simulador --MQTT--> Mosquitto --> GATEWAY --> gg.telemetria (RabbitMQ)
    simulador <--MQTT-- Mosquitto <-- GATEWAY <-- q.comandos    (RabbitMQ)

Por que dois brokers? O MQTT e leve e feito para dispositivo pequeno em rede
ruim; e o protocolo da borda. Dentro da aplicacao precisamos de filas
duraveis, varios consumidores independentes, DLQ e roteamento por padrao -
isso e o RabbitMQ. O gateway e o unico servico que fala os dois.

Ida (telemetria):
  1. chega em gasguard/<codigo>/telemetria
  2. valida o JSON e confere o codigo no cadastro (Postgres, em cache)
  3. carimba o instante (o relogio do dispositivo nao e confiavel)
  4. embrulha no envelope e publica em telemetry.<zona>.<tipo>.<codigo>
  Payload invalido ou dispositivo desconhecido vai para a DLQ, com o corpo
  original preservado e o motivo no cabecalho.

Volta (comando):
  consome q.comandos e publica em gasguard/<codigo>/comando.
"""

import asyncio
import json
import time
from typing import Any

import aiomqtt
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import joinedload

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.core import config
from app.core.database import SessionLocal
from app.dispositivos.models import Dispositivo
from app.mensageria import envelope, topologia
from app.mensageria.conexao import Publicador, conectar, consumir
from app.servicos.base import batimento, configurar_log, rodar

log = configurar_log("gateway")

TOPICO_TELEMETRIA = "gasguard/+/telemetria"
TAMANHO_MAXIMO = 4096        # bytes; payload legitimo tem uns 200
RECARREGAR_CADASTRO = 15     # segundos

# Dispositivo virtual que recebe os comandos do proprio simulador
# (injetar falha, vazamento, pausar). Nao precisa estar no cadastro.
SIMULADOR = "SIMULADOR"


class TelemetriaMqtt(BaseModel):
    """O payload que o simulador publica."""

    codigo: str = Field(max_length=50)
    leituras: dict[str, float] = Field(default_factory=dict)
    estado: str | None = Field(default=None, max_length=20)


class Cadastro:
    """Copia em memoria de codigo -> (zona, tipo, ativo), relida a cada 15 s.

    Consultar o Postgres a cada leitura (varias por segundo) seria
    desperdicio; um dispositivo recem-cadastrado demora no maximo 15 s para
    ser aceito.
    """

    def __init__(self) -> None:
        self.dispositivos: dict[str, dict[str, Any]] = {}
        self.lido_em = 0.0

    def _ler(self) -> dict[str, dict[str, Any]]:
        with SessionLocal() as db:
            linhas = db.query(Dispositivo).options(joinedload(Dispositivo.ambiente)).all()
            return {
                d.codigo: {"zona": d.ambiente.zona, "tipo": d.tipo, "ativo": d.ativo}
                for d in linhas
            }

    async def atualizar_se_preciso(self) -> None:
        if time.monotonic() - self.lido_em < RECARREGAR_CADASTRO:
            return
        try:
            self.dispositivos = await asyncio.to_thread(self._ler)
            self.lido_em = time.monotonic()
        except Exception:
            log.exception("nao consegui ler o cadastro; mantendo o anterior")


async def principal(parar: asyncio.Event) -> None:
    conexao = await conectar("gateway")
    canal = await conexao.channel()
    await canal.set_qos(prefetch_count=20)
    publicador = Publicador(canal)
    cadastro = Cadastro()

    # O consumidor de comandos precisa do cliente MQTT da vez. Quando o MQTT
    # cai, o cliente e recriado; este dicionario guarda o atual.
    estado: dict[str, Any] = {"mqtt": None}
    mqtt_pronto = asyncio.Event()

    async def para_dlq(corpo: bytes, topico: str, motivo: str) -> None:
        log.warning("descartado (%s) em %s", motivo, topico)
        await publicador.publicar_bruto(
            topologia.EX_DLX,
            "mqtt.invalido",
            corpo[:TAMANHO_MAXIMO],
            {"x-origem": "mqtt", "x-topico": topico, "x-motivo": motivo},
        )

    async def ao_receber_mqtt(topico: str, corpo: bytes) -> None:
        if len(corpo) > TAMANHO_MAXIMO:
            await para_dlq(corpo, topico, "payload grande demais")
            return

        try:
            dados = TelemetriaMqtt.model_validate_json(corpo)
        except ValidationError as erro:
            await para_dlq(corpo, topico, f"json invalido: {erro.errors()[0]['msg']}")
            return

        # o codigo do topico e o do payload precisam bater: impede que um
        # dispositivo publique leituras em nome de outro
        codigo_topico = topico.split("/")[1]
        if dados.codigo != codigo_topico:
            await para_dlq(corpo, topico, "codigo do payload difere do topico")
            return

        await cadastro.atualizar_se_preciso()
        registro = cadastro.dispositivos.get(dados.codigo)
        if registro is None:
            # Protege o InfluxDB: cada codigo inventado viraria uma serie
            # nova e permanente no indice (explosao de cardinalidade).
            await para_dlq(corpo, topico, "dispositivo nao cadastrado")
            return
        if not registro["ativo"]:
            return  # desativado de proposito: ignora em silencio

        mensagem = envelope.novo(
            "telemetria",
            dados.codigo,
            {
                "zona": registro["zona"],
                "tipo": registro["tipo"],
                "leituras": dados.leituras,
                "estado": dados.estado,
            },
        )
        rk = topologia.rk_telemetria(registro["zona"], registro["tipo"], dados.codigo)
        await publicador.publicar(topologia.EX_TELEMETRIA, rk, mensagem)

    async def ao_receber_comando(mensagem: envelope.Envelope, _bruta) -> None:
        if not mensagem.dispositivo:
            raise envelope.MensagemInvalida("comando sem dispositivo")
        acao = mensagem.conteudo.get("acao")
        if not acao:
            raise envelope.MensagemInvalida("comando sem acao")

        # espera o MQTT voltar por alguns segundos antes de desistir
        try:
            await asyncio.wait_for(mqtt_pronto.wait(), timeout=5)
        except TimeoutError:
            raise RuntimeError("MQTT fora do ar, comando nao entregue")

        payload = {
            "id": mensagem.id,
            "acao": acao,
            "parametros": mensagem.conteudo.get("parametros") or {},
            "origem": mensagem.conteudo.get("origem"),
        }
        topico = f"gasguard/{mensagem.dispositivo}/comando"
        await estado["mqtt"].publish(topico, json.dumps(payload), qos=1)
        log.info("comando %s -> %s (%s)", acao, mensagem.dispositivo, payload["origem"])

    async def laco_mqtt() -> None:
        """Conecta no Mosquitto e reconecta para sempre se cair."""
        while not parar.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=config.MQTT_HOST,
                    port=config.MQTT_PORT,
                    username=config.obrigatoria("MQTT_USUARIO"),
                    password=config.obrigatoria("MQTT_SENHA"),
                    identifier="gasguard-gateway",
                ) as cliente:
                    estado["mqtt"] = cliente
                    await cliente.subscribe(TOPICO_TELEMETRIA, qos=1)
                    mqtt_pronto.set()
                    log.info("MQTT: conectado, assinando %s", TOPICO_TELEMETRIA)
                    async for msg in cliente.messages:
                        try:
                            await ao_receber_mqtt(msg.topic.value, bytes(msg.payload))
                        except Exception:
                            log.exception("falha ao repassar mensagem MQTT")
            except aiomqtt.MqttError as erro:
                mqtt_pronto.clear()
                estado["mqtt"] = None
                log.warning("MQTT: conexao perdida (%s), tentando de novo em 3 s", erro)
                await asyncio.sleep(3)

    await consumir(canal, topologia.Q_COMANDOS, ao_receber_comando, tipo_esperado="comando")

    tarefas = [
        asyncio.create_task(laco_mqtt()),
        asyncio.create_task(
            batimento(lambda: not conexao.is_closed and mqtt_pronto.is_set())
        ),
    ]
    await parar.wait()
    for tarefa in tarefas:
        tarefa.cancel()
    await conexao.close()


if __name__ == "__main__":
    rodar(principal)
