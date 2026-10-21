# Enunciado do 2º bimestre

Cópia do enunciado do professor (última atualização: 5 out. 2026), para
referência do grupo. Apresentação: **16/11/2026**.

## Objetivo

Continuar e evoluir o projeto do 1º bimestre, transformando o protótipo numa
aplicação AIoT completa: Web + IoT + Inteligência Artificial. Além de novos
sensores, atuadores, comunicação em tempo real, banco relacional e
containers, a aplicação deve gerar dados sintéticos em massa, treinar modelos
de regressão com esses dados, mostrar o resultado em uma interface 3D ao vivo,
trafegar as mensagens por um broker RabbitMQ e responder perguntas sobre os
dados com um LLM rodando localmente. Mesmo problema e proposta do 1º
bimestre, agora com equipamentos monitorados para manutenção preditiva.

## Stack obrigatória

| Camada | Tecnologia | Finalidade |
| --- | --- | --- |
| Frontend | Vue.js 3 ou React, com TypeScript + Vite | Interface Web |
| Visualização 2D | Chart.js ou Apache ECharts | Gráficos e indicadores |
| Visualização 3D | Three.js (direto, TresJS ou React Three Fiber) ou equivalente | Gêmeo digital 3D em tempo real |
| Backend | Python + FastAPI | API REST, regras de negócio e integração |
| Tempo real | WebSocket | Atualização ao vivo |
| IoT | MQTT + Mosquitto | Dispositivos ↔ aplicação |
| Dispositivo | Simulador em software (Python) | Sensores e atuadores simulados via MQTT |
| Mensageria | RabbitMQ | Barramento interno entre os serviços |
| IA | Python + scikit-learn (ou equivalente) | Regressão e inferência |
| LLM local | Ollama (ou equivalente), modelo pequeno em CPU | Assistente sobre os dados |
| Banco relacional | PostgreSQL | Usuários, dispositivos, configurações, regras, alertas, auditoria |
| Séries temporais | InfluxDB | Leituras e telemetria |
| Infraestrutura | Docker + Docker Compose | Execução e integração |
| Versionamento | Git + GitHub | Controle de versão |

Proibido: Node.js como backend e LLM em nuvem.

## Requisitos mínimos

- Interface Web em Vue 3 ou React, com TypeScript e Vite
- Backend Python + FastAPI com API REST
- WebSocket para tempo real
- MQTT com Mosquitto, nos dois sentidos
- Pelo menos 3 sensores simulados e 2 atuadores
- Pelo menos 1 equipamento monitorado para manutenção preditiva, com no
  mínimo 3 variáveis medidas
- Pelo menos 1 atuador acionado por regra de negócio e 1 controlado pela Web
- RabbitMQ como barramento interno, com filas, consumidores e uma tela para
  acompanhá-lo
- PostgreSQL e InfluxDB, cada um com papel claro
- Dashboard com gráficos, indicadores e histórico
- Cadastro e gerenciamento dos dispositivos
- Interface 3D atualizada somente por dados em tempo real
- Gerador de dados sintéticos massivos configurável pela interface
- Pelo menos 2 modelos de regressão treinados com os dados sintéticos, com
  métricas
- Insights em tempo real: saúde, vida útil restante e alertas preditivos
- Assistente com LLM local respondendo sobre os dados
- Docker Compose subindo tudo com um único comando
- Código no GitHub

## Fluxos que precisam ser demonstrados

1. **IoT → Web**: sensor simulado, MQTT, gateway, RabbitMQ, gravador no
   InfluxDB, API, WebSocket e dashboard.
2. **Web → IoT**: botão no dashboard, API, RabbitMQ, gateway, MQTT,
   simulador e atuador, que muda de estado e aparece nas leituras seguintes.
3. **IA**: o laboratório gera os dados, o treino cria os modelos, a
   inferência os aplica à telemetria ao vivo e devolve previsões e alertas
   pelo RabbitMQ até a interface.

## Interface 3D

- Muda somente com dados do WebSocket; sem ligação direta com o simulador. Se
  o simulador desligar, a cena para e avisa que não há dados.
- Todos os sensores, atuadores e o equipamento aparecem; posição 3D só no
  frontend, indexada pelo id do cadastro.
