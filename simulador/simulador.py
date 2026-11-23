"""Simulador da cozinha: o "dispositivo" do gas-guard na 2a entrega.

Faz o papel do ESP32 do 1o bimestre, so que com tudo o que a cozinha tem:

  sensores     GAS-01 (ppm), TEMP-01 (°C), UMID-01 (%), LUZ-01 (lx), VAZAO-01 (m³/h)
  atuadores    VALVULA-01 (aberta/fechada), SIRENE-01 (ligado/desligado)
  equipamento  EXAUSTOR-01: liga/desliga e mede vibracao, corrente,
               temperatura do motor e rotacao

A cada INTERVALO segundos publica a leitura de cada um em
gasguard/<codigo>/telemetria. Assina gasguard/+/comando e, quando chega um
comando, muda o estado do atuador - e isso aparece nas leituras seguintes:
valvula fechada zera a vazao e para o vazamento; exaustor ligado puxa o gas
para fora e a concentracao cai.

O que o simulador NUNCA publica: a saude verdadeira do exaustor, o tempo
que falta para ele falhar, o modo de falha injetado. Ele sabe tudo isso
(e imprime no log), mas um sensor de verdade nao mediria - quem descobre e
a IA, a partir das leituras.

Os comandos para o proprio simulador chegam em gasguard/SIMULADOR/comando:
injetar_falha, reparar, vazamento, relogio, pausar, retomar.
"""

import json
import logging
import math
import os
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import paho.mqtt.client as mqtt

