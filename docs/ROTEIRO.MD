# Roteiro da apresentação (16/11/2026)

Na ordem pedida pelo enunciado. Cada etapa tem o que fazer, o que deve
aparecer e uma frase para explicar. Tempo total: uns 25 minutos.

## Antes da aula

- [ ] `.wslconfig` com `memory=10GB` e Docker Desktop aberto.
- [ ] `git pull`, depois `python scripts/gerar_segredos.py` (só completa o que falta).
- [ ] **30 min antes**: `docker compose up -d --build`. A primeira subida baixa
      ~2 GB do modelo de linguagem; com o volume pronto, sobe em ~1 min.
- [ ] Abra `secrets/usuarios-demo.txt` (senhas da demo e das interfaces).
- [ ] Faça uma pergunta qualquer ao Assistente: a primeira resposta em CPU é a
      mais lenta.
- [ ] Deixe abertas: http://localhost:8080, http://127.0.0.1:15672,
      http://127.0.0.1:8086, http://127.0.0.1:8081 e um terminal na pasta do projeto.
- [ ] Plano B: se a geração ou o treino falharem na hora, já deixe um modelo
      treinado de antes (a página Treinamento mostra todas as versões; dá para
      "Usar esta versão").
- [ ] Se o banco ainda tiver dispositivos do 1º bimestre (`ESP32-COZINHA-01`),
      desative-os em **Dispositivos** para não aparecerem como "sem dados".

## 1. Tudo subindo com um comando

```bash
docker compose up -d --build
docker compose ps
```

Todos `healthy`; `migrador` e `ollama-init` aparecem `Exited (0)` (fazem o
trabalho e saem).

> "São 16 containers. Os serviços têm healthcheck, e a ordem de subida espera o
> anterior ficar saudável: bancos e brokers, depois o migrador cria as
> tabelas, depois os serviços Python, o simulador e por último o frontend. Só
> a porta 8080 da aplicação fica aberta; as interfaces de administração
> escutam só em 127.0.0.1."

## 2. Login e os três papéis

Entre como `visualizador`: o painel não mostra botões de comando nem o
Laboratório para gerar. Mostre que a API também recusa:

```bash
# no Swagger (/api/docs), Authorize como visualizador e tente
# POST /api/dispositivos/VALVULA-01/comandos -> 403
```

Depois entre como `operador` (aparecem os botões) e `administrador`
(aparece Auditoria).

> "Senha com bcrypt, token JWT de 8 horas, e cinco erros seguidos travam a
> conta por 5 minutos. Esconder o botão é conforto; quem decide é o backend."

## 3. Simulador publicando no Mosquitto

```bash
docker compose exec mosquitto mosquitto_sub -u gg_observador -P <senha do usuarios-demo.txt> -t 'gasguard/#' -v
```

Aparecem `gasguard/GAS-01/telemetria`, `gasguard/EXAUSTOR-01/telemetria`...

> "O simulador substitui o ESP32: são 8 dispositivos publicando a cada 2
> segundos. O Mosquitto não aceita anônimo e cada usuário só acessa os
> tópicos dele; este observador só lê."

## 4. A API REST

http://localhost:8080/api/docs. Mostre as seções (dispositivos, leituras,
regras, laboratório, IA, mensageria, assistente) e use o **Authorize**.

## 5. Mensageria (RabbitMQ)

Página **Mensageria**. Mostre as filas, quem consome cada uma e as taxas.

```bash
docker compose stop gravador
```

Em ~20 s a fila `q.gravador` passa de 100 mensagens (linha fica vermelha;
consumidor "parado").

```bash
docker compose start gravador
```

A fila esvazia em segundos.

> "O gateway lê o MQTT e republica no RabbitMQ, numa exchange topic com
> routing key telemetry.zona.tipo.dispositivo. Cada serviço tem a sua fila: o
> gravador parado não afeta os outros, e nada se perde porque a fila é
> durável. Cada serviço entra com um usuário próprio no RabbitMQ, sem o
> guest."

DLQ: clique **Publicar mensagem inválida** (administrador). Ela aparece em
`q.dlq` com o motivo `rejected` e a fila de origem `q.alertas`.

> "O que falha vai para a fila de mensagens mortas, preservado, com o
> cabeçalho dizendo de onde veio."

## 6. InfluxDB e PostgreSQL

- InfluxDB (127.0.0.1:8086), Data Explorer, bucket `sensores`, measurement
  `telemetria`, filtro `dispositivo = GAS-01`.
- Adminer (127.0.0.1:8081, servidor `postgres`): tabelas `dispositivos`,
  `regras`, `auditoria`.
- No **Painel**, troque o período para "1 hora": o gráfico vem do InfluxDB.

> "InfluxDB guarda o que é série temporal: leituras e previsões. PostgreSQL
> guarda o que tem relação e precisa de consistência: cadastro, usuários,
> regras, alertas e auditoria."

## 7. Painel em tempo real

O indicador "Ao vivo" no topo, cartões e gráfico mudando a cada 2 s.

> "Nada aqui é polling: a API consome a fila q.websocket e empurra cada
> mensagem pelo WebSocket. Para abrir o WebSocket o navegador pede um ticket
> que vale 30 segundos e uma vez só: o token nunca vai na URL."

