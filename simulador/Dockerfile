FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt \
 && useradd --system --uid 10001 --home-dir /app simulador

# mesmo modelo fisico que o Laboratorio usa para gerar os dados de treino
COPY --from=comum . ./comum
COPY simulador.py .

USER simulador
CMD ["python", "simulador.py"]