from comum.fisica import (
    AMOSTRA_MINUTOS,
    AMOSTRAS_POR_HORA,
    BASE_NOMINAL,
    CANAIS,
    DERIVA_MAXIMA,
    MODOS_EQUIPAMENTO,
    MODOS_SENSOR,
    carga_exaustor,
    leituras_exaustor,
    luminosidade_externa,
    nivel_degradacao,
    servico,
    temperatura_ambiente,
    umidade_ambiente,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [simulador] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("simulador")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USUARIO = os.environ["MQTT_USUARIO"]
MQTT_SENHA = os.environ["MQTT_SENHA"]
INTERVALO = float(os.getenv("INTERVALO", "2"))
FATOR_RELOGIO = float(os.getenv("FATOR_RELOGIO", "1"))
RUIDO = float(os.getenv("RUIDO", "0.3"))
PCT_FALTANTES = float(os.getenv("PCT_FALTANTES", "0.5"))
PCT_OUTLIERS = float(os.getenv("PCT_OUTLIERS", "0.2"))
FUSO = ZoneInfo(os.getenv("TZ", "America/Sao_Paulo"))
BATIMENTO = Path("/tmp/vivo")

EXAUSTOR = "EXAUSTOR-01"


class Relogio:
    """Hora do AMBIENTE (dia e noite). Comeca na hora real e pode ser
    acelerado: com fator 120, um dia inteiro passa em 12 minutos - e o que
    deixa mostrar o dia virar noite na cena 3D durante a apresentacao."""

    def __init__(self, fator: float):
        agora = datetime.now(FUSO)
        self._hora0 = agora.hour + agora.minute / 60 + agora.second / 3600
        self._dia0 = agora.timetuple().tm_yday
        self._t0 = time.monotonic()
        self.fator = fator

    def _horas_passadas(self) -> float:
        return (time.monotonic() - self._t0) * self.fator / 3600

    @property
    def hora(self) -> float:
        return (self._hora0 + self._horas_passadas()) % 24

    @property
    def dia_do_ano(self) -> float:
        return (self._dia0 + (self._hora0 + self._horas_passadas()) / 24) % 365

    def acelerar(self, fator: float) -> None:
        # rebase: a hora atual vira o novo ponto de partida
        self._hora0, self._dia0 = self.hora, self.dia_do_ano
        self._t0 = time.monotonic()
        self.fator = fator


class Exaustor:
    """O exaustor da coifa, com relogio proprio de operacao.

    Cada leitura publicada vale AMOSTRA_MINUTOS (5 min) de operacao - igual
    a uma linha do dataset do Laboratorio. O desgaste e o ciclo de carga do
    expediente andam nesse relogio, entao o modelo ve ao vivo um exaustor
    que se comporta exatamente como os que ele estudou no treino.
    """

    def __init__(self, rng: np.random.Generator, hora_inicial: float, dia: float):
        self.rng = rng
        # personalidade fixa e perto da nominal: o exaustor "da casa"
        self.base = {chave: valor * rng.uniform(0.97, 1.03) for chave, valor in BASE_NOMINAL.items()}
        self.estado = "ligado"   # coifa ligada no expediente
        self.amostras = 0
        self.hora0, self.dia0 = hora_inicial, dia
        self.offset_cozinha = float(rng.uniform(-1, 1))
        self.temperatura_motor = 25.0 + BASE_NOMINAL["dt0"]
        # falha de equipamento
        self.modo: str | None = None
        self.progresso = 0.0
        self.passo = 0.0
        self.expoente = 2.0
        # falha de sensor
        self.defeito_sensor: dict | None = None
        # depois de um reparo, a proxima leitura sai com estado "manutencao":
        # e o aviso de que a maquina recomecou (a IA zera a referencia dela)
        self.acabou_de_reparar = False

    # ----- quanto o desgaste atrapalha a ventilacao da cozinha -----
    @property
    def eficiencia(self) -> float:
        if self.estado != "ligado":
            return 0.0
        if self.modo == "entupimento":
            return 1.0 - 0.7 * self.nivel
        return 1.0 - 0.2 * self.nivel

    @property
    def nivel(self) -> float:
        if self.modo not in MODOS_EQUIPAMENTO:
            return 0.0
        return float(nivel_degradacao(self.progresso, self.expoente))

    def _hora(self) -> tuple[float, float]:
        horas = self.amostras * AMOSTRA_MINUTOS / 60
        return (self.hora0 + horas) % 24, (self.dia0 + horas / 24) % 365

    def injetar(self, modo: str, horas_ate_falha: float, progresso_inicial: float) -> None:
        if self.estado == "falha":
            log.info("exaustor esta em falha; repare antes de injetar outra")
            return
        amostras_restantes = max(1.0, horas_ate_falha * AMOSTRAS_POR_HORA)
        if modo in MODOS_EQUIPAMENTO:
            self.modo, self.progresso = modo, progresso_inicial
            self.passo = (1.0 - progresso_inicial) / amostras_restantes
            self.defeito_sensor = None
        elif modo in MODOS_SENSOR:
            self.defeito_sensor = {
                "modo": modo,
                "canal": str(self.rng.choice(CANAIS)),
                "k": progresso_inicial * amostras_restantes,
                "duracao": amostras_restantes,
                "congelado": None,
            }
        log.info("FALHA INJETADA: %s, %.0f h de operacao ate a falha (~%.0f s reais)",
                 modo, horas_ate_falha, amostras_restantes * INTERVALO)

    def reparar(self) -> None:
        self.modo, self.progresso, self.passo = None, 0.0, 0.0
        self.defeito_sensor = None
        if self.estado == "falha":
            self.estado = "ligado"
        self.acabou_de_reparar = True
        log.info("exaustor reparado: desgaste zerado")

    def ler(self) -> dict:
        hora, dia = self._hora()
        t_amb = float(temperatura_ambiente(hora, dia)) + self.offset_cozinha + self.rng.normal(0, 0.8)

        if self.estado != "ligado":
            # motor parado: sem rotacao, sem corrente, esfriando devagar
            self.temperatura_motor = t_amb + (self.temperatura_motor - t_amb) * 0.95
            return {
                "vibracao": round(float(abs(self.rng.normal(0.05, 0.02))), 3),
                "corrente": 0.0,
                "temperatura": round(self.temperatura_motor + self.rng.normal(0, 0.3), 2),
                "rpm": 0.0,
            }

        self.amostras += 1
        if self.modo in MODOS_EQUIPAMENTO:
            self.progresso = min(1.0, self.progresso + self.passo)
            if self.progresso >= 1.0:
                self.estado = "falha"
                log.info("EXAUSTOR FALHOU (%s): motor parou", self.modo)
                return self.ler()

        carga = float(carga_exaustor(hora)) * self.rng.normal(1.0, 0.02)
        degradacao = {self.modo: self.nivel} if self.modo in MODOS_EQUIPAMENTO else {}
        valores = {
            canal: float(valor)
            for canal, valor in leituras_exaustor(self.base, carga, t_amb, degradacao, self.rng, RUIDO).items()
        }

        if self.defeito_sensor:
            d = self.defeito_sensor
            canal = d["canal"]
            if d["modo"] == "deriva_sensor":
                d["k"] += 1
                valores[canal] += DERIVA_MAXIMA[canal] * min(1.0, d["k"] / d["duracao"])
            else:
                if d["congelado"] is None:
                    d["congelado"] = valores[canal]
                valores[canal] = d["congelado"]

        self.temperatura_motor = valores["temperatura"]
        return {canal: round(valor, 3) for canal, valor in valores.items()}


class Cozinha:
    def __init__(self):
        self.trava = threading.Lock()
        self.rng = np.random.default_rng(int(os.getenv("SEMENTE", "7")))
        self.relogio = Relogio(FATOR_RELOGIO)
        self.pausado = False
        self.valvula = "aberta"
        self.sirene = "desligado"
        self.vazamento = 0.0
        self.ppm = 230.0
        self.temperatura = float(temperatura_ambiente(self.relogio.hora, self.relogio.dia_do_ano))
        self.umidade = float(umidade_ambiente(self.relogio.hora, self.relogio.dia_do_ano))
        self.nublado = 1.0
        self.exaustor = Exaustor(self.rng, self.relogio.hora, self.relogio.dia_do_ano)

    # ---------------- fisica de um passo ----------------

    def passo(self) -> dict[str, dict]:
        """Avanca INTERVALO segundos e devolve o payload de cada dispositivo."""
        hora, dia = self.relogio.hora, self.relogio.dia_do_ano
        ruido = 0.15 + RUIDO
        exaustor_ligado = self.exaustor.estado == "ligado"

        # --- gas: o vazamento (depois da valvula) soma, a ventilacao tira ---
        base = 220.0 + 40.0 * float(servico(hora))
        fonte = 60.0 * self.vazamento if self.valvula == "aberta" else 0.0  # ppm/s
        retirada = 0.005 + 0.02 * self.exaustor.eficiencia                  # 1/s
        self.ppm += (fonte - retirada * (self.ppm - base)) * INTERVALO
        self.ppm = max(200.0, self.ppm + self.rng.normal(0, 3))

        # --- vazao de gas: bocas do fogao no expediente + o vazamento ---
        if self.valvula == "aberta":
            vazao = 0.15 + 1.4 * float(servico(hora)) + 1.6 * self.vazamento
            vazao = max(0.0, vazao + self.rng.normal(0, 0.03 * ruido))
        else:
            vazao = 0.0

        # --- temperatura e umidade: seguem o alvo com atraso ---
        alvo_t = float(temperatura_ambiente(hora, dia)) - (1.5 if exaustor_ligado else 0.0)
        alvo_u = float(umidade_ambiente(hora, dia)) - (5.0 if exaustor_ligado else 0.0)
        self.temperatura += (alvo_t - self.temperatura) * 0.05
        self.umidade += (alvo_u - self.umidade) * 0.05

        # --- luz na janela: o ceu nubla e abre aos poucos ---
        self.nublado = float(np.clip(self.nublado + self.rng.normal(0, 0.01), 0.5, 1.1))
        lux = float(luminosidade_externa(hora, dia)) * self.nublado

        sensores = {
            "GAS-01": {"ppm": self.ppm + self.rng.normal(0, 10 * ruido)},
            "TEMP-01": {"temperatura": self.temperatura + self.rng.normal(0, 0.15 * ruido)},
            "UMID-01": {"umidade": self.umidade + self.rng.normal(0, 0.8 * ruido)},
            "LUZ-01": {"lux": max(0.0, lux + self.rng.normal(0, 5 * ruido))},
            "VAZAO-01": {"vazao": vazao},
        }
        # Os sensores de ambiente saem so com ruido. Leitura faltante e valor
        # absurdo ficam no exaustor, onde a IA foi preparada para eles: um
        # pico falso no detector de gas fecharia a valvula a toa.
        payloads = {
            codigo: {"codigo": codigo, "leituras": {k: round(float(v), 3) for k, v in leituras.items()}}
            for codigo, leituras in sensores.items()
        }
        estado_exaustor = self.exaustor.estado
        if self.exaustor.acabou_de_reparar and estado_exaustor == "ligado":
            estado_exaustor = "manutencao"
            self.exaustor.acabou_de_reparar = False
        payloads[EXAUSTOR] = {
            "codigo": EXAUSTOR,
            "leituras": self._sujar(self.exaustor.ler()),
            "estado": estado_exaustor,
        }
        payloads["VALVULA-01"] = {"codigo": "VALVULA-01", "estado": self.valvula}
        payloads["SIRENE-01"] = {"codigo": "SIRENE-01", "estado": self.sirene}
        return payloads

    def estado_de(self, codigo: str) -> dict:
        estados = {"VALVULA-01": self.valvula, "SIRENE-01": self.sirene, EXAUSTOR: self.exaustor.estado}
        return {"codigo": codigo, "estado": estados[codigo]}

    def _sujar(self, leituras: dict) -> dict:
        """Como no Laboratorio: de vez em quando falta uma leitura ou chega
        um valor absurdo. As features da IA tratam os dois (ver limpar())."""
        saida = {}
        for campo, valor in leituras.items():
            sorteio = random.random() * 100
            if sorteio < PCT_FALTANTES:
                continue
            if sorteio < PCT_FALTANTES + PCT_OUTLIERS:
                valor = valor * random.choice([-1.0, 0.0, 6.0, 15.0])
            saida[campo] = round(float(valor), 3) if math.isfinite(valor) else None
        return {k: v for k, v in saida.items() if v is not None}

    # ---------------- comandos ----------------

    def comandar(self, codigo: str, acao: str, parametros: dict) -> str | None:
        """Aplica o comando. Devolve o codigo do dispositivo que mudou."""
        if codigo == "VALVULA-01" and acao in ("abrir", "fechar"):
            self.valvula = "aberta" if acao == "abrir" else "fechada"
            return codigo
        if codigo == "SIRENE-01" and acao in ("ligar", "desligar"):
            self.sirene = "ligado" if acao == "ligar" else "desligado"
            return codigo
        if codigo == EXAUSTOR and acao in ("ligar", "desligar"):
            if self.exaustor.estado == "falha":
                log.info("exaustor em falha nao liga: precisa de reparo")
                return codigo
            self.exaustor.estado = "ligado" if acao == "ligar" else "desligado"
            return codigo
        if codigo == "SIMULADOR":
            return self._comandar_simulador(acao, parametros)
        log.warning("comando desconhecido: %s %s", codigo, acao)
        return None

    def _comandar_simulador(self, acao: str, p: dict) -> str | None:
        if acao == "injetar_falha":
            self.exaustor.injetar(p.get("modo", "rolamento"), float(p.get("horas_ate_falha", 24)),
                                  float(p.get("progresso_inicial", 0.35)))
            return EXAUSTOR
        if acao == "reparar":
            self.exaustor.reparar()
            return EXAUSTOR
        if acao == "vazamento":
            self.vazamento = float(np.clip(p.get("intensidade", 0.0), 0.0, 1.0))
            log.info("vazamento de gas: intensidade %.2f", self.vazamento)
        elif acao == "relogio":
            self.relogio.acelerar(float(p.get("fator", 1)))
            log.info("relogio do ambiente: %.0fx", self.relogio.fator)
        elif acao == "pausar":
            self.pausado = True
            log.info("PAUSADO: nenhuma leitura sera publicada")
        elif acao == "retomar":
            self.pausado = False
            log.info("retomado")
        return None


def main() -> None:
    cozinha = Cozinha()
    conectado = threading.Event()

    def publicar(payloads: dict[str, dict]) -> None:
        for codigo, payload in payloads.items():
            cliente.publish(f"gasguard/{codigo}/telemetria", json.dumps(payload), qos=1)

    def ao_conectar(cli, _dados, _flags, codigo_razao, _props):
        if codigo_razao.is_failure:
            log.error("MQTT recusou a conexao: %s", codigo_razao)
            return
        log.info("MQTT: conectado em %s:%s", MQTT_HOST, MQTT_PORT)
        cli.subscribe("gasguard/+/comando", qos=1)
        conectado.set()

    def ao_desconectar(_cli, _dados, _flags, codigo_razao, _props):
        conectado.clear()
        log.warning("MQTT: desconectado (%s)", codigo_razao)

    def ao_receber(_cli, _dados, mensagem):
        codigo = mensagem.topic.split("/")[1]
        try:
            comando = json.loads(mensagem.payload)
        except ValueError:
            log.warning("comando ilegivel em %s", mensagem.topic)
            return
        acao = comando.get("acao", "")
        with cozinha.trava:
            mudou = cozinha.comandar(codigo, acao, comando.get("parametros") or {})
            log.info("comando %s -> %s (origem %s)", acao, codigo, comando.get("origem"))
            # o estado novo sai na hora, sem esperar o proximo ciclo (so o
            # estado: as leituras continuam no ritmo normal)
            if mudou and not cozinha.pausado:
                publicar({mudou: cozinha.estado_de(mudou)})

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gasguard-simulador")
    cliente.username_pw_set(MQTT_USUARIO, MQTT_SENHA)
    cliente.on_connect = ao_conectar
    cliente.on_disconnect = ao_desconectar
    cliente.on_message = ao_receber
    cliente.reconnect_delay_set(min_delay=1, max_delay=15)
    cliente.connect_async(MQTT_HOST, MQTT_PORT)
    cliente.loop_start()

    log.info("simulando a cozinha a cada %.1f s (relogio do ambiente %.0fx)", INTERVALO, FATOR_RELOGIO)
    ultimo_log = 0.0
    while True:
        inicio = time.monotonic()
        if conectado.is_set():
            with cozinha.trava:
                if not cozinha.pausado:
                    publicar(cozinha.passo())
                ex = cozinha.exaustor
                if time.monotonic() - ultimo_log > 30:
                    ultimo_log = time.monotonic()
                    log.info(
                        "hora %.1f | gas %.0f ppm | valvula %s | exaustor %s | desgaste %s %.0f%% "
                        "(saude real %.0f - nao publicada)",
                        cozinha.relogio.hora, cozinha.ppm, cozinha.valvula, ex.estado,
                        ex.modo or "-", 100 * ex.progresso, 100 * (1 - ex.nivel),
                    )
            BATIMENTO.touch()
        time.sleep(max(0.0, INTERVALO - (time.monotonic() - inicio)))


if __name__ == "__main__":
    main()