- Cor por estado: normal, atenção, crítico ou sem dados (faixa do sensor +
  alertas da IA).
- Atuadores animados quando ligados; equipamento treme mais quanto mais
  vibração.
- Pelo menos 2 elementos do ambiente reagindo a dados reais.
- Clique abre painel com última leitura, mini gráfico, saúde prevista e
  comandos.
- Tubulações saem e chegam exatamente nos equipamentos.
- Desempenho: dados num store lido no loop de animação; InstancedMesh para
  repetições.

## RabbitMQ

- Exchange topic com routing keys de tipo e dispositivo
  (`telemetry.<zona>.<tipo>.<id>`).
- Pelo menos 4 filas com consumidores diferentes: InfluxDB, inferência,
  WebSocket e comandos para o dispositivo.
- Filas para jobs demorados (geração e treino).
- DLQ com a mensagem preservada.
- JSON com formato único (identificador, instante, tipo, dispositivo,
  conteúdo).
- Um usuário do RabbitMQ por serviço, sem guest.
- Página Mensageria ao vivo (filas, taxas, consumidores, últimas mensagens,
  DLQ), via API de gerenciamento consultada pelo backend.
- Demonstrar o consumidor parado: a fila cresce e depois esvazia.

## Dados sintéticos

- Configurável: número de equipamentos e sensores por tipo, dias, % que
  falha, modos de falha, ruído, % faltantes, % outliers, semente.
- Degradação progressiva com ruído e sobreposição; ciclo diário; rótulos de
  verdade só no treino; mínimo de 1 milhão de leituras; numpy em blocos; teto
  máximo; job em segundo plano por fila com progresso; amostra num bucket
  separado do InfluxDB.

## IA

- Features por um único código no treino e na inferência; janelas só do
  passado; divisão por equipamento.
- Métricas MAE, RMSE e R², previsto × real, importância dos atributos,
  comparação com base simples (o modelo só vale se vencer).
- Treino disparado pela interface, em segundo plano; modelo novo em uso sem
  reiniciar, mostrando a versão.
- Inferência em tempo real sobre o RabbitMQ, publicando previsões e alertas.
- Alertas com histerese.
- Página Insights por equipamento; os mesmos dados colorem a cena 3D.

## Assistente

- LLM local no Compose, sem chave e sem nuvem, modelo pequeno em CPU.
- Responde sobre estado atual, previsões, métricas e arquitetura.
- Resumo dos dados vai pronto no prompt; o LLM nunca acessa os bancos;
  ferramentas, se houver, só leitura e em lista fixa.
- Streaming, aviso de "carregando o modelo", Markdown sem HTML e sem imagens
  remotas, limite de perguntas por minuto, auditoria.

## Segurança, Compose e GitHub

- `docker compose up` sobe tudo, com healthchecks e ordem de subida.
- JWT com papéis visualizador, operador e administrador; bcrypt e limite de
  tentativas; segredos fora do Git, gerados por script, sem admin/admin.
- Mosquitto sem anônimo e com permissão por tópico; RabbitMQ com usuário por
  serviço; WebSocket sem JWT na URL (ticket curto de uso único).
- Containers sem root; só a porta do frontend publicada; interfaces do
  InfluxDB, RabbitMQ e PostgreSQL só em 127.0.0.1, com links numa página.
- Auditoria no PostgreSQL com logins, comandos e jobs.
- GitHub com commits de todos os integrantes e README com descrição,
  diagrama, como subir, usuários de demonstração (sem senhas) e como rodar a
  demonstração.

## Avaliação (10,0 pontos)

| Critério | Pontos |
| --- | --- |
| Evolução e qualidade geral (segurança mínima, GitHub com README) | 1,0 |
| Sensores, atuadores e MQTT + Mosquitto | 1,0 |
| Regra automática e controle pela Web | 1,0 |
| RabbitMQ (exchange, filas, consumidores, DLQ, página Mensageria) | 1,0 |
| PostgreSQL e InfluxDB | 1,0 |
| WebSocket, dashboard, gráficos e histórico | 1,0 |
| Interface 3D | 1,0 |
| Dados sintéticos e modelos de regressão | 1,0 |
| Insights de IA e LLM local | 1,0 |
| Docker Compose e apresentação completa | 1,0 |

A pontuação depende do funcionamento durante a apresentação.
