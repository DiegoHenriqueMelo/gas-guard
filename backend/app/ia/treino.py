"""Treino dos dois modelos de regressao a partir de um dataset do Laboratorio.

    saude      -- indice de saude do exaustor, de 0 a 100
    rul_horas  -- vida util restante: horas ate a falha (teto de 96 h)

Os dois usam as mesmas 24 features (app/ia/features.py) e o mesmo algoritmo,
HistGradientBoostingRegressor do scikit-learn: arvores de decisao em
sequencia, cada uma corrigindo o erro das anteriores. Treina rapido em
centenas de milhares de linhas e lida bem com relacoes nao lineares (o dano
de rolamento cresce como uma curva, nao como uma reta).

Tres cuidados que separam um modelo que funciona ao vivo de um que so
parece bom no teste:

1. DIVISAO POR EQUIPAMENTO. Treino, validacao e teste recebem MAQUINAS
   diferentes. Se a divisao fosse por linha, a leitura das 10h05 de uma
   maquina iria para o treino e a das 10h10 para o teste - quase iguais. O
   modelo "decoraria" cada maquina e a nota sairia inflada.
2. BASE SIMPLES. Comparamos com um "modelo" que sempre responde a media do
   treino. Se o nosso nao vencer isso com folga, ele nao aprendeu nada.
3. MESMAS FEATURES DA INFERENCIA. calcular_features e a mesma funcao que o
   servico de inferencia chama ao vivo.
"""

import json
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from app.core import config
from app.ia.features import FEATURES, JANELA_CURTA, JANELA_LONGA, JANELA_MEDIA, MIN_AMOSTRAS, calcular_features
from app.lab.gerador import pasta_do_dataset
from comum.fisica import CANAIS, MODOS_EQUIPAMENTO, MODOS_FALHA, RUL_MAXIMO_HORAS

log = logging.getLogger(__name__)

ALVOS = {
    "saude": {"nome": "Índice de saúde", "unidade": "pontos", "limites": (0.0, 100.0)},
    "rul_horas": {"nome": "Vida útil restante", "unidade": "h", "limites": (0.0, RUL_MAXIMO_HORAS)},
}

Progresso = Callable[[float, str], None]

# Funcao de perda das arvores. Com erro absoluto o modelo mira a MEDIANA:
# numa maquina saudavel ele responde 100 e 96 h cravados, em vez de 97 e
# 90 "puxados" pelos poucos exemplos de maquina doente.
PERDA = "absolute_error"


def pasta_do_modelo(versao: str) -> Path:
    return config.DIR_MODELOS / versao


def _carregar(pasta: Path, max_linhas: int, progresso: Progresso) -> pd.DataFrame:
    """Le o dataset e calcula as features maquina por maquina."""
    meta = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))
    # amostragem: uma linha a cada `passo`, para caber em max_linhas
    passo = max(1, math.ceil(meta["linhas_exaustor"] / max_linhas))

    arquivos = sorted(pasta.glob("exaustores_*.npz"))
    if not arquivos:
        raise FileNotFoundError(f"dataset vazio em {pasta}")

    partes = []
    for n, arquivo in enumerate(arquivos):
        with np.load(arquivo) as dados:
            bruto = pd.DataFrame({chave: dados[chave] for chave in dados.files})
        for equipamento, linhas in bruto.groupby("equipamento", sort=False):
            linhas = linhas.sort_values("t")
            features = calcular_features(linhas[list(CANAIS)].reset_index(drop=True))
            features["equipamento"] = int(equipamento)
            for rotulo in ("saude", "rul_horas", "degradando", "modo"):
                features[rotulo] = linhas[rotulo].to_numpy()
            # descarta o aquecimento (ao vivo o servico tambem nao preve com
            # menos de MIN_AMOSTRAS) e amostra a cada `passo` linhas
            partes.append(features.iloc[MIN_AMOSTRAS::passo])
        progresso(0.05 + 0.35 * (n + 1) / len(arquivos), f"features: arquivo {n + 1} de {len(arquivos)}")

    return pd.concat(partes, ignore_index=True)


