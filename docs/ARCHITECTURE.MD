# Arquitetura

O diagrama geral está no [README](../README.md#arquitetura). Aqui fica o
porquê de cada peça e as decisões que valem ser defendidas na apresentação.

## Princípio: todo dado passa pelo RabbitMQ

Nenhum serviço chama outro diretamente. O simulador não conhece a API, a cena
3D não conhece o simulador, a IA não conhece o painel. Cada um publica num
barramento e consome dele. Consequências:

- dá para **parar um consumidor** (`docker compose stop gravador`) sem perder
  nada: as mensagens esperam na fila durável e são gravadas quando ele volta;
- um serviço novo (outra IA, um exportador) só precisa de uma fila nova
  ligada na exchange, sem mexer em quem já existe;
- a IA fica **entre** a telemetria e a interface: o painel só sabe da saúde do
  exaustor pelo que a inferência publica.

## Dois brokers, dois papéis

| | Mosquitto (MQTT) | RabbitMQ (AMQP) |
| --- | --- | --- |
| Onde | borda: dispositivo ↔ aplicação | interno: serviço ↔ serviço |
| Por quê | leve, feito para dispositivo pequeno em rede ruim | filas duráveis, vários consumidores por mensagem, roteamento por padrão, ack, DLQ |
| Quem fala | `simulador`, `gateway` | `gateway`, `api`, `gravador`, `regras`, `inferencia`, `lab` |

O `gateway` é o único que fala os dois. Ele valida o payload, confere o
código no cadastro (para não criar série nova no InfluxDB a cada código
inventado), carimba o horário e republica.

## O envelope

Toda mensagem no RabbitMQ tem o mesmo formato (`backend/app/mensageria/envelope.py`):

```json
{
  "id": "6f1c0b9e...",
  "instante": "2026-11-16T19:02:11.483Z",
  "tipo": "telemetria",
  "dispositivo": "GAS-01",
  "conteudo": { "zona": "cozinha", "tipo": "gas", "leituras": { "ppm": 312.5 }, "estado": null }
}
```

Tipos: `telemetria`, `comando`, `insight`, `alerta`, `acionamento`, `job`,
`progresso`, `modelo`. Mensagem que não valida vira `MensagemInvalida` e vai
direto para a DLQ.

## Topologia do RabbitMQ

Declarada em `infra/rabbitmq/topologia.json` e carregada pelo broker ao subir.
Os serviços **não declaram nada**: os usuários deles não têm permissão de
`configure`.

| Exchange | Tipo | Quem publica | Routing keys |
| --- | --- | --- | --- |
| `gg.telemetria` | topic | gateway | `telemetry.<zona>.<tipo>.<dispositivo>` |
| `gg.comandos` | topic | api, regras | `cmd.<zona>.<tipo>.<dispositivo>` |
| `gg.eventos` | topic | inferencia, regras, lab, api | `insight.*`, `alerta.*`, `acionamento.*`, `job.*`, `modelo.*` |
| `gg.jobs` | direct | api | `gerar`, `treinar` |
| `gg.dlx` | fanout | o próprio broker (e o gateway) | qualquer |

| Fila | Ligada em | Consumidor | Argumentos |
| --- | --- | --- | --- |
| `q.gravador` | `telemetry.#`, `insight.#` | gravador | DLX |
| `q.inferencia` | `telemetry.*.exaustor.*` | inferencia | DLX |
| `q.regras` | `telemetry.#` | regras | DLX |
| `q.alertas` | `alerta.#` | regras | DLX |
| `q.websocket` | `telemetry.#`, `#` (eventos), `cmd.#` | api | TTL 30 s, máx. 5000 (dado velho não interessa ao navegador) |
| `q.comandos` | `cmd.#` | gateway | DLX, TTL 30 s (um "fechar válvula" de 10 min atrás não deve executar) |
| `q.jobs.gerar` | `gerar` | lab | DLX |
| `q.jobs.treinar` | `treinar` | lab | DLX |
| `q.dlq` | `gg.dlx` | ninguém: a página Mensageria inspeciona | máx. 10000 |

**Política de erro** (igual em todos, em `mensageria/conexao.py`): mensagem
inválida → `reject` sem requeue → DLQ. Erro inesperado → devolve uma vez para
a fila; se falhar de novo → DLQ. O broker move a mensagem para `gg.dlx` com o
cabeçalho `x-death` (fila de origem, motivo, horário): a mensagem fica
preservada.

**Usuários** (gerados por `scripts/gerar_segredos.py`, sem `guest`):

| Usuário | write (publica em) | read (consome de) |
| --- | --- | --- |
| `gg_api` (tag monitoring) | gg.comandos, gg.jobs, gg.eventos | q.websocket, q.dlq |
| `gg_gateway` | gg.telemetria, gg.dlx | q.comandos |
| `gg_gravador` | — | q.gravador |
| `gg_regras` | gg.comandos, gg.eventos | q.regras, q.alertas |
| `gg_inferencia` | gg.eventos | q.inferencia |
| `gg_lab` | gg.eventos | q.jobs.gerar, q.jobs.treinar |
| `gg_admin` (administrator) | tudo | tudo (só para a interface em 127.0.0.1) |

## MQTT

| Tópico | Quem publica | Quem assina |
| --- | --- | --- |
| `gasguard/<codigo>/telemetria` | simulador | gateway |
| `gasguard/<codigo>/comando` | gateway | simulador |

Payload da telemetria: `{"codigo": "EXAUSTOR-01", "leituras": {"vibracao": 1.9, ...}, "estado": "ligado"}`.
O Mosquitto não aceita anônimo; a ACL (`infra/mosquitto/config/acl`) dá a
cada usuário só os tópicos de que ele precisa. O `gg_observador` só lê, para
acompanhar o MQTT na apresentação.

Comandos para o próprio simulador (injetar falha, vazamento, pausar, acelerar
o relógio) vão para o dispositivo virtual `SIMULADOR`, pelo mesmo caminho.

## Cada banco com seu papel

**PostgreSQL** (relacional, consistência, relações): `usuarios`,
`ambientes`, `dispositivos`, `regras`, `alertas`, `jobs`, `modelos`,
`configuracoes`, `auditoria`. Migrations com Alembic
(`backend/alembic/versions/`). A auditoria só recebe INSERT.

**InfluxDB** (série temporal, escrita contínua, consulta por período):

| Bucket | Measurement | Tags | Fields |
| --- | --- | --- | --- |
| `sensores` | `telemetria` | dispositivo, tipo, zona | ppm, temperatura, vibracao, ..., estado, acionado |
| `sensores` | `insights` | dispositivo, zona | saude, rul_horas, inclinacao_saude |
| `lab` | `sintetico_exaustor` | dataset, equipamento, modo | vibracao, corrente, temperatura, rpm, saude, rul_horas |
| `lab` | `sintetico_ambiente` | dataset, sensor, tipo | valor |

O dado sintético nunca vai para o bucket ao vivo. O dataset completo fica em
arquivos `.npz` no volume `dados_lab`; no InfluxDB vai só uma amostra, para
explorar na interface.

## IA

### O modelo físico (`comum/fisica.py`)

Um arquivo, dois usuários: o **simulador** (um instante por vez) e o
**gerador** do Laboratório (meses de uma vez, em vetores do numpy). Assim o
exaustor que a IA estuda é o mesmo que ela vê ao vivo.

- Ciclo diário: o expediente (almoço e jantar) esquenta a cozinha e aumenta a
  carga do exaustor; há estação do ano e dia/noite na luminosidade.
- Cada exaustor tem uma "personalidade" (vibração, corrente e temperatura de
  base diferentes): é isso que gera sobreposição entre saudáveis e doentes.
- Modos de falha, cada um com assinatura própria nos 4 canais: rolamento
  (vibração dispara), desbalanceamento (vibração sobe linear), entupimento do
  filtro de gordura (**corrente cai**, rotação sobe, motor esquenta),
  superaquecimento (temperatura dispara). E falhas de sensor (deriva,
  travamento), em que a máquina está boa e quem mente é a medição.
- Degradação progressiva: o dano cresce como `progresso^p` (p entre 1,6 e 2,6),
  devagar no começo e rápido no fim, ao longo de 1 a 4 dias.

### O gerador (`backend/app/lab/gerador.py`)

Configurável pela página Laboratório: número de exaustores e de sensores de
ambiente por tipo, dias, % que falha, modos, ruído, % faltantes, % absurdos e
semente. Cada exaustor é um bloco vetorizado (nunca ponto a ponto), com um
gerador aleatório próprio derivado da semente (reprodutível). Rótulos em toda
linha: `saude`, `rul_horas` (teto de 96 h), `degradando`, `modo`. **Os rótulos
nunca saem nas mensagens ao vivo**: o simulador conhece a saúde verdadeira mas
só publica o que um sensor mediria. Teto de 30 milhões de leituras.

### As features (`backend/app/ia/features.py`)

Uma função, `calcular_features`, usada no treino **e** na inferência. Para
cada um dos 4 canais: média curta (30 min), média longa (12 h), desvio e
máximo (3 h), inclinação em 3 h e em 12 h, diferença curta − longa e o
**afastamento da referência da própria máquina** (média das primeiras 24 h
desde a instalação ou a última manutenção). 32 atributos.

Tudo olha só para o passado: `rolling` termina na linha atual, faltante
repete a última leitura válida, pico absurdo é comparado com a mediana das
leituras **anteriores**. Nada usa a média da série inteira (que incluiria o
futuro).

A primeira versão não tinha a referência da máquina e perdeu para a base: o
modelo decorou a temperatura média de cada exaustor do treino. Com a
referência, ele passou a olhar a mudança, não o patamar.

### O treino (`backend/app/ia/treino.py`)

- **Divisão por equipamento**: 70% das máquinas no treino, 15% validação, 15%
  teste, estratificado (as que falham e as que não falham divididas
  separadamente). Nunca por linha: leituras vizinhas da mesma máquina são
  quase iguais e inflariam a nota.
- `HistGradientBoostingRegressor` com perda de erro absoluto, um para cada
  alvo.
- **Base simples**: `DummyRegressor` (sempre a média do treino). O modelo só
  é ativado sozinho se vencer a base nos dois alvos.
- Métricas MAE, RMSE e R² na validação, no teste e no teste só com máquinas
  degradando; gráfico previsto × real; importância por permutação.
- O arquivo vai para o volume `modelos` e os metadados para a tabela
  `modelos`.

### A inferência (`backend/app/servicos/inferencia.py`)

- Guarda, por exaustor, as primeiras 288 leituras (a referência) e as últimas
  144. Na última linha dessa tabela, `calcular_features` dá exatamente o que
  daria com a história inteira.
- A cada 5 s pergunta ao PostgreSQL qual versão está ativa. Mudou? Carrega o
  arquivo novo e troca a referência: **sem reiniciar**. Cada insight leva a
  versão do modelo.
- Cada previsão passa por uma média móvel exponencial (a nova pesa 25%)
  antes de ir para a tela e para os alertas: o ruído do sensor faz a
  previsão de uma leitura oscilar alguns pontos. O valor bruto segue no
  insight (`saude_bruta`, `rul_bruta`).
- Alertas com histerese (`alertas/histerese.py`): 3 previsões seguidas abaixo
  do limite abrem, 10 acima fecham. Limites e contagens na tabela
  `configuracoes`, editáveis na página Regras e limites.
- Motor desligado ou em falha: não há o que prever; publica o estado.
- Ao reiniciar, retoma do banco os alertas que estavam abertos, para
  conseguir fechá-los.

## Tempo real

- O navegador pede um **ticket** (`POST /api/ws/ticket`, com o JWT no
  cabeçalho) e abre `/ws?ticket=...`. O ticket vale 30 s e uma vez só: o JWT
  nunca vai na URL (onde vazaria para logs e histórico).
- A API consome `q.websocket` e repassa a todos os navegadores. Quem conecta
  recebe um snapshot com o último estado de cada dispositivo.
- No frontend, o store `tempoReal` guarda os dados num objeto **sem
  reatividade** (lido pela cena 3D a cada quadro) e só um contador reativo,
  que sobe no máximo 4 vezes por segundo, para as telas comuns.

## Gêmeo 3D (`frontend/src/cena/CenaCozinha.ts`)

- A cena lê o store a cada quadro; mensagem nenhuma redesenha a cena.
- Posições 3D só no frontend, indexadas pelo código do cadastro.
  Dispositivo sem posição vai para a prateleira: todos aparecem.
- Cor por estado (normal, atenção, crítico, sem dados) vinda da faixa do
  sensor, dos alertas e da saúde prevista.
- Ambiente reagindo a dados: dia e noite pela luminosidade, nuvem de gás
  perto do chão pela concentração, partículas no cano e tamanho das chamas
  pela vazão.
- Exaustor gira pela rotação medida e treme mais quanto maior a vibração.
  Válvula vira a alavanca; sirene pisca com luz vermelha.
- O cano é uma lista de pontos que começa na saída do botijão e termina na
  entrada do fogão, passando pelo centro do medidor de vazão e da válvula.
- Piso, azulejos, nuvem de gás e partículas usam `InstancedMesh`.
- Sem leitura por 8 s: animações param, tudo fica cinza e aparece o aviso.

## Assistente

- Ollama no compose, `llama3.2:3b` em CPU, `keep_alive = -1` e pré-carga pela
  API ao subir.
- O backend monta o contexto (`assistente/contexto.py`): instruções fixas e
  arquitetura primeiro (o Ollama reaproveita esse começo entre perguntas),
  depois os dados atuais. O LLM não tem ferramenta nenhuma.
- Resposta em streaming (`StreamingResponse` → `fetch` + `ReadableStream`),
  Markdown sem HTML e sem imagens, 5 perguntas por minuto por usuário, toda
  pergunta na auditoria.

## Segurança

- JWT HS256 (8 h), três papéis; o frontend esconde botões, mas quem decide é
  o backend (401/403).
- bcrypt (12 rodadas); conta trava 5 min depois de 5 erros; no máximo 10
  tentativas por minuto por IP; usuário inexistente gasta o mesmo tempo que
  senha errada.
- Segredos só no `.env` e em `secrets/`, gerados pelo script e ignorados pelo
  Git. Senhas do RabbitMQ vão com hash no `definitions.json`; as do Mosquitto
  viram hash no entrypoint.
- Containers da aplicação com usuário sem privilégio (`gasguard`, uid 10001;
  nginx-unprivileged). Só a porta 8080 da aplicação é publicada; interfaces
  de administração só em 127.0.0.1.

## Docker Compose

Ordem: bancos e brokers ficam `healthy` → `migrador` roda Alembic e seed e
termina → serviços Python (esperam o migrador e o RabbitMQ) → `simulador`
(espera o gateway) → `frontend` (espera a API). Os serviços de fundo tocam
um arquivo de batimento enquanto estão conectados; o healthcheck confere a
idade dele.

## Decisões registradas

**Dispositivo desconhecido é barrado no gateway.** No InfluxDB, `dispositivo`
é tag; tag com valores ilimitados explode a cardinalidade do índice. A
mensagem vai para a DLQ com o motivo.

**A consulta Flux só recebe código validado.** O histórico confere o código
no PostgreSQL antes de montar a consulta por interpolação.

**Escrita síncrona no InfluxDB.** O gravador só dá ack depois da escrita
confirmada; o modo em lote da biblioteca engoliria erros.

**Regra dispara na transição.** Senão mandaria o mesmo comando a cada leitura
e brigaria com o operador que reabriu a válvula.

**A válvula não reabre sozinha.** Depois de um corte por gás crítico, o
rearme é manual, como em sistemas reais de segurança.

**Exclusão de ambiente é física; de dispositivo é lógica.** Dispositivo
desativado preserva o histórico no InfluxDB.

**O ESP32 virou legado.** O enunciado da 2ª entrega pede dispositivo
simulado em software. A pasta `firmware/` fica como registro do 1º bimestre.
