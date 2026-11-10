# Teste guiado: aprender o sistema pelo roteiro da apresentação

Este é o [roteiro da apresentação](ROTEIRO.MD) feito devagar, para estudar.
Cada etapa tem:

- **Faça**: o que digitar ou clicar.
- **Confira**: o que tem de aparecer. Se aparecer, a etapa passou.
- **Por baixo**: o que aconteceu dentro do sistema.
- **No código**: onde olhar, se quiser entender a linha.
- **Se der errado**: o primeiro lugar para investigar.

Reserve umas 2 horas na primeira vez. Os comandos são para o terminal do
VS Code (PowerShell), dentro da pasta do projeto.

Durante o teste, deixe aberto `secrets/usuarios-demo.txt`: todas as senhas
estão lá.

---

## 0. Preparação

**Faça**

1. Abra o Docker Desktop e espere aparecer "Engine running".
2. No terminal:

   ```powershell
   git switch feat/2-bimestre
   docker compose up -d --build
   ```

3. **Opcional, mas recomendado para ensaiar:** começar com os bancos vazios,
   como vai ser na apresentação. Isso apaga cadastro, leituras, modelos e
   filas, mas **mantém o modelo do assistente** (não baixa os 2 GB de novo):

   ```powershell
   docker compose down
   docker volume rm gas-guard_postgres_data gas-guard_influx_data gas-guard_rabbitmq_data gas-guard_dados_lab gas-guard_modelos
   docker compose up -d
   ```

   (`docker compose down -v` também limpa tudo, mas apaga o modelo do
   assistente junto.)

**Confira**

- [ ] `docker compose ps` mostra os serviços como `healthy`. `adminer` não
      tem healthcheck; `migrador` e `ollama-init` aparecem `Exited (0)`.
- [ ] http://localhost:8080 abre a tela de login.

**Se der errado**: `docker compose logs <serviço>` mostra o erro daquele
container. Exemplo: `docker compose logs api`.

---

## 1. Tudo subindo com um comando

**Faça**

```powershell
docker compose ps
docker compose logs migrador
```

**Confira**

- [ ] No log do `migrador`: `Running upgrade ...` (as tabelas sendo criadas)
      e, no fim, `seed concluido`.
- [ ] Na coluna de portas, só o `frontend` aparece como `0.0.0.0:8080`. As
      outras portas publicadas começam com `127.0.0.1:` (só a sua máquina
      acessa).

**Por baixo**

São 16 containers. O `docker-compose.yml` diz quem espera quem com
`depends_on` + `condition: service_healthy`: um serviço só sobe quando o
anterior **responde**, não só quando ele "ligou". O `migrador` cria as
tabelas (Alembic) e os dados iniciais (usuários, cozinha, dispositivos,
regras) e termina; os serviços Python esperam ele acabar com sucesso.

O healthcheck de cada serviço Python confere um arquivo que o serviço "toca"
a cada 5 s enquanto está conectado ao RabbitMQ. Se a conexão cai, o arquivo
envelhece e o Docker marca o container como `unhealthy`.

**No código**: `docker-compose.yml`, `backend/app/seed.py`,
`backend/app/servicos/base.py` (o batimento).

**Pergunta provável**: *"Por que o migrador sai?"* Ele faz um trabalho de
uma vez (migrar e semear) e os outros esperam o fim dele, para nunca rodarem
contra um banco sem tabelas.

---

## 2. Login e os três papéis

**Faça**

1. Entre como `visualizador`.
2. Saia (botão **Sair**) e entre como `operador`.
3. Saia e entre como `administrador`.
4. Teste o bloqueio: saia, digite a senha **errada** do `visualizador` 6
   vezes seguidas.

**Confira**

- [ ] `visualizador`: nos cartões dos atuadores aparece "Comandos disponíveis
      para operador e administrador"; não há cartão do Simulador nem menu
      Auditoria.
- [ ] `operador`: aparecem os botões Ligar/Desligar/Abrir/Fechar e o cartão
      do Simulador.
- [ ] `administrador`: aparece o menu **Auditoria**.
- [ ] Na 6ª tentativa errada: "Conta bloqueada por excesso de tentativas".
      (O bloqueio dura 5 minutos.)

**Por baixo** (pense em HTTP)

