"""As variaveis de entrada (features) dos modelos. Um codigo so, dois usos.

- No TREINO, `calcular_features` recebe a vida inteira de um exaustor
  (dezenas de milhares de linhas) e devolve uma linha de features por
  instante.
- Na INFERENCIA ao vivo, recebe as ultimas JANELA_LONGA leituras do exaustor
  e o servico usa so a ultima linha.

Se o treino e a inferencia tivessem cada um o seu calculo, bastaria uma
diferenca de arredondamento ou de janela para o modelo receber, ao vivo,
numeros que ele nunca viu ("training-serving skew"). Aqui e impossivel: e a
mesma funcao.

Todas as janelas olham SO PARA O PASSADO. O `rolling` do pandas termina na
linha atual por padrao; nada aqui usa shift negativo, media centrada ou
estatistica da serie inteira. Usar o futuro seria vazamento de dados: o
modelo pareceria otimo no teste e seria inutil ao vivo, onde o futuro nao
existe ainda.

As janelas contam AMOSTRAS (1 amostra = 5 min de operacao, ver
comum/fisica.py), entao valem igual para o laboratorio e para o simulador.

A REFERENCIA da maquina: cada exaustor tem a sua "personalidade" (um vibra
1,2 mm/s novo, outro 2,3). Comparar com um numero fixo confunde maquina
naturalmente agitada com maquina doente - foi exatamente o que o primeiro
modelo que treinamos fez. Por isso cada canal tambem e comparado com a media
das primeiras REFERENCIA amostras (24 h) desde a instalacao ou a ultima
manutencao. Ao vivo, o servico de inferencia guarda essas primeiras amostras
e as entrega a esta funcao junto com as mais recentes (ver
montar_janela_ao_vivo).
"""

import numpy as np
import pandas as pd

from comum.fisica import AMOSTRAS_POR_HORA, BASE_NOMINAL, CANAIS

JANELA_CURTA = 6     # 30 min: o que esta acontecendo agora
JANELA_MEDIA = 36    # 3 h: variacao e tendencia recentes
JANELA_LONGA = 144   # 12 h: o patamar recente
REFERENCIA = 288     # 24 h: como esta maquina era logo depois de instalada

# Com menos que isso a previsao ainda nao vale (o servico avisa "aquecendo").
# No treino, as primeiras linhas de cada maquina tambem sao descartadas.
MIN_AMOSTRAS = 12

# Fora destes limites a leitura e fisicamente impossivel para este exaustor:
# e defeito de sensor ou de transmissao, nao desgaste.
LIMITES_FISICOS = {
    "vibracao": (0.0, 60.0),
    "corrente": (0.0, 20.0),
    "temperatura": (-10.0, 200.0),
    "rpm": (100.0, 2500.0),
}

# Valor usado quando nao ha leitura valida nenhuma ainda (comeco da serie).
NOMINAL = {
    "vibracao": BASE_NOMINAL["vib0"],
    "corrente": BASE_NOMINAL["corr0"],
    "temperatura": 25.0 + BASE_NOMINAL["dt0"],
    "rpm": BASE_NOMINAL["rpm0"],
}


def _nomes() -> list[str]:
    nomes = []
    for canal in CANAIS:
        nomes += [
            f"{canal}_media_curta",
            f"{canal}_media_longa",
            f"{canal}_desvio",
            f"{canal}_maximo",
            f"{canal}_tendencia_h",
            f"{canal}_tendencia_longa_h",
            f"{canal}_delta",
            f"{canal}_vs_referencia",
        ]
    return nomes


FEATURES = _nomes()  # 8 por canal x 4 canais = 32, sempre nesta ordem


def limpar(leituras: pd.DataFrame) -> pd.DataFrame:
    """Trata leitura faltante e valor absurdo, olhando so para tras.

    1. valor fora dos limites fisicos vira "faltante";
    2. pico isolado (mais de 3x ou menos de 1/3 da mediana das 12 leituras
       ANTERIORES) tambem vira "faltante" - pega o absurdo que ainda cabe
       nos limites fisicos, como uma vibracao de 25 mm/s do nada;
    3. faltante repete a ultima leitura valida (ffill: so o passado);
    4. se ainda nao houve leitura valida, usa o valor nominal.

    Note o que NAO fazemos: preencher com a media da serie inteira. Seria
    pratico e seria vazamento - a media inclui o futuro.
    """
    limpo = pd.DataFrame(index=leituras.index)
    for canal in CANAIS:
        serie = pd.to_numeric(leituras[canal], errors="coerce").astype("float64")
        minimo, maximo = LIMITES_FISICOS[canal]
        serie = serie.where((serie >= minimo) & (serie <= maximo))

        # shift(1): a mediana de referencia termina na leitura ANTERIOR
        referencia = serie.shift(1).rolling(12, min_periods=3).median()
        pico = (serie > 3 * referencia) | (serie < referencia / 3)
        serie = serie.where(~pico)

        limpo[canal] = serie.ffill().fillna(NOMINAL[canal])
    return limpo


