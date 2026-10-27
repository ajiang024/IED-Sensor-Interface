#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// Verify the flowmeter signal is safe for a 3.3 V ESP32 input before wiring.
volatile uint32_t pulses = 0;
portMUX_TYPE pulseMux = portMUX_INITIALIZER_UNLOCKED;
String bootId;
uint32_t sequence = 0;
unsigned long lastSend = 0, lastReconnect = 0;
void IRAM_ATTR pulse() {
  portENTER_CRITICAL_ISR(&pulseMux);
  pulses++;
  portEXIT_CRITICAL_ISR(&pulseMux);
}
void setup() {
  Serial.begin(115200);
  pinMode(FLOW_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), pulse, FALLING);
  bootId = String(esp_random(), HEX) + String(esp_random(), HEX);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastReconnect >= 10000) {
      lastReconnect = millis();
      WiFi.reconnect();
    }
    return;
  }
  if (millis() - lastSend < 2000) return;
  lastSend = millis();
  portENTER_CRITICAL(&pulseMux);
  uint32_t count = pulses;
  portEXIT_CRITICAL(&pulseMux);
  JsonDocument doc;
  doc["device_id"] = WiFi.macAddress();
  doc["boot_id"] = bootId;
  doc["sequence"] = sequence++;
  doc["cumulative_pulses"] = count;
  doc["pulses_per_liter"] = PULSES_PER_LITER;
  String payload;
  serializeJson(doc, payload);
  HTTPClient http;
  http.setTimeout(3000);
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.POST(payload);
  Serial.printf("Upload: %d, pulses: %lu\n", code, (unsigned long)count);
  if (code > 0 && code != 200) Serial.println(http.getString());
  http.end();
}
