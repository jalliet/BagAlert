#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "YourHotspotSSID";
const char* password = "YourHotspotPassword";
const char* mqtt_server = "192.168.1.100";  // Replace with Raspberry Pi's IP

WiFiClient espClient;
PubSubClient client(espClient);

// Define RFID reader's RX/TX pins (modify based on your module)
#define RX_PIN 16  
#define TX_PIN 17

void setup_wifi() {
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected!");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32_RFID")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_server, 1883);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  if (Serial.available()) {  
    String rfidTag = Serial.readStringUntil('\n');
    rfidTag.trim();
    
    if (rfidTag.length() > 0) {
      Serial.print("RFID Tag: ");
      Serial.println(rfidTag);
      client.publish("rfid/data", rfidTag.c_str());
    }
  }
}
