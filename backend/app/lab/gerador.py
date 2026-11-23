"""Gerador de dados sinteticos: a vida inteira de dezenas de exaustores.

Equipamento de verdade leva meses para falhar. Para ter exemplos de
maquinas degradando suficientes para treinar, simulamos a operacao inteira
de uma frota: cada exaustor tem a sua "personalidade", alguns falham por um
dos modos escolhidos, outros so tem um sensor com defeito.

Regras de qualidade (pedidas no enunciado e respeitadas aqui):
  - degradacao PROGRESSIVA: o dano cresce aos poucos ate a falha;
  - ruido e sobreposicao entre maquinas saudaveis e doentes;
  - ciclo diario (expediente, dia e noite) e de estacao do ano;
  - rotulos de verdade em toda linha: saude, vida util restante,
    se esta degradando. Ficam SO no dataset; nunca vao para o ao vivo;
  - numpy em blocos: cada exaustor e um bloco vetorizado de dezenas de
    milhares de instantes, nunca um laco ponto a ponto;
  - teto de leituras para nao travar a maquina (LAB_MAX_LEITURAS).

Saida, em /dados/datasets/ds<job>/:
  exaustores_<bloco>.npz  -- leituras e rotulos, 10 maquinas por arquivo
  ambiente.npz            -- sensores de ambiente (gas, temperatura...)
  meta.json               -- parametros e contagens
"""

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.core import config, influx
from app.lab.schemas import TIPOS_AMBIENTE, ParametrosGeracao
from comum.fisica import (
    AMOSTRA_MINUTOS,
    AMOSTRAS_POR_DIA,
    AMOSTRAS_POR_HORA,
    CANAIS,
    DERIVA_MAXIMA,
    MODOS_EQUIPAMENTO,
    MODOS_FALHA,
    MODOS_SENSOR,
    RUL_MAXIMO_HORAS,
    base_do_equipamento,
    carga_exaustor,
    leituras_exaustor,
    luminosidade_externa,
    nivel_degradacao,
    saude_real,
    servico,
    temperatura_ambiente,
    umidade_ambiente,
)

log = logging.getLogger(__name__)

MAQUINAS_POR_ARQUIVO = 10

# Quanto tempo, em dias de operacao, vai do inicio do desgaste ate a falha.
# Precisa cobrir o que a falha injetada ao vivo produz (algumas dezenas de
# horas), senao o modelo ve ao vivo uma degradacao mais rapida do que
# qualquer uma que estudou.
DIAS_DE_DEGRADACAO = (1.0, 4.0)

Progresso = Callable[[float, str], None]


class TetoExcedido(ValueError):
    pass


def pasta_do_dataset(job_id: int) -> Path:
    return config.DIR_DADOS / "datasets" / f"ds{job_id}"


def _sujar(x: np.ndarray, rng, pct_faltantes: float, pct_outliers: float) -> np.ndarray:
    """Leitura faltante vira NaN; outlier vira valor absurdo (negativo,
    zero ou varias vezes maior). Mesmo tratamento para todo sensor."""
    x = x.astype(np.float32, copy=True)
    n = len(x)
    absurdo = rng.random(n) < pct_outliers / 100
    fator = rng.choice(np.array([-1.0, 0.0, 6.0, 15.0], dtype=np.float32), size=n)
    x = np.where(absurdo, x * fator, x)
    x[rng.random(n) < pct_faltantes / 100] = np.nan
    return x


