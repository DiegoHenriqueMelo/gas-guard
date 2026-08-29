# Arquitetura

## Fluxo obrigatorio da 1a etapa

```
Sensor  ->  MQTT  ->  Mosquitto  ->  Python  ->  InfluxDB  ->  Web
  OK        OK          OK           falta      falta       falta
```

O ESP32 publica em `gasguard/<codigo>/leitura` a cada 3s, com payload
`{"codigo":"...","ppm":1834}`. O Mosquitto recebe. Como ainda nao existe
assinante, as mensagens sao descartadas: os tres ultimos elos sao as
etapas 3 a 6.

Contrato de mensagem: o horario NAO vai no payload, quem carimba e o
InfluxDB na gravacao. A tag do Influx e `codigo`, igual a coluna do
Postgres e ao nivel do meio do topico.

## Estrutura

```
gas-guard
 |- backend
 |   |- alembic
 |   |   |- versions
 |   |   |   \- 21bda3d0d359_cria_ambientes_e_dispositivos.py
 |   |   |- env.py
 |   |   |- README
 |   |   \- script.py.mako
 |   |- app
 |   |   |- ambientes
 |   |   |   |- __init__.py
 |   |   |   |- models.py
 |   |   |   |- repository.py    (vazio)
 |   |   |   |- router.py        (vazio) nao registrado no main.py
 |   |   |   \- service.py       (vazio)
 |   |   |- core
 |   |   |   |- __init__.py
 |   |   |   |- database.py      SQLAlchemy + sessao por request
 |   |   |   \- influx.py        gravar_leitura() / ler_ultimas_leituras()
 |   |   |- dispositivos         CRUD completo, em camadas
 |   |   |   |- __init__.py
 |   |   |   |- exceptions.py
 |   |   |   |- models.py
 |   |   |   |- repository.py
 |   |   |   |- router.py
 |   |   |   |- schemas.py
 |   |   |   \- service.py
 |   |   |- leituras             (vazia) etapa 5: historico via API
 |   |   |- mqtt                 (vazia) etapa 3: subscriber paho
 |   |   |- __init__.py
 |   |   \- main.py              FastAPI; falta CORSMiddleware
 |   |- alembic.ini
 |   |- Dockerfile
 |   |- requirements.txt
 |   \- ruff.toml
 |- docs
 |   |- ARCHITECTURE.MD
 |   \- PLAN.MD                  enunciado do professor
 |- firmware                     projeto Wokwi + PlatformIO
 |   |- src
 |   |   \- sketch.ino           ESP32: sensor, alarme local, publish MQTT
 |   |- diagram.json             ESP32 DevKit-C v4, sensor no GPIO 34 (ADC1)
 |   |- libraries.txt            usado pelo wokwi.com
 |   |- platformio.ini           pioarduino (core 3.x) + build_dir ASCII
 |   |- wokwi.toml               aponta para build/ (juncao, nao versionada)
 |   |- sketch.ino.bak           backup pre-millis, pode apagar
 |   \- wokwi-project.txt
 |- frontend                     Vue 3 + TS + Vite
 |   |- public
 |   |   |- favicon.svg
 |   |   \- icons.svg
 |   |- src
 |   |   |- assets
 |   |   |   |- hero.png
 |   |   |   |- vite.svg
 |   |   |   \- vue.svg
 |   |   |- components           (vazia)
 |   |   |- App.vue              
 |   |   |- main.ts
 |   |   \- style.css
 |   |- Dockerfile
 |   |- index.html
 |   |- package.json             axios, chart.js, vue-chartjs, pinia, vue-router
 |   |- tsconfig*.json
 |   \- vite.config.ts
 |- infra
 |   |- mosquitto
 |   |   \- config
 |   |       \- mosquitto.conf   listener 1883, allow_anonymous
 |   \- postgres                 (vazia)
 |- .env / .env.example
 |- docker-compose.yml           postgres + influx + mosquitto
 \- README.md                    
```

## Pendencias conhecidas

1. `frontend/src/App.vue` importa `./components/HelloWorld.vue`, que foi
   apagado. O `npm run dev` e o `npm run build` falham. Precisa de um
   componente proprio no lugar.
2. `ambientes` tem router/service/repository criados mas vazios, e o router
   nao esta registrado no `main.py`. Sem isso nao da para criar um Ambiente
   pela API, e o POST de dispositivo exige um `ambiente_id` que exista.
3. `main.py` sem `CORSMiddleware`: o Vue na 5173 nao consegue chamar a API
   na 8000.
4. O payload publica o valor bruto do ADC (0-4095) num campo chamado `ppm`.
   Ou converte, ou renomeia o campo.

## Notas

**`firmware/build`** e uma juncao (`mklink /J`) para `C:\pio-build\gasguard\esp32dev`.
O toolchain xtensa nao escreve em caminhos com caracteres nao-ASCII (o "3o ano"
deste repo), entao o PlatformIO gera o binario fora e a juncao o expoe dentro do
workspace, que e onde a extensao do Wokwi exige que ele esteja. Nao e versionada:
quem clonar o repo precisa recria-la.

**Backend e frontend nao estao no docker-compose.** Sobem na maquina host; os
`Dockerfile` existem mas ainda nao sao usados. Dockerizar e item do 2o bimestre.

**Postgres nao e exigido nesta etapa.** O PLAN.MD coloca banco relacional no
2o bimestre. O CRUD de dispositivos existe porque o backend precisa saber quais
dispositivos sao validos, mas nao pontua na 1a entrega.