def _inclinacao(serie: pd.Series, janela: int) -> pd.Series:
    """Inclinacao da reta de minimos quadrados nas ultimas `janela` amostras.

    inclinacao = cov(x, t) / var(t), com t = 0, 1, 2... Resultado em
    unidades por amostra; multiplicamos por amostras/hora fora daqui.
    """
    tempo = pd.Series(np.arange(len(serie), dtype="float64"), index=serie.index)
    covariancia = serie.rolling(janela, min_periods=3).cov(tempo)
    variancia = tempo.rolling(janela, min_periods=3).var()
    return (covariancia / variancia).fillna(0.0)


def _referencia(serie: pd.Series) -> pd.Series:
    """Media das primeiras REFERENCIA amostras da serie, sem olhar o futuro.

    Na linha k (k < REFERENCIA) e a media das linhas 0..k; dali em diante
    fica congelada na media das primeiras REFERENCIA linhas.
    """
    referencia = serie.expanding(min_periods=1).mean()
    if len(serie) > REFERENCIA:
        referencia.iloc[REFERENCIA:] = referencia.iloc[REFERENCIA - 1]
    return referencia


def calcular_features(leituras: pd.DataFrame) -> pd.DataFrame:
    """Leituras de UM exaustor, em ordem de tempo -> features por linha.

    `leituras` precisa ter as colunas vibracao, corrente, temperatura, rpm,
    e a primeira linha precisa ser a primeira leitura desde a instalacao ou
    a ultima manutencao (e dali que sai a referencia da maquina).
    Devolve um DataFrame com as colunas de FEATURES, mesmo indice.
    """
    limpo = limpar(leituras)
    saida = {}
    for canal in CANAIS:
        x = limpo[canal]
        curta = x.rolling(JANELA_CURTA, min_periods=1).mean()
        longa = x.rolling(JANELA_LONGA, min_periods=1).mean()
        saida[f"{canal}_media_curta"] = curta
        saida[f"{canal}_media_longa"] = longa
        saida[f"{canal}_desvio"] = x.rolling(JANELA_MEDIA, min_periods=2).std().fillna(0.0)
        saida[f"{canal}_maximo"] = x.rolling(JANELA_MEDIA, min_periods=1).max()
        saida[f"{canal}_tendencia_h"] = _inclinacao(x, JANELA_MEDIA) * AMOSTRAS_POR_HORA
        # a mesma inclinacao em 12 h: e a VELOCIDADE do desgaste, que e o que
        # diferencia "vai falhar em 10 h" de "vai falhar em 3 dias" no mesmo
        # nivel de vibracao
        saida[f"{canal}_tendencia_longa_h"] = _inclinacao(x, JANELA_LONGA) * AMOSTRAS_POR_HORA
        saida[f"{canal}_delta"] = curta - longa
        # quanto o "agora" se afastou de como ESTA maquina era quando nova:
        # separa a que sempre vibrou 2,3 da que subiu para 2,3
        saida[f"{canal}_vs_referencia"] = curta - _referencia(x)
    return pd.DataFrame(saida, index=leituras.index)[FEATURES]


def montar_janela_ao_vivo(cabeca: list[dict], cauda: list[dict]) -> pd.DataFrame:
    """Junta o que a inferencia guarda de um exaustor numa tabela so.

    cabeca -- as primeiras REFERENCIA leituras desde a partida/manutencao
    cauda  -- as ultimas JANELA_LONGA leituras

    Na ULTIMA linha desta tabela, calcular_features da exatamente o que daria
    se recebesse a historia inteira: todas as janelas moveis cabem na cauda,
    e a referencia sai da cabeca. As linhas do meio nao sao usadas.
    """
    return pd.DataFrame(cabeca + cauda, columns=list(CANAIS))