def _exaustor(i: int, falha: bool, p: ParametrosGeracao, tempo: dict) -> dict:
    """Simula a vida de UM exaustor, toda de uma vez (vetorizado)."""
    # Um gerador aleatorio por maquina, derivado da semente: a maquina 7 sai
    # igual mesmo que o numero de maquinas mude. E isso que torna a geracao
    # reproduzivel.
    rng = np.random.default_rng([p.semente, i])
    total = tempo["total"]
    t = np.arange(total)

    modo = str(rng.choice(p.modos)) if falha and p.modos else None
    base = base_do_equipamento(rng)

    nivel = np.zeros(total)
    rul = np.full(total, RUL_MAXIMO_HORAS)
    comprimento = total

    if modo in MODOS_EQUIPAMENTO:
        # instante da falha: depois de 35% do periodo, para haver historico
        # saudavel antes; a degradacao comeca de 1 a 4 dias antes dela
        fim = int(rng.integers(int(0.35 * total), total))
        duracao = min(int(rng.uniform(*DIAS_DE_DEGRADACAO) * AMOSTRAS_POR_DIA), fim)
        inicio = fim - duracao
        expoente = rng.uniform(1.6, 2.6)
        nivel = nivel_degradacao((t - inicio) / max(duracao, 1), expoente)
        rul = np.minimum((fim - t) / AMOSTRAS_POR_HORA, RUL_MAXIMO_HORAS)
        # a serie termina na falha: a maquina parou
        comprimento = fim + 1

    fatia = slice(0, comprimento)
    hora = tempo["hora"][fatia]
    dia = tempo["dia_do_ano"][fatia]

    # cada cozinha e um pouco mais quente ou mais fria; cada dia tem um
    # movimento diferente no restaurante
    temp_ambiente = (
        temperatura_ambiente(hora, dia)
        + rng.uniform(-2.0, 2.0)
        + rng.normal(0.0, 0.8, comprimento)
    )
    movimento_do_dia = rng.normal(1.0, 0.05, p.dias + 1)[tempo["indice_dia"][fatia]]
    carga = np.clip(carga_exaustor(hora) * movimento_do_dia, 0.5, 1.1)

    degradacao = {modo: nivel[fatia]} if modo in MODOS_EQUIPAMENTO else {}
    leituras = leituras_exaustor(base, carga, temp_ambiente, degradacao, rng, p.ruido)

    if modo in MODOS_SENSOR:
        # defeito de sensor num trecho do periodo; a maquina continua saudavel
        canal = str(rng.choice(CANAIS))
        de = int(rng.integers(int(0.2 * comprimento), int(0.8 * comprimento)))
        ate = min(comprimento, de + int(rng.uniform(1, 5) * AMOSTRAS_POR_DIA))
        if modo == "deriva_sensor":
            rampa = np.linspace(0.0, 1.0, ate - de)
            leituras[canal][de:ate] = leituras[canal][de:ate] + DERIVA_MAXIMA[canal] * rampa
        else:
            leituras[canal][de:ate] = leituras[canal][de]

    saida = {
        "equipamento": np.full(comprimento, i, dtype=np.int32),
        "t": t[fatia].astype(np.int32),
        "instante": tempo["instante"][fatia],
        "saude": saude_real(nivel[fatia]).astype(np.float32),
        "rul_horas": rul[fatia].astype(np.float32),
        "degradando": nivel[fatia] > 0,
        "modo": np.full(comprimento, MODOS_FALHA.index(modo) if modo else -1, dtype=np.int8),
    }
    for canal in CANAIS:
        saida[canal] = _sujar(leituras[canal], rng, p.pct_faltantes, p.pct_outliers)
    return saida


def _sensor_ambiente(tipo: str, k: int, p: ParametrosGeracao, tempo: dict) -> np.ndarray:
    rng = np.random.default_rng([p.semente, 100_000 + TIPOS_AMBIENTE.index(tipo) * 1000 + k])
    hora, dia = tempo["hora"], tempo["dia_do_ano"]
    total = tempo["total"]
    escala = 0.15 + p.ruido

    if tipo == "gas":
        valor = 220.0 + 40.0 * servico(hora) + rng.normal(0, 15 * escala, total)
        # vazamentos de verdade sao raros: um a cada ~15 dias, subindo rapido
        # e caindo conforme o ambiente ventila
        for _ in range(rng.poisson(max(p.dias / 15, 0.2))):
            inicio = int(rng.integers(0, total))
            depois = np.arange(total - inicio)
            valor[inicio:] += rng.uniform(800, 3000) * np.exp(-depois / rng.uniform(10, 40))
        valor = np.maximum(valor, 200.0)
    elif tipo == "temperatura":
        valor = temperatura_ambiente(hora, dia) + rng.uniform(-2, 2) + rng.normal(0, 0.6 * escala, total)
    elif tipo == "umidade":
        valor = umidade_ambiente(hora, dia) + rng.normal(0, 2.0 * escala, total)
    else:
        nublado = rng.uniform(0.5, 1.1, p.dias + 1)[tempo["indice_dia"]]
        valor = luminosidade_externa(hora, dia) * nublado + rng.normal(0, 8 * escala, total)
        valor = np.maximum(valor, 0.0)

    return _sujar(valor, rng, p.pct_faltantes, p.pct_outliers)