O login é um `POST /api/auth/login` com usuário e senha. A API compara a
senha com o **hash bcrypt** guardado na tabela `usuarios` (a senha em si
nunca é gravada) e devolve um **JWT**: um texto assinado com o usuário, o
papel e a validade (8 h). Daí para frente, todo request leva o cabeçalho
`Authorization: Bearer <token>`. Sem ele: **401**. Com ele, mas sem papel
suficiente: **403**.

Para ver o que tem dentro do token: F12 → aba **Console** → cole:

```js
JSON.parse(atob(JSON.parse(sessionStorage.getItem('gasguard-sessao')).token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')))
```

Aparecem `sub` (usuário), `papel`, `nome`, `exp` (validade). O conteúdo não
é secreto, só **assinado**: quem alterar o papel quebra a assinatura e a API
recusa.

**No código**: `backend/app/auth/service.py` (bloqueio e tentativas),
`backend/app/auth/seguranca.py` (bcrypt e JWT), `backend/app/auth/deps.py`
(o `exige("operador")` das rotas).

**Pergunta provável**: *"Esconder o botão não basta?"* Não: qualquer um pode
chamar a API direto. O botão some por conforto; quem bloqueia é o backend
(próxima etapa mostra o 403).

---

## 3. Simulador publicando no Mosquitto

**Faça**

1. Leia em `secrets/usuarios-demo.txt` a senha do `gg_observador`.
2. No terminal (troque `SENHA`):

   ```powershell
   docker compose exec mosquitto mosquitto_sub -u gg_observador -P "SENHA" -t "gasguard/#" -v
   ```

   Pare com **Ctrl+C**.
3. Agora tente **sem** usuário:

   ```powershell
   docker compose exec mosquitto mosquitto_sub -t "gasguard/#"
   ```

**Confira**

- [ ] A cada 2 s, uma linha por dispositivo, por exemplo
      `gasguard/GAS-01/telemetria {"codigo": "GAS-01", "leituras": {"ppm": 251.3}}`.
- [ ] O exaustor manda 4 leituras e o estado:
      `{"vibracao": 1.6, "corrente": 3.3, "temperatura": 40.0, "rpm": 1683.7}, "estado": "ligado"`.
- [ ] Sem usuário: `Connection Refused: not authorised`.

**Por baixo**

O MQTT é "publicar num tópico / assinar um tópico". O `#` assina tudo abaixo
de `gasguard/`. O simulador faz o papel do ESP32 do 1º bimestre: 8
dispositivos publicando. Repare que **não tem saúde nem horário** no payload:
o simulador sabe a saúde verdadeira do exaustor, mas só publica o que um
sensor mediria; e quem carimba o horário é o gateway.

O Mosquitto não aceita anônimo, e o arquivo de ACL dá a cada usuário só os
tópicos dele: o simulador só **escreve** telemetria e só **lê** comandos; o
observador só lê.

**No código**: `simulador/simulador.py`, `infra/mosquitto/config/acl`,
`comum/fisica.py` (as fórmulas do exaustor).

---

## 4. A API REST (Swagger)

**Faça**

1. Abra http://localhost:8080/api/docs.
2. Clique em **Authorize**, preencha `username` = `visualizador` e a senha,
   e confirme.
3. Abra `GET /api/dispositivos` → **Try it out** → **Execute**.
4. Abra `POST /api/dispositivos/{codigo}/comandos`, `codigo` = `VALVULA-01`,
   corpo `{"acao": "fechar"}` → **Execute**.
5. **Authorize** de novo (Logout, depois login) como `operador` e repita o
   passo 4.
6. Repita com `{"acao": "ligar"}`.
7. Volte a válvula: `{"acao": "abrir"}`.

**Confira**

- [ ] Passo 3: **200** e a lista de dispositivos.
- [ ] Passo 4 (visualizador): **403** "Ação permitida a partir do papel operador".
- [ ] Passo 5 (operador): **202** com a `routing_key`
      `cmd.cozinha.valvula.VALVULA-01`. No Painel, a válvula aparece
      "Fechada" e a vazão de gás vai a 0.
- [ ] Passo 6: **422** "Ação inválida para valvula; use: abrir, fechar".

**Por baixo**

Por que **202** e não 200? A API só garante que o comando **entrou na fila**.
Quem confirma que a válvula fechou é a **próxima leitura** do simulador, que
volta pelo caminho da telemetria. É o "Accepted" do HTTP: aceito para
processamento, ainda não processado.

**No código**: `backend/app/dispositivos/router.py` (rota de comando) e
`backend/app/dispositivos/service.py` (`montar_comando`).

