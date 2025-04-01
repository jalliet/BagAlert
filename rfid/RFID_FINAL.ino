#include <WiFi.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 22
#define SS_PIN  21

MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);

String lastUID = "No UID yet";

void handleRoot() {
  server.send(200, "text/plain", lastUID);
}

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  // Create ESP32 Wi-Fi Access Point
  WiFi.softAP("ESP32-RFID", "12345678");
  Serial.println("ESP32 Access Point Started");
  Serial.print("IP address: ");
  Serial.println(WiFi.softAPIP());  // Usually 192.168.4.1

  // Start web server
  server.on("/", handleRoot);
  server.begin();
  Serial.println("Web server started.");
}

void loop() {
  server.handleClient();

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

  lastUID = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) lastUID += "0";
    lastUID += String(rfid.uid.uidByte[i], HEX);
  }
  Serial.println("Scanned UID: " + lastUID);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(1000);
}
