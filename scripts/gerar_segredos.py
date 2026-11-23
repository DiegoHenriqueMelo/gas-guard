"""Gera todos os segredos do gas-guard. Rode uma vez antes do primeiro `up`.

    python scripts/gerar_segredos.py
    (sem Python na maquina:)
    docker run --rm -v "${PWD}:/w" -w /w python:3.13-slim python scripts/gerar_segredos.py

Cria (todos ignorados pelo Git):
  .env                              senhas, tokens e o segredo do JWT
  secrets/rabbitmq/definitions.json usuarios do RabbitMQ (com hash) + topologia
  secrets/usuarios-demo.txt         login e senha dos 3 usuarios da demonstracao

Rodar de novo NAO troca o que ja existe: so completa o que falta. Isso
importa porque o PostgreSQL e o InfluxDB gravam a senha do administrador no
volume na primeira subida - trocar a senha no .env depois disso faz os
servicos nao conseguirem mais entrar. Para comecar do zero de verdade:

    docker compose down -v                  (apaga os volumes!)
    python scripts/gerar_segredos.py --refazer

Usa so a biblioteca padrao do Python. Grava com fim de linha LF mesmo no
Windows: o .env tambem e lido por shell e por containers Linux.
"""

import argparse
import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV = RAIZ / ".env"
PASTA_SEGREDOS = RAIZ / "secrets"
TOPOLOGIA = RAIZ / "infra" / "rabbitmq" / "topologia.json"


def aleatoria(tamanho: int = 24) -> str:
    # token_urlsafe: letras, numeros, - e _. Nada que quebre URL, .env ou o
    # split do entrypoint do Mosquitto.
    return secrets.token_urlsafe(tamanho)


# (chave, valor padrao ou funcao geradora, comentario do grupo)
GRUPOS = [
    ("PostgreSQL", [
        ("POSTGRES_USER", "gasguard"),
        ("POSTGRES_DB", "gasguard"),
        ("POSTGRES_PASSWORD", aleatoria),
    ]),
    ("InfluxDB (o init so roda com o volume vazio)", [
        ("DOCKER_INFLUXDB_INIT_USERNAME", "gasguard"),
        ("DOCKER_INFLUXDB_INIT_PASSWORD", aleatoria),
        ("DOCKER_INFLUXDB_INIT_ORG", "gasguard"),
        ("DOCKER_INFLUXDB_INIT_BUCKET", "sensores"),
        ("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN", lambda: aleatoria(48)),
    ]),
    ("API", [
        ("JWT_SEGREDO", lambda: aleatoria(48)),
    ]),
    ("RabbitMQ: um usuario por servico", [
        ("RABBIT_SENHA_API", aleatoria),
        ("RABBIT_SENHA_GATEWAY", aleatoria),
        ("RABBIT_SENHA_GRAVADOR", aleatoria),
        ("RABBIT_SENHA_REGRAS", aleatoria),
        ("RABBIT_SENHA_INFERENCIA", aleatoria),
        ("RABBIT_SENHA_LAB", aleatoria),
        ("RABBIT_SENHA_ADMIN", aleatoria),  # interface http://127.0.0.1:15672
    ]),
    ("Mosquitto: sem anonimo, um usuario por papel", [
        ("MQTT_SIMULADOR_SENHA", aleatoria),
        ("MQTT_GATEWAY_SENHA", aleatoria),
        ("MQTT_OBSERVADOR_SENHA", aleatoria),
    ]),
    ("Usuarios de demonstracao (login no painel)", [
        ("DEMO_SENHA_ADMINISTRADOR", lambda: aleatoria(9)),
        ("DEMO_SENHA_OPERADOR", lambda: aleatoria(9)),
        ("DEMO_SENHA_VISUALIZADOR", lambda: aleatoria(9)),
    ]),
    ("LLM local", [
        ("OLLAMA_MODELO", "llama3.2:3b"),
    ]),
]

USUARIO_RABBIT = {
    "gg_api": "RABBIT_SENHA_API",
    "gg_gateway": "RABBIT_SENHA_GATEWAY",
    "gg_gravador": "RABBIT_SENHA_GRAVADOR",
    "gg_regras": "RABBIT_SENHA_REGRAS",
    "gg_inferencia": "RABBIT_SENHA_INFERENCIA",
    "gg_lab": "RABBIT_SENHA_LAB",
    "gg_admin": "RABBIT_SENHA_ADMIN",
}


