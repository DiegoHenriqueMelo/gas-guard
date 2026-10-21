"""Qual modelo esta em uso, e a troca dele sem reiniciar o servico.

O servico de inferencia pergunta ao Postgres, a cada poucos segundos, qual
versao esta com ativo = True. Se mudou (treino novo, ou alguem ativou outra
versao na pagina de Treinamento), carrega o arquivo novo e troca a
referencia. A troca e uma atribuicao so: a previsao seguinte ja usa o
modelo novo, e nenhuma mensagem fica sem resposta durante a troca.
"""

import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.database import SessionLocal
from app.ia.features import FEATURES
from app.ia.models import Modelo

log = logging.getLogger(__name__)


class RegistroDeModelos:
    def __init__(self, intervalo: float = 5.0):
        self.intervalo = intervalo
        self.versao: str | None = None
        self._pacote: dict | None = None
        self._conferido_em = 0.0
        self._recusada: str | None = None

    def _ativo_no_banco(self) -> tuple[str, str] | None:
        with SessionLocal() as db:
            modelo = db.scalars(select(Modelo).where(Modelo.ativo.is_(True))).first()
            return (modelo.versao, modelo.caminho) if modelo else None

    def atualizar(self) -> None:
        """Chamado de uma thread (faz IO). Barato quando nada mudou."""
        if time.monotonic() - self._conferido_em < self.intervalo:
            return
        self._conferido_em = time.monotonic()

        ativo = self._ativo_no_banco()
        if ativo is None:
            if self.versao is not None:
                log.info("nenhum modelo ativo no banco; parando as previsoes")
            self.versao, self._pacote = None, None
            return

        versao, caminho = ativo
        if versao in (self.versao, self._recusada):
            return

        pacote = joblib.load(Path(caminho))
        if pacote.get("features") != FEATURES:
            # modelo treinado com outra lista de features: usar daria
            # previsoes sem sentido, entao recusamos
            log.error("modelo %s tem features diferentes das atuais; treine de novo", versao)
            self._recusada = versao
            self.versao, self._pacote = None, None
            return

        # a troca: daqui para frente, toda previsao usa o pacote novo
        self._pacote, self.versao = pacote, versao
        log.info("modelo %s carregado e em uso", versao)

    @property
    def pronto(self) -> bool:
        return self._pacote is not None

    def prever(self, linha: pd.DataFrame) -> dict[str, float]:
        """Recebe UMA linha de features e devolve {"saude": ..., "rul_horas": ...}."""
        pacote = self._pacote
        if pacote is None:
            raise RuntimeError("nenhum modelo carregado")
        saida = {}
        for alvo, modelo in pacote["modelos"].items():
            minimo, maximo = pacote["limites"][alvo]
            valor = float(modelo.predict(linha[FEATURES])[0])
            saida[alvo] = float(np.clip(valor, minimo, maximo))
        return saida
