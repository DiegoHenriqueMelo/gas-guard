"""Histerese: o alerta so muda depois de varias avaliacoes seguidas concordando.

Sem isso, um valor oscilando em cima do limite (59, 61, 58, 62...) abriria e
fecharia o alerta a cada leitura, e o painel ficaria piscando. Aqui:

  - para ABRIR (ou piorar a severidade): n_abrir avaliacoes seguidas ruins;
  - para FECHAR (ou melhorar):           n_fechar avaliacoes seguidas boas.

Fechar exige mais que abrir de proposito: e melhor avisar cedo e so dar o
problema por resolvido quando ele estiver resolvido mesmo.
"""

ORDEM = {None: 0, "atencao": 1, "critico": 2}


class Histerese:
    def __init__(self, n_abrir: int = 3, n_fechar: int = 10):
        self.n_abrir = n_abrir
        self.n_fechar = n_fechar
        self.ativo: str | None = None  # severidade do alerta aberto, ou None
        self._candidato: str | None = None
        self._contagem = 0

    def avaliar(self, severidade: str | None) -> tuple[str, str | None] | None:
        """Recebe a severidade desta avaliacao (None = tudo bem).

        Devolve ("abrir", severidade), ("fechar", None) ou None quando nada
        muda. "abrir" tambem serve para mudar a severidade de um alerta que
        ja estava aberto.
        """
        if severidade == self.ativo:
            self._candidato, self._contagem = None, 0
            return None

        if severidade == self._candidato:
            self._contagem += 1
        else:
            self._candidato, self._contagem = severidade, 1

        melhorando = ORDEM[severidade] < ORDEM[self.ativo]
        necessario = self.n_fechar if melhorando else self.n_abrir
        if self._contagem < necessario:
            return None

        self.ativo = severidade
        self._candidato, self._contagem = None, 0
        return ("fechar", None) if severidade is None else ("abrir", severidade)