def ler_env(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not caminho.exists():
        return valores
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip()
    return valores


def hash_rabbitmq(senha: str) -> str:
    """O formato que o RabbitMQ aceita no definitions.json
    (rabbit_password_hashing_sha256): base64(sal + sha256(sal + senha)),
    com 4 bytes de sal aleatorio. Assim a senha em si nunca vai no arquivo."""
    sal = os.urandom(4)
    return base64.b64encode(sal + hashlib.sha256(sal + senha.encode()).digest()).decode()


def gravar_env(valores: dict[str, str], conhecidas: set[str]) -> None:
    linhas = [
        "# Gerado por scripts/gerar_segredos.py. NAO versionar (esta no .gitignore).",
        "# Rodar o script de novo so completa o que falta.",
        "",
    ]
    for titulo, itens in GRUPOS:
        linhas.append(f"# --- {titulo} ---")
        linhas += [f"{chave}={valores[chave]}" for chave, _ in itens]
        linhas.append("")

    extras = [chave for chave in valores if chave not in conhecidas]
    if extras:
        linhas.append("# --- outras variaveis que ja estavam neste arquivo (mantidas) ---")
        linhas += [f"{chave}={valores[chave]}" for chave in extras]
        linhas.append("")
    ENV.write_text("\n".join(linhas), encoding="utf-8", newline="\n")


def gravar_definicoes(valores: dict[str, str]) -> Path:
    topologia = json.loads(TOPOLOGIA.read_text(encoding="utf-8"))
    servicos = topologia.pop("servicos")
    for chave in [k for k in topologia if k.startswith("_")]:
        topologia.pop(chave)

    usuarios, permissoes = [], []
    for usuario, regra in servicos.items():
        usuarios.append({
            "name": usuario,
            "password_hash": hash_rabbitmq(valores[USUARIO_RABBIT[usuario]]),
            "hashing_algorithm": "rabbit_password_hashing_sha256",
            "tags": regra["tags"],
        })
        permissoes.append({
            "user": usuario,
            "vhost": "gasguard",
            "configure": regra["configure"],
            "write": regra["write"],
            "read": regra["read"],
        })

    definicoes = {"users": usuarios, "permissions": permissoes, **topologia}
    destino = PASTA_SEGREDOS / "rabbitmq" / "definitions.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(definicoes, indent=2), encoding="utf-8", newline="\n")
    return destino


def gravar_usuarios_demo(valores: dict[str, str]) -> Path:
    destino = PASTA_SEGREDOS / "usuarios-demo.txt"
    destino.write_text(
        "Usuarios de demonstracao do gas-guard (NAO versionar)\n\n"
        f"administrador  {valores['DEMO_SENHA_ADMINISTRADOR']}   gera dados, treina, edita cadastros, ve auditoria\n"
        f"operador       {valores['DEMO_SENHA_OPERADOR']}   comanda atuadores e o simulador\n"
        f"visualizador   {valores['DEMO_SENHA_VISUALIZADOR']}   so ve\n\n"
        f"RabbitMQ (http://127.0.0.1:15672): gg_admin / {valores['RABBIT_SENHA_ADMIN']}\n"
        f"InfluxDB (http://127.0.0.1:8086): {valores['DOCKER_INFLUXDB_INIT_USERNAME']} / "
        f"{valores['DOCKER_INFLUXDB_INIT_PASSWORD']}\n"
        f"Adminer  (http://127.0.0.1:8081): servidor postgres, usuario {valores['POSTGRES_USER']}, "
        f"senha {valores['POSTGRES_PASSWORD']}, banco {valores['POSTGRES_DB']}\n"
        f"MQTT observador (127.0.0.1:1883): gg_observador / {valores['MQTT_OBSERVADOR_SENHA']}\n",
        encoding="utf-8",
        newline="\n",
    )
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refazer", action="store_true",
                        help="gera TUDO de novo (so depois de `docker compose down -v`)")
    args = parser.parse_args()

    valores = {} if args.refazer else ler_env(ENV)
    conhecidas: set[str] = set()
    novas = []
    for _, itens in GRUPOS:
        for chave, padrao in itens:
            conhecidas.add(chave)
            if not valores.get(chave):
                valores[chave] = padrao() if callable(padrao) else padrao
                novas.append(chave)

    gravar_env(valores, conhecidas)
    definicoes = gravar_definicoes(valores)
    demo = gravar_usuarios_demo(valores)

    print(f".env: {len(novas)} variaveis novas" + (f" ({', '.join(novas)})" if novas else ""))
    print(f"{definicoes.relative_to(RAIZ)}: usuarios do RabbitMQ e topologia")
    print(f"{demo.relative_to(RAIZ)}: logins da demonstracao")
    print("\nPronto. Agora: docker compose up -d --build")


if __name__ == "__main__":
    main()
