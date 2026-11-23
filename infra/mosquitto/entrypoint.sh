#!/bin/sh
# Gera o arquivo de senhas do Mosquitto a partir das variaveis de ambiente e
# sobe o broker. Roda a cada subida do container, entao trocar uma senha no
# .env e reiniciar o servico basta.
set -e

PASTA=/mosquitto/auth
mkdir -p "$PASTA"
: > "$PASTA/passwd"

for par in \
  "gg_simulador:$MQTT_SIMULADOR_SENHA" \
  "gg_gateway:$MQTT_GATEWAY_SENHA" \
  "gg_observador:$MQTT_OBSERVADOR_SENHA"
do
  usuario="${par%%:*}"
  senha="${par#*:}"
  if [ -z "$senha" ]; then
    echo "senha de $usuario nao definida (rode scripts/gerar_segredos.py)" >&2
    exit 1
  fi
  # -b: senha na linha de comando; o arquivo guarda so o hash (PBKDF2)
  mosquitto_passwd -b "$PASTA/passwd" "$usuario" "$senha"
done

# O Mosquitto avisa (e vai recusar no futuro) arquivo de senha/ACL que
# qualquer um pode ler. A copia aqui dentro fica so com o dono.
cp /mosquitto/config/acl "$PASTA/acl"
chown -R mosquitto:mosquitto "$PASTA"
chmod 0700 "$PASTA"
chmod 0600 "$PASTA/passwd" "$PASTA/acl"

exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