def _dividir_por_equipamento(dados: pd.DataFrame, semente: int) -> dict[str, set[int]]:
    """70% das maquinas para treino, 15% validacao, 15% teste.

    Estratificado: as que falham e as que nao falham sao divididas
    separadamente, senao o teste poderia ficar sem nenhuma maquina doente.
    """
    rng = np.random.default_rng(semente)
    falham_mesmo = {MODOS_FALHA.index(m) for m in MODOS_EQUIPAMENTO}
    por_maquina = dados.groupby("equipamento")["modo"].first()
    grupos = [
        por_maquina[por_maquina.isin(falham_mesmo)].index.to_numpy(),
        por_maquina[~por_maquina.isin(falham_mesmo)].index.to_numpy(),
    ]
    divisao = {"treino": set(), "validacao": set(), "teste": set()}
    for grupo in grupos:
        grupo = rng.permutation(grupo)
        n = len(grupo)
        n_teste = max(1, round(0.15 * n)) if n >= 3 else 0
        n_val = max(1, round(0.15 * n)) if n >= 3 else 0
        divisao["teste"].update(grupo[:n_teste].tolist())
        divisao["validacao"].update(grupo[n_teste:n_teste + n_val].tolist())
        divisao["treino"].update(grupo[n_teste + n_val:].tolist())
    return divisao


def _metricas(real: np.ndarray, previsto: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(real, previsto)),
        "rmse": float(root_mean_squared_error(real, previsto)),
        "r2": float(r2_score(real, previsto)) if len(np.unique(real)) > 1 else 0.0,
    }


