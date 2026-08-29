## Objetivo do trabalho

O trabalho consiste no desenvolvimento da primeira etapa de uma aplicação Web integrada com Internet das Coisas (IoT).

Nesta primeira etapa, o grupo deverá criar a base funcional do projeto, permitindo que um dispositivo IoT real ou simulado envie dados para a aplicação, que esses dados sejam armazenados e posteriormente apresentados em um dashboard Web.

O projeto deverá resolver um problema real utilizando Internet das Coisas.

Os sensores poderão ser implementados utilizando dispositivos físicos ou simulados, como ESP32 no Wokwi.

O projeto desenvolvido neste bimestre será obrigatoriamente continuado e ampliado no 2º bimestre.

## Stack obrigatória

Todas as tecnologias abaixo deverão obrigatoriamente fazer parte do projeto:

| Camada | Tecnologia | Finalidade |
| --- | --- | --- |
| Frontend | Vue.js 3 + TypeScript + Vite | Desenvolvimento da interface Web |
| Visualização | Chart.js ou Apache ECharts | Gráficos e indicadores |
| Backend | Python | Processamento e integração dos dados IoT |
| IoT | MQTT + Mosquitto | Comunicação entre os dispositivos e a aplicação |
| Dispositivo | ESP32 físico ou simulado no Wokwi | Geração dos dados IoT |
| Banco de Séries Temporais | InfluxDB | Armazenamento das leituras dos sensores |
| Versionamento | Git + GitHub | Controle de versão do projeto |

Não será permitido substituir Vue.js por React ou utilizar Node.js como backend.

## Requisitos mínimos do 1º Bimestre

A aplicação deverá possuir obrigatoriamente:

- um problema real claramente definido;
- interface Web utilizando Vue.js 3;
- utilização de TypeScript;
- projeto configurado com Vite;
- pelo menos 1 sensor IoT;
- dispositivo físico ou simulado utilizando Wokwi;
- comunicação utilizando MQTT;
- utilização do Mosquitto como Broker MQTT;
- backend desenvolvido em Python;
- armazenamento das leituras no InfluxDB;
- consulta ao histórico dos dados coletados;
- pelo menos um gráfico ou indicador apresentando os dados;
- código versionado em um repositório no GitHub.

A aplicação deverá estar funcional, com o fluxo mínimo:

```
Sensor → MQTT → Mosquitto → Python → InfluxDB → Aplicação Web
```

## Exemplos de projetos

Os exemplos abaixo servem apenas como referência. O grupo poderá propor outra aplicação IoT, desde que utilize corretamente todas as tecnologias obrigatórias.

| Projeto | Dados que podem ser monitorados | Exemplos de funcionalidades |
| --- | --- | --- |
| Smart Campus | Temperatura, umidade, luminosidade, presença e qualidade do ar | Monitoramento de salas, histórico e gráficos |
| Monitoramento Industrial | Temperatura, vibração, corrente elétrica e consumo de energia | Monitoramento de máquinas e identificação de situações de atenção |
| Smart Agriculture | Umidade do solo, temperatura, umidade do ar e luminosidade | Monitoramento das condições de cultivo e histórico das medições |
| Smart Home | Temperatura, luminosidade e presença | Monitoramento de ambientes residenciais |
| Monitoramento Ambiental | Temperatura, umidade, pressão e qualidade do ar | Dashboard de acompanhamento ambiental |

## Avaliação – 10,0 pontos

| Critério | Pontuação |
| --- | --- |
| Definição do problema e proposta da solução IoT | 1,0 ponto |
| Frontend Vue.js 3 + TypeScript + Vite funcionando corretamente | 2,0 pontos |
| Dispositivo IoT físico ou simulado no Wokwi | 1,5 pontos |
| Comunicação MQTT + Mosquitto funcionando corretamente | 2,0 pontos |
| Backend em Python recebendo e processando os dados | 1,0 ponto |
| Persistência correta dos dados no InfluxDB | 1,5 pontos |
| Dashboard com gráfico ou indicador dos dados coletados | 1,0 ponto |
| **Total** | **10,0 pontos** |

A pontuação de cada item dependerá do seu correto funcionamento durante a avaliação.

A simples inclusão da tecnologia no código, sem demonstrar seu funcionamento, não garante a pontuação correspondente.

## Importante

Esta entrega representa apenas a primeira etapa do projeto.

O mesmo projeto deverá ser continuado no 2º bimestre, quando serão adicionados novos sensores, atuadores, comunicação bidirecional, banco de dados relacional, Docker e outras melhorias.