---

## 5. Mensageria (RabbitMQ)

**Faça**

1. No app, página **Mensageria**.
2. Abra também http://127.0.0.1:15672 e entre com `gg_admin` (senha no
   arquivo). Veja as abas **Queues**, **Exchanges** e **Admin → Users**.
3. Pare um consumidor:

   ```powershell
   docker compose stop gravador
   ```

   Espere uns 30 s olhando a fila `q.gravador`. Depois:

   ```powershell
   docker compose start gravador
   ```

4. Como `administrador`, na Mensageria clique em **Publicar mensagem inválida**.

**Confira**

- [ ] Cada fila mostra o serviço que consome (gravador, inferencia, regras,
      api, gateway, lab).
- [ ] Com o gravador parado, `q.gravador` passa de 100 mensagens e a linha
      fica avermelhada ("parado").
- [ ] Ao religar, esvazia em poucos segundos.
- [ ] A mensagem inválida aparece em **q.dlq** com motivo `rejected`, vinda de
      `q.alertas`.
- [ ] No RabbitMQ, **Admin → Users**: um usuário por serviço, sem `guest`.

**Por baixo**

Pense no RabbitMQ como uma central de correio. O gateway entrega cada leitura
na **exchange** `gg.telemetria` com um endereço, a **routing key**
`telemetry.cozinha.gas.GAS-01`. Cada **fila** se inscreve num padrão
(**binding**): `q.gravador` recebe `telemetry.#` (tudo); `q.inferencia` só
`telemetry.*.exaustor.*`. A mesma mensagem vai para várias filas, uma cópia
para cada uma.

O consumidor confirma (**ack**) só depois de terminar o trabalho. Parado, não
confirma nada e as mensagens esperam na fila (é durável, nada se perde).
Mensagem que o consumidor **rejeita** vai para a fila de mensagens mortas
(DLQ), preservada, com um cabeçalho dizendo de onde veio.

Por que dois brokers? O MQTT é leve e feito para o dispositivo. O RabbitMQ
tem filas duráveis, várias cópias por mensagem, ack e DLQ para dentro da
aplicação.

**No código**: `infra/rabbitmq/topologia.json` (todas as filas e ligações),
`backend/app/mensageria/conexao.py` (a regra de ack/DLQ),
`backend/app/servicos/gateway.py`, `backend/app/mensageria/router.py` (a
página consulta a API de gerenciamento do RabbitMQ).

---

## 6. InfluxDB e PostgreSQL

**Faça**

1. http://127.0.0.1:8086 → login do InfluxDB (no arquivo de senhas) →
   **Data Explorer** → **Script Editor** → cole e clique **Submit**:

   ```flux
   from(bucket: "sensores")
     |> range(start: -15m)
     |> filter(fn: (r) => r._measurement == "telemetria" and r.dispositivo == "GAS-01" and r._field == "ppm")
   ```

2. http://127.0.0.1:8081 (Adminer) → Sistema **PostgreSQL**, servidor
   `postgres`, usuário `gasguard`, senha do arquivo, base `gasguard`. Clique
   em **Comando SQL** e rode, um de cada vez:

   ```sql
   select codigo, nome, categoria, tipo, ativo from dispositivos;
   select id, nome, dispositivo_codigo, operador, limite, alvo_codigo, acao from regras;
   select instante, usuario, acao, detalhe from auditoria order by id desc limit 20;
   ```

3. No app, **Painel** → período **1 hora (InfluxDB)**.

**Confira**

- [ ] O InfluxDB mostra o gráfico do gás dos últimos 15 min.
- [ ] A auditoria tem os seus logins, o login que falhou e o comando da
      etapa 4.
- [ ] O gráfico de 1 hora no Painel é o mesmo dado do InfluxDB, em médias
      por janela.

**Por baixo**

Cada banco faz o que sabe fazer melhor:

- **InfluxDB**: dados que chegam o tempo todo e são lidos por período
  ("últimas 6 horas"). Leituras e previsões da IA.
- **PostgreSQL**: dados com relações e consistência. Usuário, dispositivo e
  seu ambiente, regras, alertas, auditoria.

O histórico do painel é um `GET /api/leituras/GAS-01?minutos=60`: a API
confere o código no PostgreSQL e só então consulta o InfluxDB.

**No código**: `backend/app/core/influx.py`, `backend/app/leituras/service.py`,
os `models.py` de cada pasta (as tabelas).