def _dispersao(real, previsto, degradando, rng, n=500) -> list[list[float]]:
    """Pontos para o grafico previsto x real. Metade vem de linhas em
    degradacao: sao poucas, e sao as que interessam."""
    indices = np.arange(len(real))
    doentes, saudaveis = indices[degradando], indices[~degradando]
    escolhidos = np.concatenate([
        rng.choice(doentes, min(len(doentes), n // 2), replace=False) if len(doentes) else [],
        rng.choice(saudaveis, min(len(saudaveis), n // 2), replace=False) if len(saudaveis) else [],
    ]).astype(int)
    return [[round(float(real[i]), 2), round(float(previsto[i]), 2)] for i in escolhidos]


def treinar(versao: str, dataset_job_id: int, max_linhas: int, progresso: Progresso) -> dict:
    inicio = time.monotonic()
    pasta = pasta_do_dataset(dataset_job_id)
    if not (pasta / "meta.json").exists():
        raise FileNotFoundError(f"dataset ds{dataset_job_id} nao encontrado (foi gerado?)")
    meta = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))

    progresso(0.02, "lendo o dataset")
    dados = _carregar(pasta, max_linhas, progresso)
    # o teto vale o de AGORA: um dataset gerado com teto antigo continua
    # utilizavel, sem ensinar ao modelo numeros acima do que ele pode prever
    dados["rul_horas"] = dados["rul_horas"].clip(upper=RUL_MAXIMO_HORAS)

    divisao = _dividir_por_equipamento(dados, meta["parametros"]["semente"])
    if not divisao["teste"] or not divisao["treino"]:
        raise ValueError("maquinas de menos para dividir em treino e teste (gere ao menos 10)")
    conjuntos = {nome: dados[dados["equipamento"].isin(ids)] for nome, ids in divisao.items()}
    progresso(0.42, "dados divididos por equipamento")

    rng = np.random.default_rng(0)
    modelos, resultado = {}, {}
    for n, (alvo, info) in enumerate(ALVOS.items()):
        base = 0.42 + 0.27 * n
        treino, val, teste = conjuntos["treino"], conjuntos["validacao"], conjuntos["teste"]

        progresso(base + 0.02, f"treinando {info['nome'].lower()}")
        modelo = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.08,
            max_leaf_nodes=31,
            min_samples_leaf=40,
            l2_regularization=1.0,
            loss=PERDA,
            early_stopping=False,
            random_state=0,
        )
        modelo.fit(treino[FEATURES], treino[alvo])
        # a "base simples": sempre responde a media do treino
        media = DummyRegressor(strategy="mean").fit(treino[FEATURES], treino[alvo])

        minimo, maximo = info["limites"]
        avaliacao = {}
        for nome, conjunto in (("validacao", val), ("teste", teste)):
            if conjunto.empty:
                continue
            previsto = np.clip(modelo.predict(conjunto[FEATURES]), minimo, maximo)
            avaliacao[nome] = {
                "modelo": _metricas(conjunto[alvo].to_numpy(), previsto),
                "base": _metricas(conjunto[alvo].to_numpy(), media.predict(conjunto[FEATURES])),
                "linhas": int(len(conjunto)),
            }

        previsto_teste = np.clip(modelo.predict(teste[FEATURES]), minimo, maximo)
        degradando = teste["degradando"].to_numpy(dtype=bool)
        if degradando.any():
            # so as linhas de maquinas degradando: onde o erro custa caro
            avaliacao["teste_degradando"] = {
                "modelo": _metricas(teste[alvo].to_numpy()[degradando], previsto_teste[degradando]),
                "base": _metricas(
                    teste[alvo].to_numpy()[degradando],
                    media.predict(teste[FEATURES])[degradando],
                ),
                "linhas": int(degradando.sum()),
            }

        progresso(base + 0.18, f"importância dos atributos: {info['nome'].lower()}")
        amostra = teste.sample(min(len(teste), 6000), random_state=0)
        importancia = permutation_importance(
            modelo, amostra[FEATURES], amostra[alvo],
            scoring="neg_mean_absolute_error", n_repeats=3, random_state=0,
        )
        ranking = sorted(
            zip(FEATURES, importancia.importances_mean, strict=True),
            key=lambda par: par[1], reverse=True,
        )

        teste_mae = avaliacao["teste"]["modelo"]["mae"]
        base_mae = avaliacao["teste"]["base"]["mae"]
        resultado[alvo] = {
            **info,
            "limites": list(info["limites"]),
            "avaliacao": avaliacao,
            "venceu_base": teste_mae < base_mae,
            "ganho_sobre_base_pct": round(100 * (1 - teste_mae / base_mae), 1) if base_mae else 0.0,
            "importancia": [[nome, round(float(valor), 4)] for nome, valor in ranking[:12]],
            "dispersao": _dispersao(teste[alvo].to_numpy(), previsto_teste, degradando, rng),
        }
        modelos[alvo] = modelo

    progresso(0.95, "salvando os modelos")
    pasta_saida = pasta_do_modelo(versao)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    pacote = {
        "versao": versao,
        "features": FEATURES,
        "modelos": modelos,
        "limites": {alvo: info["limites"] for alvo, info in ALVOS.items()},
        "criado_em": datetime.now(UTC).isoformat(),
    }
    caminho = pasta_saida / "modelo.joblib"
    joblib.dump(pacote, caminho)

    return {
        "versao": versao,
        "caminho": str(caminho),
        "venceu_base": all(r["venceu_base"] for r in resultado.values()),
        "alvos": resultado,
        "dados": {
            "dataset": meta["dataset"],
            "linhas_usadas": int(len(dados)),
            "maquinas": {nome: len(ids) for nome, ids in divisao.items()},
            "maquinas_teste": sorted(int(i) for i in divisao["teste"]),
            "features": len(FEATURES),
            "janelas": {"curta": JANELA_CURTA, "media": JANELA_MEDIA, "longa": JANELA_LONGA},
        },
        "segundos": round(time.monotonic() - inicio, 1),
    }
