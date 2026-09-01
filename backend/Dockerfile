FROM python:3.13-slim

# Nao gera .pyc e nao bufferiza o stdout: sem isto os print() do callback
# MQTT so aparecem no `docker logs` quando o buffer enche.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# requirements primeiro, sozinho: a camada de dependencias so e reconstruida
# quando o arquivo muda, nao a cada alteracao de codigo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

# Migra antes de servir: num `docker compose up` do zero o Postgres sobe
# vazio e as tabelas precisam existir antes do primeiro request.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