---

## 7. Painel em tempo real (WebSocket)

**Faça**

1. **Painel**, com F12 aberto na aba **Network**. Recarregue a página (F5).
2. Filtre por `ticket`: clique no request `ticket`.
3. Filtre por **WS**: clique em `ws?ticket=...` → aba **Messages**.
4. Reinicie a API para ver a reconexão:

   ```powershell
   docker compose restart api
   ```

**Confira**

- [ ] Primeiro um `POST /api/ws/ticket` (com o JWT no cabeçalho); depois o
      `ws?ticket=...` com status **101 Switching Protocols**.
- [ ] Em **Messages**, chega uma mensagem por leitura, a cada 2 s, no
      formato `{"rk": "...", "id", "instante", "tipo", "dispositivo", "conteudo"}`.
- [ ] Com a API reiniciando, o indicador no topo fica vermelho
      ("WebSocket desconectado") e volta para "Ao vivo" sozinho.

**Por baixo**

O WebSocket começa como um request HTTP que pede um "upgrade" (o 101) e vira
um canal aberto, por onde o servidor **empurra** dados sem o navegador
pedir. Nada aqui é polling.

O navegador não consegue mandar o cabeçalho `Authorization` ao abrir um
WebSocket. Pôr o JWT na URL vazaria o token em logs e no histórico. Por isso:
pega-se um **ticket** que vale 30 s e uma vez só, e é ele que vai na URL.

**No código**: `backend/app/tempo_real/tickets.py`, `backend/app/tempo_real/hub.py`,
`frontend/src/stores/tempoReal.ts`.

---

## 8. Regra automática e controle pela Web

Entre como `operador`, no **Painel**.

**Faça**

1. No cartão do **Exaustor**, clique **Desligar**.
2. No cartão **Simulador da cozinha**, clique **Vazamento forte** e acompanhe
   o cartão do gás e a lista **Eventos ao vivo**.
3. Quando a válvula fechar, clique **Parar vazamento**.
4. Quando o gás ficar abaixo de 1.000 ppm, clique **Abrir** na válvula.

**Confira** (tempos aproximados)

- [ ] Passo 1: na leitura seguinte o exaustor fica "Desligado", rotação e
      corrente vão a 0.
- [ ] ~10 a 15 s: o gás passa de 1.000 ppm → evento "Regra 'Gás em atenção
      liga o exaustor'" e o exaustor volta a "Ligado" sozinho.
- [ ] ~45 a 50 s: passa de 2.000 ppm → a válvula fecha e a sirene liga
      sozinhas. A vazão vai a 0 e o gás começa a cair.
- [ ] Abaixo de 1.000 ppm a sirene desliga sozinha.
- [ ] A válvula **não** reabre sozinha: só pelo botão (passo 4).
- [ ] Como administrador, em **Auditoria**, filtro "Comandos": aparecem
      `comando.regra` (sistema) e `comando.enviado` (operador).

**Por baixo**

O serviço `regras` lê toda a telemetria (fila `q.regras`) e compara com as
regras da tabela `regras`. A regra dispara na **transição**: quando a
condição passa de falsa para verdadeira, não a cada leitura. E só manda o
comando se o atuador ainda não estiver no estado pedido.

O comando automático faz o **mesmo caminho** do botão: `gg.comandos` →
gateway → MQTT → simulador. A válvula não reabre sozinha de propósito: em
sistemas reais de segurança o rearme é manual.

**No código**: `backend/app/servicos/regras.py`, a página **Regras e
limites** (dá para pausar e criar regras).

---

## 9. Laboratório de dados

Entre como `administrador`.

**Faça**

1. **Laboratório** → deixe os valores padrão → **Gerar dados**.
2. Em paralelo, no terminal: `docker compose logs -f lab` (Ctrl+C para sair).
3. Quando terminar, no InfluxDB (bucket **lab**), Script Editor. Troque
   `ds7` pelo nome do dataset que apareceu no Laboratório:

   ```flux
   from(bucket: "lab")
     |> range(start: -70d)
     |> filter(fn: (r) => r._measurement == "sintetico_exaustor" and r.dataset == "ds7" and r.modo != "saudavel")
     |> filter(fn: (r) => r._field == "vibracao" or r._field == "saude")
   ```

**Confira**

