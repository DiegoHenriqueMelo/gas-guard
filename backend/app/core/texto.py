import re
import unicodedata


def slug(texto: str, tamanho: int = 40) -> str:
    """"Cozinha do Restaurante" -> "cozinha-do-restaurante"."""
    sem_acento = (
        unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    )
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return limpo[:tamanho].strip("-") or "ambiente"
