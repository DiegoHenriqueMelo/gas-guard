"""Dados iniciais: `python -m app.seed` (o servico `migrador` roda sozinho).

Idempotente: pode rodar a cada subida. So cria o que falta e nunca apaga
nem sobrescreve o que alguem editou pelas telas - com uma excecao: a senha
dos usuarios de demonstracao acompanha o .env (gerado por
scripts/gerar_segredos.py), para trocar a senha bastar gerar de novo.
"""

import logging
import os

from sqlalchemy import select

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.ambientes.models import Ambiente
from app.auth.models import Usuario
from app.auth.seguranca import conferir_senha, hash_senha
from app.core.database import SessionLocal
from app.dispositivos.catalogo import ACOES_POR_TIPO, TIPOS
from app.dispositivos.models import Dispositivo
from app.ia.models import Configuracao
from app.regras.models import Regra

logging.basicConfig(level=logging.INFO, format="%(asctime)s [seed] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("seed")

ZONA = "cozinha"

USUARIOS = [
    # (usuario, nome, papel, variavel de ambiente com a senha)
    ("administrador", "Administração", "administrador", "DEMO_SENHA_ADMINISTRADOR"),
    ("operador", "Operação da cozinha", "operador", "DEMO_SENHA_OPERADOR"),
    ("visualizador", "Visitante", "visualizador", "DEMO_SENHA_VISUALIZADOR"),
]

# codigo, nome, tipo, faixa (normal_min, normal_max, critico_min, critico_max)
DISPOSITIVOS = [
    ("GAS-01", "Detector de GLP", "gas", (None, 1000, None, 2000)),
    ("TEMP-01", "Temperatura da cozinha", "temperatura", (15, 35, 8, 45)),
    ("UMID-01", "Umidade da cozinha", "umidade", (30, 80, 15, 92)),
    ("LUZ-01", "Luminosidade na janela", "luminosidade", (None, None, None, None)),
    ("VAZAO-01", "Vazão de gás", "vazao", (None, 2.5, None, 4.0)),
    # vibracao pela ISO 10816 (maquina pequena): ate 4,5 mm/s aceitavel,
    # acima de 11,2 inaceitavel
    ("EXAUSTOR-01", "Exaustor da coifa", "exaustor", (None, 4.5, None, 11.2)),
    ("VALVULA-01", "Válvula solenoide de gás", "valvula", (None, None, None, None)),
    ("SIRENE-01", "Sirene de alarme", "sirene", (None, None, None, None)),
]

# nome, origem, campo, operador, limite, alvo, acao
REGRAS = [
    ("Gás em atenção liga o exaustor", "GAS-01", "ppm", ">=", 1000, "EXAUSTOR-01", "ligar"),
    ("Gás crítico fecha a válvula", "GAS-01", "ppm", ">=", 2000, "VALVULA-01", "fechar"),
    ("Gás crítico liga a sirene", "GAS-01", "ppm", ">=", 2000, "SIRENE-01", "ligar"),
    ("Gás normalizado desliga a sirene", "GAS-01", "ppm", "<", 1000, "SIRENE-01", "desligar"),
    ("Cozinha muito quente liga o exaustor", "TEMP-01", "temperatura", ">", 38, "EXAUSTOR-01", "ligar"),
]

CONFIGURACOES = [
    ("ia_saude_atencao", 60, "Saúde prevista abaixo disto abre alerta de atenção"),
    ("ia_saude_critico", 30, "Saúde prevista abaixo disto abre alerta crítico"),
    ("ia_rul_atencao_h", 48, "Vida útil restante (h) abaixo disto abre alerta de atenção"),
    ("ia_rul_critico_h", 12, "Vida útil restante (h) abaixo disto abre alerta crítico"),
    ("ia_histerese_abrir", 3, "Previsões seguidas ruins para abrir um alerta da IA"),
    ("ia_histerese_fechar", 10, "Previsões seguidas boas para fechar um alerta da IA"),
]


def usuarios(db) -> None:
    for usuario, nome, papel, variavel in USUARIOS:
        senha = os.getenv(variavel)
        if not senha:
            log.warning("%s nao definida: usuario %s nao criado", variavel, usuario)
            continue
        conta = db.scalars(select(Usuario).where(Usuario.usuario == usuario)).first()
        if conta is None:
            db.add(Usuario(usuario=usuario, nome=nome, papel=papel, senha_hash=hash_senha(senha)))
            log.info("usuario %s (%s) criado", usuario, papel)
        elif not conferir_senha(senha, conta.senha_hash):
            conta.senha_hash = hash_senha(senha)
            log.info("senha de %s atualizada a partir do .env", usuario)


def ambiente(db) -> Ambiente:
    cozinha = db.scalars(select(Ambiente).where(Ambiente.zona == ZONA)).first()
    if cozinha is None:
        cozinha = Ambiente(nome="Cozinha do restaurante", zona=ZONA,
                           descricao="Cozinha comercial com central de GLP e coifa")
        db.add(cozinha)
        db.flush()
        log.info("ambiente %s criado", cozinha.nome)
    return cozinha


def dispositivos(db, cozinha: Ambiente) -> None:
    for codigo, nome, tipo, (nmin, nmax, cmin, cmax) in DISPOSITIVOS:
        if db.scalars(select(Dispositivo).where(Dispositivo.codigo == codigo)).first():
            continue
        padrao = TIPOS[tipo]
        db.add(Dispositivo(
            codigo=codigo, nome=nome, tipo=tipo, ambiente_id=cozinha.id,
            categoria=padrao["categoria"], campo_principal=padrao["campo"],
            unidade=padrao["unidade"], controlavel=tipo in ACOES_POR_TIPO,
            normal_min=nmin, normal_max=nmax, critico_min=cmin, critico_max=cmax,
        ))
        log.info("dispositivo %s criado", codigo)


def regras(db) -> None:
    if db.scalars(select(Regra)).first() is not None:
        return  # ja existem regras: respeita o que foi editado
    for nome, origem, campo, operador, limite, alvo, acao in REGRAS:
        db.add(Regra(nome=nome, dispositivo_codigo=origem, campo=campo, operador=operador,
                     limite=limite, alvo_codigo=alvo, acao=acao))
    log.info("%d regras padrao criadas", len(REGRAS))


def configuracoes(db) -> None:
    for chave, valor, descricao in CONFIGURACOES:
        if db.get(Configuracao, chave) is None:
            db.add(Configuracao(chave=chave, valor=valor, descricao=descricao))


def main() -> None:
    with SessionLocal() as db:
        usuarios(db)
        cozinha = ambiente(db)
        dispositivos(db, cozinha)
        db.flush()
        regras(db)
        configuracoes(db)
        db.commit()
    log.info("seed concluido")


if __name__ == "__main__":
    main()
