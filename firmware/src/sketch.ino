#include <WiFi.h>
#include <PubSubClient.h>

// ---------- rede do simulador ----------
const char* WIFI_SSID  = "Wokwi-GUEST";
const char* WIFI_SENHA = "";
const int   WIFI_CANAL = 6;  // sem isto o Wokwi varre todos os canais e demora

// ---------- broker MQTT ----------
// TROQUE ESTAS DUAS LINHAS a cada tunel novo do pinggy.
// Host SEM "tcp://" e SEM a porta colada. Porta e numero, sem aspas.
const char* MQTT_HOST  = "dcetj-2804-7f0-b769-ec4f-e124-5e80-8765-2795.run.pinggy-free.link";
const int   MQTT_PORTA = 38881;

// ---------- identidade deste dispositivo ----------
// Precisa existir na coluna "codigo" da tabela dispositivos.
const char* CODIGO = "ESP32-COZINHA-01";
char topico[64];  // montado no setup a partir do CODIGO

// ---------- pinos ----------
const int pinoSensor = 34;  // ADC1: continua funcionando com o WiFi ligado
const int pinoLed    = 2;
const int pinoBuzzer = 4;

// ---------- limiar local ----------
// Faz o alarme fisico tocar mesmo sem rede. O backend tem o seu proprio.
const int limiteGas = 1500;  // escala 0 a 4095

// ---------- os quatro ritmos, em milissegundos ----------
const unsigned long INTERVALO_PISCA      = 150;
const unsigned long INTERVALO_SERIAL     = 500;
const unsigned long INTERVALO_PUBLICACAO = 3000;
const unsigned long INTERVALO_RECONEXAO  = 5000;

// ---------- memoria de cada ritmo ----------
unsigned long ultimoPisca      = 0;
unsigned long ultimoSerial     = 0;
unsigned long ultimaPublicacao = 0;
unsigned long ultimaReconexao  = 0;

bool ledAceso = false;

// O PubSubClient nao fala TCP sozinho: precisa de um transporte por baixo.
// E essa separacao que permite trocar por TLS depois sem mudar o resto.
WiFiClient rede;
PubSubClient mqtt(rede);

void conectarWiFi() {
  Serial.print("WiFi: conectando");
  WiFi.begin(WIFI_SSID, WIFI_SENHA, WIFI_CANAL);

  // Travar AQUI e permitido: o setup roda uma vez e nada mais esta rodando.
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }

  Serial.print(" ok, IP ");
  Serial.println(WiFi.localIP());
}

// Uma unica tentativa. Quem decide QUANDO tentar e o loop().
void tentarConectarMqtt() {
  Serial.print("MQTT: conectando em ");
  Serial.print(MQTT_HOST);
  Serial.print(":");
  Serial.print(MQTT_PORTA);

  // O client ID precisa ser unico no broker, senao um cliente derruba o outro.
  if (mqtt.connect(CODIGO)) {
    Serial.println(" -> conectado");
  } else {
    Serial.print(" -> falhou, estado=");
    Serial.println(mqtt.state());
  }
}

void setup() {
  pinMode(pinoLed, OUTPUT);
  Serial.begin(115200);
  ledcAttachChannel(pinoBuzzer, 1000, 8, 0);

  digitalWrite(pinoLed, LOW);
  ledcWriteTone(pinoBuzzer, 0);

  // Topico montado uma vez, a partir do CODIGO: um lugar so pra mudar.
  snprintf(topico, sizeof(topico), "gasguard/%s/leitura", CODIGO);
  Serial.print("Topico: ");
  Serial.println(topico);

  conectarWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORTA);
}

void loop() {
  unsigned long agora = millis();

  // ---------- reconexao sem travar ----------
  // O exemplo padrao do PubSubClient usa while() aqui e prende o programa.
  // Isso mataria o alarme justo quando a rede cai. Usamos o mesmo padrao
  // de temporizador do resto do sketch.
  if (!mqtt.connected() && agora - ultimaReconexao >= INTERVALO_RECONEXAO) {
    ultimaReconexao = agora;
    tentarConectarMqtt();
  }

  // Em TODA volta: e ele que processa keepalive e mantem a sessao viva.
  // Era exatamente isto que os delay() antigos sufocavam.
  mqtt.loop();

  // Sem timer: ler e decidir toda volta, pro alarme reagir na hora.
  int gas = analogRead(pinoSensor);
  bool emAlarme = (gas > limiteGas);

  // ---------- ritmo 1: piscar enquanto houver alarme ----------
  if (emAlarme) {
    if (agora - ultimoPisca >= INTERVALO_PISCA) {
      ultimoPisca = agora;
      ledAceso = !ledAceso;
      digitalWrite(pinoLed, ledAceso ? HIGH : LOW);
      ledcWriteTone(pinoBuzzer, ledAceso ? 1000 : 0);
    }
  } else {
    if (ledAceso) {
      ledAceso = false;
      digitalWrite(pinoLed, LOW);
      ledcWriteTone(pinoBuzzer, 0);
    }
  }

  // ---------- ritmo 2: imprimir no Serial ----------
  if (agora - ultimoSerial >= INTERVALO_SERIAL) {
    ultimoSerial = agora;
    Serial.print("Nivel do Gas: ");
    Serial.print(gas);
    Serial.println(emAlarme ? "  [ALARME]" : "");
  }

  // ---------- ritmo 3: publicar ----------
  if (agora - ultimaPublicacao >= INTERVALO_PUBLICACAO) {
    ultimaPublicacao = agora;

    if (mqtt.connected()) {
      // snprintf em buffer fixo: concatenar String fragmenta a heap
      // e o dispositivo trava depois de horas rodando.
      char payload[64];
      snprintf(payload, sizeof(payload),
               "{\"codigo\":\"%s\",\"ppm\":%d}", CODIGO, gas);

      // publish devolve bool. Sem conferir, mensagem sumida vira
      // meia hora de investigacao.
      bool ok = mqtt.publish(topico, payload);

      Serial.print(ok ? ">> publicado: " : ">> FALHOU ao publicar: ");
      Serial.println(payload);
    } else {
      Serial.println(">> sem conexao MQTT, leitura descartada");
    }
  }
}