def _amostra_no_influx(job_id: int, pasta: Path, p: ParametrosGeracao, escolhidas: list[int]):
    """Grava um pedaco do dataset no bucket "lab" para explorar na interface
    do InfluxDB. Nunca no bucket ao vivo: dado sintetico misturado com real
    estragaria o painel e o historico."""
    from influxdb_client import Point

    influx.garantir_bucket(config.INFLUX_BUCKET_LAB)
    dataset = f"ds{job_id}"
    influx.apagar_serie_lab(dataset)

    pontos: list = []

    def descarregar(forcar: bool = False):
        if pontos and (forcar or len(pontos) >= 5000):
            influx.gravar(pontos, bucket=config.INFLUX_BUCKET_LAB)
            pontos.clear()

    for arquivo in sorted(pasta.glob("exaustores_*.npz")):
        with np.load(arquivo) as dados:
            for i in np.unique(dados["equipamento"]):
                if int(i) not in escolhidas:
                    continue
                linhas = np.flatnonzero(dados["equipamento"] == i)[::3]
                modo = int(dados["modo"][linhas[0]])
                for linha in linhas:
                    ponto = (
                        Point(influx.MEDIDA_LAB_EXAUSTOR)
                        .tag("dataset", dataset)
                        .tag("equipamento", f"EXA-{int(i):03d}")
                        .tag("modo", MODOS_FALHA[modo] if modo >= 0 else "saudavel")
                        .time(int(dados["instante"][linha]) * 1_000_000_000)
                        .field("saude", float(dados["saude"][linha]))
                        .field("rul_horas", float(dados["rul_horas"][linha]))
                    )
                    for canal in CANAIS:
                        valor = float(dados[canal][linha])
                        if np.isfinite(valor):
                            ponto.field(canal, valor)
                    pontos.append(ponto)
                    descarregar()

    with np.load(pasta / "ambiente.npz") as dados:
        nomes = list(dados["nomes"])
        for tipo in TIPOS_AMBIENTE:
            sensor = f"{tipo.upper()}-S01"
            if sensor not in nomes:
                continue
            serie = dados["valores"][nomes.index(sensor)]
            for coluna in range(0, len(serie), 6):
                valor = float(serie[coluna])
                if not np.isfinite(valor):
                    continue
                pontos.append(
                    Point(influx.MEDIDA_LAB_AMBIENTE)
                    .tag("dataset", dataset)
                    .tag("sensor", sensor)
                    .tag("tipo", tipo)
                    .time(int(dados["instante"][coluna]) * 1_000_000_000)
                    .field("valor", valor)
                )
                descarregar()
    descarregar(forcar=True)


