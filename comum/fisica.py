"""Modelo fisico do gas-guard: o ambiente da cozinha e o exaustor da coifa.

Este arquivo e usado em DOIS lugares, de proposito:

- pelo simulador (simulador/), que gera a telemetria ao vivo, um instante
  por vez;
- pelo gerador do Laboratorio de Dados (backend/app/lab/), que gera meses
  de operacao de uma vez so, em vetores do numpy.

Se cada um tivesse a sua propria formula, o modelo treinado com os dados do
laboratorio veria, ao vivo, um exaustor que se comporta diferente daquele
que ele aprendeu. Por isso as funcoes aceitam numeros soltos OU arrays do
numpy: o laboratorio passa vetores com milhares de instantes, o simulador
passa um instante so. As operacoes do numpy funcionam igual nos dois casos.

O docker-compose copia esta pasta para dentro das duas imagens
(additional_contexts), entao existe um unico arquivo de verdade.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Tempo do equipamento
# ---------------------------------------------------------------------------

# Cada amostra do exaustor representa 5 minutos de operacao. No laboratorio
# isso e literal (uma linha a cada 5 min simulados). Ao vivo o simulador
# publica a cada 2 s, e cada publicacao vale 5 min de desgaste: o tempo do
# equipamento corre acelerado, senao uma falha levaria dias para aparecer na
# apresentacao. As janelas de features contam AMOSTRAS, entao o modelo ve a
# mesma coisa nos dois casos.
AMOSTRA_MINUTOS = 5
AMOSTRAS_POR_HORA = 60 // AMOSTRA_MINUTOS  # 12
AMOSTRAS_POR_DIA = 24 * AMOSTRAS_POR_HORA  # 288

# Teto do rotulo de vida util. Uma maquina saudavel nao tem "tempo ate a
# falha" conhecido; na pratica se usa um teto (RUL linear por partes). O
# teto acompanha a duracao maxima do desgaste no Laboratorio (4 dias): antes
# disso os sensores ainda nao mostram nada, e pedir ao modelo um numero
# exato so ensinaria ruido. Para a manutencao, "mais de 4 dias" basta.
RUL_MAXIMO_HORAS = 96.0

# ---------------------------------------------------------------------------
# Modos de falha
# ---------------------------------------------------------------------------

# Falhas do EQUIPAMENTO: o exaustor degrada de verdade e acaba parando.
MODOS_EQUIPAMENTO = (
    "rolamento",          # desgaste de rolamento: vibracao dispara
    "desbalanceamento",   # gordura acumulada nas pas: vibracao sobe linear
    "entupimento",        # filtro de gordura entupido: menos ar, menos corrente
    "superaquecimento",   # isolamento/ventilacao do motor: temperatura dispara
)

# Falhas do SENSOR: o exaustor esta saudavel, quem mente e a medicao. Servem
# para o modelo aprender que nem toda leitura estranha e desgaste.
MODOS_SENSOR = (
    "deriva_sensor",      # um canal vai somando um erro aos poucos
    "travamento_sensor",  # um canal congela num valor
)

MODOS_FALHA = MODOS_EQUIPAMENTO + MODOS_SENSOR

# Os quatro canais medidos no exaustor, sempre nesta ordem.
CANAIS = ("vibracao", "corrente", "temperatura", "rpm")

# Erro maximo acumulado por um sensor com deriva, ao fim do periodo de defeito.
DERIVA_MAXIMA = {"vibracao": 2.0, "corrente": 1.0, "temperatura": 12.0, "rpm": -150.0}

UNIDADES = {
    "vibracao": "mm/s",
    "corrente": "A",
    "temperatura": "°C",
    "rpm": "rpm",
}

# ---------------------------------------------------------------------------
# Ambiente da cozinha
# ---------------------------------------------------------------------------


def servico(hora):
    """Intensidade do expediente da cozinha, de 0 a 1.

    Dois picos suaves: almoco (por volta das 12h30) e jantar (20h). E isso
    que cria o ciclo diario nos dados: fogao aceso esquenta a cozinha e faz a
    coifa trabalhar mais.
    """
    h = np.asarray(hora, dtype=float) % 24
    almoco = np.exp(-0.5 * ((h - 12.5) / 1.3) ** 2)
    jantar = np.exp(-0.5 * ((h - 20.0) / 1.6) ** 2)
    return np.clip(almoco + jantar, 0.0, 1.0)


def _estacao(dia_do_ano):
    """+1 no auge do verao (meados de janeiro, hemisferio sul), -1 no inverno."""
    return np.cos(2 * np.pi * (np.asarray(dia_do_ano, dtype=float) - 15) / 365)


def temperatura_ambiente(hora, dia_do_ano):
    """Temperatura da cozinha em °C: ciclo do dia, estacao e calor do fogao."""
    h = np.asarray(hora, dtype=float) % 24
    diario = 4.0 * np.sin(2 * np.pi * (h - 9) / 24)  # maxima perto das 15h
    return 23.0 + diario + 4.0 * _estacao(dia_do_ano) + 6.0 * servico(h)


def umidade_ambiente(hora, dia_do_ano):
    """Umidade relativa em %: cai quando esquenta, sobe com o vapor das panelas."""
    h = np.asarray(hora, dtype=float) % 24
    valor = (
        62.0
        - 12.0 * np.sin(2 * np.pi * (h - 9) / 24)
        + 4.0 * _estacao(dia_do_ano)
        + 10.0 * servico(h)
    )
    return np.clip(valor, 15.0, 98.0)


def luminosidade_externa(hora, dia_do_ano):
    """Luz na janela da cozinha, em lux. Dia mais longo no verao.

    O sensor fica na janela e sombreado, por isso a escala vai so ate
    ~1000 lx (luz direta do sol passaria de 50.000).
    """
    h = np.asarray(hora, dtype=float) % 24
    duracao = 12.0 + 1.5 * _estacao(dia_do_ano)
    nascer = 12.0 - duracao / 2
    fase = (h - nascer) / duracao
    sol = np.where((fase > 0) & (fase < 1), np.sin(np.pi * np.clip(fase, 0, 1)), 0.0)
    return 5.0 + 950.0 * sol**0.8


# ---------------------------------------------------------------------------
# Exaustor da coifa
# ---------------------------------------------------------------------------

# Motor de 1 cv, 4 polos, 60 Hz. Para a vibracao, a referencia e a ISO 10816
# (maquinas pequenas): ate 1,8 mm/s bom, ate 4,5 aceitavel, ate 11,2
# insatisfatorio, acima disso inaceitavel.
BASE_NOMINAL = {"vib0": 1.7, "corr0": 3.7, "dt0": 22.0, "rpm0": 1725.0}


def base_do_equipamento(rng):
    """Sorteia a "personalidade" de um exaustor.

    Duas maquinas novas nunca sao iguais: uma ja vibra um pouco mais, outra
    esquenta um pouco mais. Isso cria sobreposicao entre maquinas saudaveis
    e doentes, que e o que impede o modelo de acertar 100% "decorando" um
    valor fixo.
    """
    return {
        "vib0": float(rng.uniform(1.1, 2.3)),
        "corr0": float(rng.uniform(3.3, 4.1)),
        "dt0": float(rng.uniform(18.0, 27.0)),
        "rpm0": float(rng.uniform(1700.0, 1745.0)),
    }


def carga_exaustor(hora):
    """Fracao da carga do motor: a coifa puxa mais ar durante o expediente."""
    return 0.7 + 0.3 * servico(hora)


def nivel_degradacao(progresso, expoente=2.0):
    """Converte o progresso da degradacao (0 a 1) no nivel de dano (0 a 1).

    Com expoente > 1 o dano comeca lento e acelera no fim, como acontece com
    um rolamento: semanas de folga crescendo devagar e poucos dias de
    deterioracao rapida antes de travar.
    """
    return np.clip(np.asarray(progresso, dtype=float), 0.0, 1.0) ** expoente


def saude_real(nivel):
    """Indice de saude verdadeiro (0 a 100). E o ROTULO do treino.

    Nunca sai nas mensagens ao vivo: o simulador conhece esse numero, mas so
    publica o que um sensor de verdade mediria.
    """
    return 100.0 * (1.0 - np.clip(np.asarray(nivel, dtype=float), 0.0, 1.0))


def leituras_exaustor(base, carga, temp_ambiente, degradacao, rng, ruido=0.3):
    """O que os quatro sensores do exaustor marcariam.

    base          -- dict de base_do_equipamento()
    carga         -- fracao da carga (0.7 a 1.0), numero ou array
    temp_ambiente -- temperatura da cozinha em °C, numero ou array
    degradacao    -- dict modo -> nivel de dano (0 a 1); modo ausente = 0
    rng           -- numpy Generator (np.random.default_rng)
    ruido         -- 0 = sensores perfeitos, 1 = bem ruidosos

    Devolve dict canal -> valores, do mesmo formato da entrada.
    """
    carga = np.asarray(carga, dtype=float)
    formato = np.broadcast(carga, np.asarray(temp_ambiente)).shape

    def d(modo):
        return np.asarray(degradacao.get(modo, 0.0), dtype=float)

    rol, des, ent, sup = (
        d("rolamento"),
        d("desbalanceamento"),
        d("entupimento"),
        d("superaquecimento"),
    )

    # Cada modo de falha deixa uma assinatura diferente nos quatro canais.
    # O entupimento e o contraintuitivo: com o filtro de gordura fechado o
    # ventilador move MENOS ar, faz menos forca e a corrente CAI, enquanto o
    # rotor gira mais solto e o motor esquenta por falta de ar passando nele.
    vibracao = (
        base["vib0"] * (0.85 + 0.15 * carga)
        + 9.0 * rol**1.5
        + 6.0 * des
        + 1.0 * ent
        + 0.8 * sup
    )
    corrente = (
        base["corr0"] * (0.55 + 0.45 * carga)
        + 0.6 * rol
        + 0.4 * des
        - 1.1 * ent
        + 1.2 * sup
    )
    temperatura = (
        temp_ambiente
        + base["dt0"] * (0.6 + 0.4 * carga)
        + 22.0 * rol
        + 4.0 * des
        + 14.0 * ent
        + 45.0 * sup
    )
    rpm = base["rpm0"] - 18.0 * carga - 25.0 * rol - 8.0 * des + 30.0 * ent - 15.0 * sup

    escala = 0.15 + ruido
    vibracao = vibracao + rng.normal(0.0, 0.18 * escala, formato)
    corrente = corrente + rng.normal(0.0, 0.10 * escala, formato)
    temperatura = temperatura + rng.normal(0.0, 1.2 * escala, formato)
    rpm = rpm + rng.normal(0.0, 6.0 * escala, formato)

    return {
        "vibracao": np.maximum(vibracao, 0.05),
        "corrente": np.maximum(corrente, 0.0),
        "temperatura": temperatura,
        "rpm": rpm,
    }
