"""Os servicos de fundo. Cada modulo aqui e um container no docker-compose:

    python -m app.servicos.gateway     MQTT <-> RabbitMQ
    python -m app.servicos.gravador    RabbitMQ -> InfluxDB
    python -m app.servicos.regras      regras de negocio e alertas
    python -m app.servicos.inferencia  modelos de IA sobre a telemetria
    python -m app.servicos.lab         geracao de dados e treino

Todos usam a mesma imagem do backend; muda so o comando.
"""
