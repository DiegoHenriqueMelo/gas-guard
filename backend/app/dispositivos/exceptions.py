class CodigoJaCadastrado(Exception):
    pass


class AmbienteNaoEncontrado(Exception):
    pass


class DispositivoNaoEncontrado(Exception):
    pass


class NomeJaCadastrado(Exception):
    pass


class ComandoInvalido(Exception):
    def __init__(self, motivo: str):
        self.motivo = motivo
