"""segundo bimestre: usuarios, auditoria, regras, alertas, jobs, modelos

Revision ID: 7c2e9a41b5d0
Revises: 21bda3d0d359
Create Date: 2026-10-20 10:00:00.000000

Escrita a mao, nao pelo autogenerate, por causa das colunas novas em tabelas
que JA TEM dados do 1o bimestre: `ambientes.zona` precisa ser preenchida
antes de virar NOT NULL e UNIQUE, e as colunas novas de `dispositivos`
precisam de valor padrao para as linhas que ja existem.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7c2e9a41b5d0"
down_revision: Union[str, Sequence[str], None] = "21bda3d0d359"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- ambientes.zona ----------
    op.add_column("ambientes", sa.Column("zona", sa.String(length=40), nullable=True))
    # Ambientes antigos ganham uma zona derivada do id ("amb1", "amb2"...);
    # da para trocar depois pela tela de Ambientes.
    op.execute("UPDATE ambientes SET zona = 'amb' || id WHERE zona IS NULL")
    op.alter_column("ambientes", "zona", nullable=False)
    op.create_unique_constraint("uq_ambientes_zona", "ambientes", ["zona"])

    # ---------- dispositivos: categoria, tipo, faixa ----------
    # O unico dispositivo do 1o bimestre era um sensor de gas, entao os
    # padroes descrevem exatamente ele.
    novas = [
        sa.Column("categoria", sa.String(20), nullable=False, server_default="sensor"),
        sa.Column("tipo", sa.String(30), nullable=False, server_default="gas"),
        sa.Column("campo_principal", sa.String(30), nullable=True, server_default="ppm"),
        sa.Column("unidade", sa.String(15), nullable=True, server_default="ppm"),
        sa.Column("controlavel", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("normal_min", sa.Float(), nullable=True),
        sa.Column("normal_max", sa.Float(), nullable=True, server_default="1000"),
        sa.Column("critico_min", sa.Float(), nullable=True),
        sa.Column("critico_max", sa.Float(), nullable=True, server_default="2000"),
    ]
    for coluna in novas:
        op.add_column("dispositivos", coluna)
    # o padrao so servia para as linhas antigas; as novas vem do cadastro
    for nome in ("campo_principal", "unidade", "normal_max", "critico_max"):
        op.alter_column("dispositivos", nome, server_default=None)

    # ---------- usuarios ----------
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario", sa.String(50), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("senha_hash", sa.String(100), nullable=False),
        sa.Column("papel", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tentativas_falhas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "papel IN ('visualizador', 'operador', 'administrador')", name="ck_usuarios_papel"
        ),
    )

    # ---------- auditoria ----------
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "instante", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("usuario", sa.String(50), nullable=True),
        sa.Column("papel", sa.String(20), nullable=True),
        sa.Column("acao", sa.String(60), nullable=False),
        sa.Column("detalhe", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_auditoria_instante", "auditoria", ["instante"])
    op.create_index("ix_auditoria_usuario", "auditoria", ["usuario"])
    op.create_index("ix_auditoria_acao", "auditoria", ["acao"])

    # ---------- regras ----------
    op.create_table(
        "regras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dispositivo_codigo", sa.String(50), nullable=False),
        sa.Column("campo", sa.String(30), nullable=False),
        sa.Column("operador", sa.String(2), nullable=False),
        sa.Column("limite", sa.Float(), nullable=False),
        sa.Column("alvo_codigo", sa.String(50), nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["dispositivo_codigo"], ["dispositivos.codigo"], onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(["alvo_codigo"], ["dispositivos.codigo"], onupdate="CASCADE"),
        sa.CheckConstraint("operador IN ('>', '>=', '<', '<=')", name="ck_regras_operador"),
    )

    # ---------- alertas ----------
    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispositivo_codigo", sa.String(50), nullable=False),
        sa.Column("chave", sa.String(30), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("severidade", sa.String(10), nullable=False),
        sa.Column("mensagem", sa.String(255), nullable=False),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "aberto_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fechado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alertas_dispositivo_codigo", "alertas", ["dispositivo_codigo"])
    op.create_index("ix_alertas_ativo", "alertas", ["ativo"])
    # Garante no banco a regra "um alerta ativo por (dispositivo, chave)".
    op.create_index(
        "uq_alertas_ativo_por_chave",
        "alertas",
        ["dispositivo_codigo", "chave"],
        unique=True,
        postgresql_where=sa.text("ativo"),
    )

    # ---------- jobs ----------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="na_fila"),
        sa.Column("parametros", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("progresso", sa.Float(), nullable=False, server_default="0"),
        sa.Column("etapa", sa.String(120), nullable=True),
        sa.Column("resultado", postgresql.JSONB(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("usuario", sa.String(50), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])

    # ---------- modelos ----------
    op.create_table(
        "modelos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("versao", sa.String(20), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("dataset_job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("caminho", sa.String(255), nullable=False),
        sa.Column("metricas", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("venceu_base", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_modelos_ativo", "modelos", ["ativo"])

    # ---------- configuracoes ----------
    op.create_table(
        "configuracoes",
        sa.Column("chave", sa.String(50), primary_key=True),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("configuracoes")
    op.drop_index("ix_modelos_ativo", table_name="modelos")
    op.drop_table("modelos")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("uq_alertas_ativo_por_chave", table_name="alertas")
    op.drop_index("ix_alertas_ativo", table_name="alertas")
    op.drop_index("ix_alertas_dispositivo_codigo", table_name="alertas")
    op.drop_table("alertas")
    op.drop_table("regras")
    op.drop_index("ix_auditoria_acao", table_name="auditoria")
    op.drop_index("ix_auditoria_usuario", table_name="auditoria")
    op.drop_index("ix_auditoria_instante", table_name="auditoria")
    op.drop_table("auditoria")
    op.drop_table("usuarios")
    for nome in (
        "critico_max",
        "critico_min",
        "normal_max",
        "normal_min",
        "controlavel",
        "unidade",
        "campo_principal",
        "tipo",
        "categoria",
    ):
        op.drop_column("dispositivos", nome)
    op.drop_constraint("uq_ambientes_zona", "ambientes", type_="unique")
    op.drop_column("ambientes", "zona")
