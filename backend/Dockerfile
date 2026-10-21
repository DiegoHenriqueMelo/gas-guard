FROM python:3.13-slim

# Nao gera .pyc e nao bufferiza o stdout: sem isto os logs so aparecem no
# `docker compose logs` quando o buffer enche.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# requirements primeiro, sozinho: a camada de dependencias so e reconstruida
# quando o arquivo muda, nao a cada alteracao de codigo.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Usuario sem privilegio. Se alguem explorar uma falha da API, cai num
# usuario que nao pode instalar nada nem mexer no sistema do container.
# /dados e /modelos ja nascem dele: o volume do Docker herda o dono da
# pasta da imagem na primeira montagem.
RUN useradd --system --uid 10001 --home-dir /app gasguard \
 && mkdir -p /dados /modelos \
 && chown gasguard:gasguard /dados /modelos

# O modelo fisico compartilhado com o simulador (pasta comum/ na raiz do
# repo). Chega pelo additional_contexts do docker-compose.yml.
COPY --from=comum . ./comum
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

USER gasguard
EXPOSE 8000

# A mesma imagem roda a API e os servicos de fundo; o docker-compose troca
# o comando (python -m app.servicos.gateway, etc.). Este e o da API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