## 8. Regra automática e controle pela Web

Como `operador`, no Painel:

1. **Desligar** o exaustor (botão no cartão dele). Na leitura seguinte: estado
   desligado, rotação e corrente zero.
2. **Vazamento forte** (cartão do Simulador).
3. Em ~10 s o gás passa de 1.000 ppm: a regra **liga o exaustor sozinha**
   (aparece em "Eventos ao vivo").
4. Em ~40 s passa de 2.000 ppm: a regra **fecha a válvula** e **liga a
   sirene**. A vazão cai a zero e o gás começa a cair.
5. **Parar vazamento**. Abaixo de 1.000 ppm a sirene desliga sozinha.
6. **Abrir** a válvula pelo botão: o rearme é manual.

> "A regra está no PostgreSQL e roda no serviço regras. Ela dispara na
> transição e só manda o comando se o atuador ainda não estiver no estado
> pedido. O comando automático faz o mesmo caminho do botão: RabbitMQ,
> gateway, MQTT, simulador."

## 9. Laboratório de dados

Como `administrador`, **Laboratório** → **Gerar dados** com o padrão (120
exaustores, 60 dias, 50% falham): cerca de 7,5 milhões de leituras em ~1 min.
A barra de progresso anda pelo WebSocket.

> "Equipamento real leva meses para falhar, então simulamos a vida inteira de
> uma frota, com o mesmo modelo físico do simulador. A degradação é
> progressiva, tem ciclo diário, ruído, leituras faltando e valores absurdos.
> Cada linha tem a saúde verdadeira e o tempo até a falha, mas esses rótulos
> nunca vão nas mensagens ao vivo. O job roda na fila q.jobs.gerar, fora da
> API."

Mostre no InfluxDB o bucket `lab` (amostra de 3 exaustores).

## 10. Treinamento

**Treinamento** → escolha o dataset → **Treinar** (~1 min). Leia as tabelas:

> "Dividimos por máquina: as do teste o modelo nunca viu. A base simples
> responde sempre a média; o modelo só entra em uso se vencer essa base nos
> dois alvos. A saúde fica com R² perto de 0,95. A vida útil é mais difícil
> (veja a linha 'só máquinas degradando'): no começo do desgaste os sensores
> quase não mudam. O atributo mais importante é o quanto a vibração se
> afastou de como a máquina era quando nova."

A versão nova aparece "em uso" e a inferência troca sem reiniciar.

## 11. Falha injetada: Insights e cena 3D

Espere ~1 min depois do treino (a inferência junta as primeiras leituras).
Em **Insights**: saúde ~100, vida útil 96 h. Então **Injetar falha**
(rolamento, 20 h). Em ~2 a 4 min:

- a saúde cai, a tendência vira "piorando";
- abrem os alertas de saúde e de vida útil (3 previsões seguidas ruins);
- no **Gêmeo 3D**, o exaustor fica amarelo e depois vermelho, e treme cada
  vez mais. Clique nele: última leitura, mini gráfico e saúde prevista.

> "O simulador nunca publica a saúde: quem descobre é o modelo, olhando
> vibração, corrente, temperatura e rotação. Ao vivo, cada leitura do
> exaustor vale 5 minutos de operação, para a falha caber na apresentação."

Na cena, mostre também: janela de dia/noite pela luminosidade (botão
**Relógio 120×** no Painel faz um dia passar em 12 min), nuvem de gás no
chão durante um vazamento, partículas no cano e chamas pela vazão. Pare o
simulador (**Pausar simulador** ou `docker compose stop simulador`): a cena
congela, fica cinza e avisa "Sem dados".

Depois, **Reparar** o exaustor: os alertas fecham depois de 10 previsões boas.

## 12. Assistente com LLM local

Pergunte: "O exaustor tem algum alerta? O que ele significa e o que devo
fazer?". A resposta chega aos pedaços.

> "O modelo roda aqui, no container ollama, em CPU, sem chave e sem nuvem. Ele
> não acessa banco nenhum: a cada pergunta o backend monta um resumo com
> leituras, previsões, alertas e métricas e manda junto. Clique em 'Ver o
> contexto enviado ao modelo' para mostrar."

Mostre na **Auditoria** a pergunta registrada.

## Perguntas que podem aparecer

- **Por que dois brokers?** MQTT é leve para o dispositivo; RabbitMQ dá filas
  duráveis, vários consumidores, DLQ e roteamento dentro da aplicação.
- **Por que dividir por equipamento?** Leituras vizinhas da mesma máquina são
  quase iguais; dividir por linha seria "colar" na prova.
- **O que é vazamento de dados?** Usar informação do futuro para prever o
  presente. As janelas só olham para trás e nenhuma estatística usa a série
  inteira.
- **Como o modelo novo entra sem reiniciar?** A inferência consulta a versão
  ativa a cada 5 s e troca o arquivo carregado.
- **Por que histerese?** Para o alerta não piscar com valor oscilando no limite.
- **O que acontece se o RabbitMQ cair?** Os serviços reconectam sozinhos
  (`connect_robust`); a API responde 503 nas rotas que publicam.
