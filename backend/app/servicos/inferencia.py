"""Inferencia: aplica os modelos treinados a telemetria ao vivo do exaustor.

    q.inferencia (telemetry.*.exaustor.*)
        -> features (o MESMO codigo do treino)
        -> saude e vida util previstas
        -> insight.<zona>.exaustor.<codigo>   (painel, cena 3D, InfluxDB)
        -> alerta.<zona>.exaustor.<codigo>    (so quando muda, com histerese)

A IA fica ENTRE a telemetria e a interface: a pagina Insights e a cor do
exaustor na cena 3D vem daqui, nunca direto do simulador. E o simulador
nunca manda a saude verdadeira - so as leituras que um sensor mediria.

Suavizacao: a previsao de cada leitura oscila alguns pontos (ruido do
sensor). Antes de exibir e de alertar, ela passa por uma media movel
exponencial (SUAVIZACAO): cada valor novo pesa 25% e o historico 75%. O valor
bruto continua no insight (saude_bruta, rul_bruta), para comparar.

Alertas com histerese (configuraveis na tabela `configuracoes`):
  ia_saude: abre com 3 previsoes seguidas abaixo de 60 (atencao) ou 30
            (critico); fecha com 10 seguidas acima.
  ia_rul:   o mesmo, com vida util abaixo de 48 h (atencao) ou 12 h.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.alertas.histerese import Histerese
from app.alertas.models import Alerta
from app.core.database import SessionLocal
from app.ia.features import (
    JANELA_LONGA,
    MIN_AMOSTRAS,
    REFERENCIA,
    calcular_features,
    montar_janela_ao_vivo,
)
from app.ia.models import Configuracao
from app.ia.registro import RegistroDeModelos
from app.mensageria import envelope, topologia
from app.mensageria.conexao import Publicador, conectar, consumir
from app.servicos.base import batimento, configurar_log, rodar
from comum.fisica import AMOSTRAS_POR_HORA, CANAIS

log = configurar_log("inferencia")

PADROES = {
    "ia_saude_atencao": 60.0,
    "ia_saude_critico": 30.0,
    "ia_rul_atencao_h": 48.0,
    "ia_rul_critico_h": 12.0,
    "ia_histerese_abrir": 3.0,
    "ia_histerese_fechar": 10.0,
}
PONTOS_TENDENCIA = 30  # previsoes usadas para medir se a saude esta caindo
SUAVIZACAO = 0.25      # peso da previsao nova na media movel exponencial
AVISO_PARADO = 10.0    # segundos entre insights de "equipamento parado"


@dataclass
class Exaustor:
    """O que a inferencia lembra de cada exaustor."""

    cabeca: list[dict] = field(default_factory=list)   # primeiras 24 h
    cauda: deque = field(default_factory=lambda: deque(maxlen=JANELA_LONGA))
    total: int = 0
    saudes: deque = field(default_factory=lambda: deque(maxlen=PONTOS_TENDENCIA))
    histerese_saude: Histerese = field(default_factory=Histerese)
    histerese_rul: Histerese = field(default_factory=Histerese)
    estado_anterior: str | None = None
    ultimo_aviso: float = 0.0
    ultimo_insight: dict = field(default_factory=dict)
    saude_suave: float | None = None
    rul_suave: float | None = None

    def suavizar(self, saude: float, rul: float) -> tuple[float, float]:
        if self.saude_suave is None or self.rul_suave is None:
            self.saude_suave, self.rul_suave = saude, rul
        else:
            self.saude_suave += SUAVIZACAO * (saude - self.saude_suave)
            self.rul_suave += SUAVIZACAO * (rul - self.rul_suave)
        return self.saude_suave, self.rul_suave

    def recomecar(self) -> None:
        """Depois de uma manutencao a maquina e "nova": historia do zero."""
        self.cabeca.clear()
        self.cauda.clear()
        self.total = 0
        self.saudes.clear()
        self.saude_suave = self.rul_suave = None

    def guardar(self, leitura: dict) -> None:
        if self.total < REFERENCIA:
            self.cabeca.append(leitura)
        else:
            self.cauda.append(leitura)
        self.total += 1

    def janela(self):
        # enquanto a cabeca nao encheu, ela E a historia inteira; depois,
        # cabeca + as ultimas JANELA_LONGA (sem repetir linhas)
        if self.total <= REFERENCIA:
            return montar_janela_ao_vivo(self.cabeca, [])
        return montar_janela_ao_vivo(self.cabeca, list(self.cauda))


def tendencia(saudes: deque) -> tuple[str, float]:
    """Inclinacao da saude em pontos por hora de operacao."""
    if len(saudes) < 6:
        return "estavel", 0.0
    inclinacao = float(np.polyfit(np.arange(len(saudes)), np.array(saudes), 1)[0])
    por_hora = inclinacao * AMOSTRAS_POR_HORA
    if por_hora < -1.0:
        return "piorando", por_hora
    if por_hora > 1.0:
        return "melhorando", por_hora
    return "estavel", por_hora


def severidade(valor: float, atencao: float, critico: float) -> str | None:
    if valor < critico:
        return "critico"
    if valor < atencao:
        return "atencao"
    return None


async def principal(parar: asyncio.Event) -> None:
    conexao = await conectar("inferencia")
    canal = await conexao.channel()
    # prefetch baixo: a previsao e rapida, mas queremos que, com o servico
    # parado, a fila fique visivel crescendo no RabbitMQ e nao no buffer daqui
    await canal.set_qos(prefetch_count=10)
    publicador = Publicador(canal)
    registro = RegistroDeModelos()
    exaustores: dict[str, Exaustor] = {}
    limites = dict(PADROES)
    lido_em = {"config": 0.0}

    def ler_configuracoes():
        with SessionLocal() as db:
            linhas = db.scalars(
                select(Configuracao).where(Configuracao.chave.in_(list(PADROES)))
            ).all()
            return {linha.chave: linha.valor for linha in linhas}

    async def atualizar_parametros():
        await asyncio.to_thread(registro.atualizar)
        if time.monotonic() - lido_em["config"] > 15:
            lido_em["config"] = time.monotonic()
            try:
                limites.update(await asyncio.to_thread(ler_configuracoes))
            except Exception:
                log.exception("nao consegui ler configuracoes; mantendo as anteriores")

    async def publicar_insight(codigo: str, zona: str, conteudo: dict) -> None:
        conteudo = {"zona": zona, "tipo": "exaustor", "versao_modelo": registro.versao, **conteudo}
        await publicador.publicar(
            topologia.EX_EVENTOS,
            topologia.rk("insight", zona, "exaustor", codigo),
            envelope.novo("insight", codigo, conteudo),
        )

    async def publicar_alerta(codigo: str, zona: str, chave: str, mudanca, mensagem: str, valor):
        acao, nivel = mudanca
        conteudo = {"zona": zona, "tipo": "exaustor", "origem": "ia", "chave": chave, "acao": acao}
        if acao == "abrir":
            conteudo.update(severidade=nivel, mensagem=mensagem, valor=round(valor, 1))
        await publicador.publicar(
            topologia.EX_EVENTOS,
            topologia.rk("alerta", zona, "exaustor", codigo),
            envelope.novo("alerta", codigo, conteudo),
        )
        log.info("alerta %s %s em %s (%s)", chave, acao, codigo, nivel)

    async def ao_receber(mensagem: envelope.Envelope, _bruta) -> None:
        await atualizar_parametros()
        codigo = mensagem.dispositivo
        if not codigo:
            raise envelope.MensagemInvalida("telemetria sem dispositivo")
        zona = mensagem.conteudo.get("zona", "?")
        estado = mensagem.conteudo.get("estado") or "ligado"
        leituras = mensagem.conteudo.get("leituras") or {}
        maquina = exaustores.setdefault(codigo, Exaustor())

        # manutencao: o simulador avisa com o estado "manutencao" logo depois
        # do reparo; sair de "falha" e voltar a girar tambem conta
        if estado == "manutencao" or (maquina.estado_anterior == "falha" and estado == "ligado"):
            log.info("%s passou por manutencao: historia e referencia reiniciadas", codigo)
            maquina.recomecar()
            estado = "ligado"
        maquina.estado_anterior = estado

        for hist in (maquina.histerese_saude, maquina.histerese_rul):
            hist.n_abrir = int(limites["ia_histerese_abrir"])
            hist.n_fechar = int(limites["ia_histerese_fechar"])

        if estado != "ligado":
            # motor parado: sem vibracao e sem corrente nao ha o que prever
            if time.monotonic() - maquina.ultimo_aviso >= AVISO_PARADO or estado == "falha":
                maquina.ultimo_aviso = time.monotonic()
                conteudo = {**maquina.ultimo_insight, "estado_operacao": estado}
                if estado == "falha":
                    conteudo.update(saude=0.0, rul_horas=0.0, tendencia="falhou", estado_ia="falha")
                else:
                    conteudo["estado_ia"] = "parado"
                await publicar_insight(codigo, zona, conteudo)
            return

        if not leituras:
            return  # so aviso de estado (ex.: logo depois de um comando)

        maquina.guardar({canal: leituras.get(canal, np.nan) for canal in CANAIS})

        if not registro.pronto:
            if time.monotonic() - maquina.ultimo_aviso >= AVISO_PARADO:
                maquina.ultimo_aviso = time.monotonic()
                await publicar_insight(codigo, zona, {
                    "estado_operacao": estado, "estado_ia": "sem_modelo", "amostras": maquina.total,
                })
            return

        if maquina.total < MIN_AMOSTRAS:
            await publicar_insight(codigo, zona, {
                "estado_operacao": estado, "estado_ia": "aquecendo", "amostras": maquina.total,
                "faltam": MIN_AMOSTRAS - maquina.total,
            })
            return

        janela = maquina.janela()
        features = await asyncio.to_thread(lambda: calcular_features(janela).iloc[[-1]])
        previsao = registro.prever(features)
        saude_bruta, rul_bruta = previsao["saude"], previsao["rul_horas"]
        saude, rul = maquina.suavizar(saude_bruta, rul_bruta)

        maquina.saudes.append(saude)
        rumo, inclinacao = tendencia(maquina.saudes)

        mudanca = maquina.histerese_saude.avaliar(
            severidade(saude, limites["ia_saude_atencao"], limites["ia_saude_critico"])
        )
        if mudanca:
            await publicar_alerta(
                codigo, zona, "ia_saude", mudanca,
                f"Saúde prevista em {saude:.0f}/100 (modelo {registro.versao})", saude,
            )
        mudanca = maquina.histerese_rul.avaliar(
            severidade(rul, limites["ia_rul_atencao_h"], limites["ia_rul_critico_h"])
        )
        if mudanca:
            await publicar_alerta(
                codigo, zona, "ia_rul", mudanca,
                f"Falha prevista em cerca de {rul:.0f} h de operação (modelo {registro.versao})", rul,
            )

        maquina.ultimo_insight = {
            "estado_operacao": estado,
            "estado_ia": "ok",
            "saude": round(saude, 1),
            "rul_horas": round(rul, 1),
            "saude_bruta": round(saude_bruta, 1),
            "rul_bruta": round(rul_bruta, 1),
            "tendencia": rumo,
            "inclinacao_saude": round(inclinacao, 2),
            "amostras": maquina.total,
            "alertas": {
                "ia_saude": maquina.histerese_saude.ativo,
                "ia_rul": maquina.histerese_rul.ativo,
            },
        }
        await publicar_insight(codigo, zona, maquina.ultimo_insight)

    def alertas_abertos():
        with SessionLocal() as db:
            return [
                (a.dispositivo_codigo, a.chave, a.severidade)
                for a in db.query(Alerta).filter(Alerta.ativo.is_(True), Alerta.origem == "ia")
            ]

    # A histerese vive na memoria: ao reiniciar, retoma os alertas que estao
    # abertos no banco, para conseguir fecha-los quando a saude voltar.
    for codigo, chave, nivel in await asyncio.to_thread(alertas_abertos):
        maquina = exaustores.setdefault(codigo, Exaustor())
        if chave == "ia_saude":
            maquina.histerese_saude.ativo = nivel
        elif chave == "ia_rul":
            maquina.histerese_rul.ativo = nivel

    await consumir(canal, topologia.Q_INFERENCIA, ao_receber, tipo_esperado="telemetria")
    tarefa = asyncio.create_task(batimento(lambda: not conexao.is_closed))
    await parar.wait()
    tarefa.cancel()
    await conexao.close()


if __name__ == "__main__":
    rodar(principal)
