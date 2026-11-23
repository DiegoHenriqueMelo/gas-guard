"""O que cada tipo de dispositivo e, mede e aceita como comando.

Serve de padrao no cadastro (quem cria um sensor de gas nao precisa saber
que o campo e "ppm") e de lista fechada para os comandos: a API so publica
uma acao que o tipo do dispositivo de fato aceita.
"""

TIPOS = {
    # sensores
    "gas": {"categoria": "sensor", "campo": "ppm", "unidade": "ppm"},
    "temperatura": {"categoria": "sensor", "campo": "temperatura", "unidade": "°C"},
    "umidade": {"categoria": "sensor", "campo": "umidade", "unidade": "%"},
    "luminosidade": {"categoria": "sensor", "campo": "lux", "unidade": "lx"},
    "vazao": {"categoria": "sensor", "campo": "vazao", "unidade": "m³/h"},
    # atuadores
    "valvula": {"categoria": "atuador", "campo": None, "unidade": None},
    "sirene": {"categoria": "atuador", "campo": None, "unidade": None},
    # equipamento monitorado (tambem atuador: liga e desliga)
    "exaustor": {"categoria": "equipamento", "campo": "vibracao", "unidade": "mm/s"},
}

CATEGORIAS = ("sensor", "atuador", "equipamento")

ACOES_POR_TIPO = {
    "exaustor": ("ligar", "desligar"),
    "valvula": ("abrir", "fechar"),
    "sirene": ("ligar", "desligar"),
}

# Estado que cada acao deixa no atuador. A regra usa para nao mandar
# "fechar" para uma valvula que ja esta fechada.
ESTADO_DEPOIS_DA_ACAO = {
    "ligar": "ligado",
    "desligar": "desligado",
    "abrir": "aberta",
    "fechar": "fechada",
}