- [ ] A barra de progresso anda sozinha (WebSocket) e termina em ~45 s.
- [ ] Resultado: cerca de 7,5 milhões de leituras, ~38 máquinas que falham,
      e a contagem por modo de falha.
- [ ] No log do `lab`: `job N (gerar) comecou` e `job N concluido`.
- [ ] No InfluxDB aparecem 2 máquinas que falharam: a vibração sobe aos
      poucos e a saúde cai até 0 no fim da série.

**Por baixo**

O botão faz um `POST /api/lab/jobs`, que responde **202 na hora**: a API só
registra o job no PostgreSQL e o põe na fila `q.jobs.gerar`. Quem gera é o
serviço `lab`, em outro container; a API nunca trava.

O gerador simula a vida inteira de 120 exaustores com o **mesmo modelo
físico** do simulador: desgaste progressivo, ciclo do dia, ruído, leituras
faltando e valores absurdos. Cada linha tem a **resposta certa** (saúde e
horas até a falha). Essas respostas existem só aqui, nunca nas mensagens ao
vivo.

**No código**: `backend/app/lab/gerador.py`, `comum/fisica.py`,
`backend/app/servicos/lab.py`.

---

## 10. Treinamento

**Faça**

1. **Treinamento** → escolha o dataset que acabou de gerar → **Treinar**.
2. Em paralelo: `docker compose logs -f inferencia`.
3. Quando terminar, leia a tabela e os gráficos da versão nova.

**Confira**

- [ ] ~40 s depois, a versão nova aparece "em uso".
- [ ] No log da `inferencia`: `modelo vN carregado e em uso` (sem reiniciar
      o container).
- [ ] Nas duas tabelas, o **MAE do modelo** é bem menor que o **MAE da base**
      e o selo diz "venceu a base".
- [ ] No gráfico previsto × real, os pontos ficam perto da diagonal.
- [ ] Na importância, o primeiro atributo é `vibracao_vs_referencia`.

**Por baixo** (as métricas em palavras)

- **MAE**: quanto o modelo erra, em média, na unidade do alvo. MAE 0,2 na
  saúde = erra 0,2 ponto de 100.
- **RMSE**: parecido, mas castiga mais os erros grandes.
- **R²**: quanto da variação o modelo explica. 1 = tudo; 0 = igual a chutar a
  média.
- **Base simples**: um "modelo" que sempre responde a média. Se o nosso não
  ganhasse dele, não teria aprendido nada.
- **Só máquinas degradando**: o caso difícil. A vida útil vai pior aqui,
  porque no começo do desgaste os sensores quase não mudam.

As máquinas são divididas **inteiras** entre treino, validação e teste. Se a
divisão fosse por linha, a leitura das 10h05 de uma máquina iria para o
treino e a das 10h10 para o teste: o modelo "colaria" na prova.

**No código**: `backend/app/ia/treino.py`, `backend/app/ia/features.py` (a
mesma função calcula as entradas no treino e ao vivo),
`backend/app/ia/registro.py` (a troca de versão sem reiniciar).

---

## 11. Falha injetada: Insights e cena 3D

**Faça**

1. **Insights** → clique **Reparar** (zera a "referência" do exaustor, para
   começar limpo). Espere **2 minutos** com saúde 100 e vida útil 96 h.
2. Escolha **Desgaste de rolamento**, 20 h → **Injetar falha**. Marque o
   horário.
3. Abra o **Gêmeo 3D** numa segunda aba e clique no exaustor.
4. Depois que ele quebrar, volte em Insights → **Reparar**.

**Confira** (tempos aproximados, a partir da injeção)

- [ ] ~20 s: abre o alerta de **vida útil** (atenção), em torno de 20 h.
- [ ] 1 a 2 min: saúde por volta de 80, tendência **piorando**.
- [ ] 3 a 5 min: saúde abaixo de 60 → abre o alerta de **saúde**; a vibração
      passa de 4,5 mm/s → alerta de **limite**.
- [ ] Na cena, o anel do exaustor fica amarelo e ele treme cada vez mais.
- [ ] ~8 min: o exaustor **para** (estado "falha", saúde 0, alerta
      **crítico** "parou por falha"), anel vermelho, para de girar.
- [ ] Depois do Reparar: em ~30 s volta a 100 / 96 h e os alertas fecham.

**Teste também na cena 3D**

- [ ] **Painel → Vazamento forte**: nuvem de gás perto do chão (o GLP é mais
      pesado que o ar). Depois **Parar vazamento**.