def gerar(job_id: int, p: ParametrosGeracao, progresso: Progresso) -> dict:
    estimadas = p.leituras_estimadas()
    if estimadas > config.LAB_MAX_LEITURAS:
        raise TetoExcedido(
            f"{estimadas:,} leituras passam do teto de {config.LAB_MAX_LEITURAS:,}"
        )

    inicio_relogio = time.monotonic()
    pasta = pasta_do_dataset(job_id)
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.glob("*"):
        velho.unlink()

    # ---------- a linha do tempo, igual para todas as maquinas ----------
    rng = np.random.default_rng(p.semente)
    total = p.dias * AMOSTRAS_POR_DIA
    horas = np.arange(total) * AMOSTRA_MINUTOS / 60.0
    dia_inicial = int(rng.integers(0, 365))
    # o dataset termina "agora", para a amostra no Influx cair num periodo
    # facil de achar na interface (ultimos N dias)
    fim = int(time.time()) // 300 * 300
    tempo = {
        "total": total,
        "hora": horas % 24,
        "dia_do_ano": (dia_inicial + horas / 24.0) % 365,
        "indice_dia": (horas // 24).astype(np.int64),
        "instante": fim - (total - np.arange(total, dtype=np.int64)) * AMOSTRA_MINUTOS * 60,
    }

    # quem falha e sorteado sem reposicao: o percentual sai exato
    quantos_falham = round(p.equipamentos * p.pct_falha / 100)
    falham = set(rng.permutation(p.equipamentos)[:quantos_falham].tolist())

    # ---------- exaustores, em blocos ----------
    linhas_exaustor = 0
    resumo_modos: dict[str, int] = {}
    bloco: list[dict] = []
    escolhidas_influx: list[int] = []

    def salvar_bloco():
        if not bloco:
            return
        juntos = {chave: np.concatenate([b[chave] for b in bloco]) for chave in bloco[0]}
        numero = len(list(pasta.glob("exaustores_*.npz")))
        np.savez(pasta / f"exaustores_{numero:03d}.npz", **juntos)
        bloco.clear()

    for i in range(p.equipamentos):
        maquina = _exaustor(i, i in falham, p, tempo)
        bloco.append(maquina)
        linhas_exaustor += len(maquina["t"])

        codigo_modo = int(maquina["modo"][0])
        nome_modo = MODOS_FALHA[codigo_modo] if codigo_modo >= 0 else "saudavel"
        resumo_modos[nome_modo] = resumo_modos.get(nome_modo, 0) + 1
        # para a amostra: duas que falham de verdade e uma saudavel
        quer_falha = nome_modo in MODOS_EQUIPAMENTO and sum(
            1 for j in escolhidas_influx if j in falham) < 2
        quer_saudavel = nome_modo == "saudavel" and not any(
            j not in falham for j in escolhidas_influx)
        if quer_falha or quer_saudavel:
            escolhidas_influx.append(i)

        if len(bloco) >= MAQUINAS_POR_ARQUIVO:
            salvar_bloco()
        progresso(0.8 * (i + 1) / p.equipamentos, f"exaustor {i + 1} de {p.equipamentos}")
    salvar_bloco()

    # ---------- sensores de ambiente ----------
    # Uma linha por sensor (matriz sensores x instantes), com os nomes a
    # parte: repetir o texto "TEMPERATURA-S01" milhoes de vezes ocuparia
    # mais memoria que as proprias leituras.
    nomes, tipos, series = [], [], []
    for tipo in TIPOS_AMBIENTE:
        for k in range(getattr(p.sensores_ambiente, tipo)):
            nomes.append(f"{tipo.upper()}-S{k + 1:02d}")
            tipos.append(tipo)
            series.append(_sensor_ambiente(tipo, k, p, tempo))
    leituras_ambiente = total * len(series)
    np.savez(
        pasta / "ambiente.npz",
        nomes=np.array(nomes, dtype="<U20"),
        tipos=np.array(tipos, dtype="<U20"),
        instante=tempo["instante"],
        valores=np.stack(series) if series else np.zeros((0, total), np.float32),
    )
    progresso(0.85, "sensores de ambiente gerados")

    leituras = linhas_exaustor * len(CANAIS) + leituras_ambiente
    meta = {
        "dataset": f"ds{job_id}",
        "parametros": p.model_dump(),
        "linhas_exaustor": linhas_exaustor,
        "leituras": leituras,
        "leituras_ambiente": leituras_ambiente,
        "modos": resumo_modos,
        "maquinas_que_falham": sum(resumo_modos.get(m, 0) for m in MODOS_EQUIPAMENTO),
        "amostra_minutos": AMOSTRA_MINUTOS,
        "inicio": int(tempo["instante"][0]),
        "fim": int(tempo["instante"][-1]),
    }

    if p.amostra_influx:
        progresso(0.88, "gravando amostra no bucket lab do InfluxDB")
        _amostra_no_influx(job_id, pasta, p, escolhidas_influx)
        meta["amostra_influx"] = [f"EXA-{i:03d}" for i in escolhidas_influx]

    meta["tamanho_mb"] = round(sum(f.stat().st_size for f in pasta.glob("*")) / 1e6, 1)
    meta["segundos"] = round(time.monotonic() - inicio_relogio, 1)
    (pasta / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    progresso(1.0, "concluido")
    return meta