- [ ] **Painel → Relógio 120×**: a janela vira dia/noite em poucos minutos.
      Volte com **Relógio 1×**.
- [ ] **Painel → Pausar simulador**: em 8 s a cena fica cinza com "Sem dados
      em tempo real". **Retomar** para voltar.

**Por baixo**

O serviço `inferencia` recebe a telemetria do exaustor, calcula os 32
atributos e aplica os dois modelos a cada leitura. As previsões passam por
uma média móvel (a previsão de uma leitura sozinha oscila). Os alertas usam
**histerese**: abrem com 3 previsões seguidas ruins e só fecham com 10
seguidas boas **e com folga** do limite, para não ficarem piscando.

Ao vivo, cada leitura do exaustor (a cada 2 s) vale **5 minutos** de
operação: 20 h viram 240 leituras, uns 8 minutos de apresentação.

Por que **Reparar** antes? A inferência compara cada máquina com ela mesma
"quando nova" (as primeiras leituras depois de ligada ou reparada). Se a
referência for tomada com o exaustor já gasto, as previsões ficam otimistas.

**No código**: `backend/app/servicos/inferencia.py`,
`backend/app/alertas/histerese.py`, `frontend/src/cena/CenaCozinha.ts` (a
cena lê o store a cada quadro; nada redesenha a cada mensagem).

---

## 12. Assistente com LLM local

**Faça**

1. **Assistente** → espere "Modelo pronto" no canto.
2. Faça uma pergunta de aquecimento qualquer (a primeira é a mais lenta).
3. Pergunte: *"O exaustor tem algum alerta? O que ele significa e o que devo
   fazer?"*
4. Clique **Ver o contexto enviado ao modelo**.
5. Mande 6 perguntas seguidas em menos de 1 minuto.

**Confira**

- [ ] A resposta chega aos pedaços (streaming), em português, citando os
      números do sistema (saúde, vida útil, alertas).
- [ ] O contexto mostra exatamente os dados que o modelo recebeu.
- [ ] A 6ª pergunta: "Limite de 5 perguntas por minuto".
- [ ] Em **Auditoria**, filtro "Perguntas ao assistente": as perguntas estão lá.

**Por baixo**

O modelo (`llama3.2:3b`) roda no container `ollama`, na CPU, sem internet e
sem chave. Ele **não acessa banco nenhum**: a cada pergunta, a API monta um
resumo dos dados atuais e envia junto com a pergunta. Modelos pequenos erram
quando precisam escolher "ferramentas" sozinhos; com o resumo pronto, só
precisam ler e explicar.

A resposta é tratada como texto não confiável: o Markdown aparece sem HTML e
sem imagens.

**No código**: `backend/app/assistente/contexto.py`,
`backend/app/assistente/router.py`, `frontend/src/components/TextoMarkdown.vue`.

---

## Mapa: o que cada etapa prova na nota

| Critério (1,0 cada) | Etapas |
| --- | --- |
| Evolução, segurança mínima, GitHub com README | 1, 2, 4 |
| Sensores, atuadores e MQTT + Mosquitto | 3, 8 |
| Regra automática e controle pela Web | 4, 8 |
| RabbitMQ: exchange, filas, consumidores, DLQ, Mensageria | 5 |
| PostgreSQL e InfluxDB | 6 |
| WebSocket, dashboard, gráficos e histórico | 6, 7 |
| Interface 3D | 11 |
| Dados sintéticos e modelos de regressão | 9, 10 |
| Insights de IA e LLM local | 11, 12 |
| Docker Compose e apresentação completa | 0, 1 e todas |

## Se der errado

| Sintoma | O que fazer |
| --- | --- |
| Container `unhealthy` ou reiniciando | `docker compose logs <serviço>` |
| Painel e cena em "Sem dados" | Simulador pausado? Clique **Retomar**. Ou `docker compose restart simulador`. |
| Insights "sem modelo treinado" | Faça as etapas 9 e 10 |
| Previsões estranhas depois de reiniciar a inferência | Insights → **Reparar** e espere 2 min |
| Assistente "Baixando o modelo" | Primeira subida: `docker compose logs -f ollama-init` até `success` |
| "Conta bloqueada" | Espere 5 min ou use outro usuário |
| Botão de comando dá erro 503 | RabbitMQ fora: `docker compose ps rabbitmq` |
| Tudo lento | Docker com pouca memória: confira o `.wslconfig` (10 GB) |
