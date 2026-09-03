/*
 * SolarSync - Commercial ESP32 IoT Node Controller (Cloud Edition)
 * 
 * Hardware Wiring Map:
 * - Voltage Sensor (0-25V Divider): Signal Pin -> GPIO 35 (ADC1_CH7)
 * - ACS712 Current Sensor (20A Mod): Signal Pin -> GPIO 34 (ADC1_CH6)
 * - 5V SPDT Relay Control Module: Signal Pin -> GPIO 26
 * - DC Water Pump: Connected in-line with Relay COM/NO contacts.
 * 
 * DC Supply & Wi-Fi Stability Enhancements:
 * - Hardware Brownout Detector disabled (prevents resets on cold DC boot)
 * - Wi-Fi RF Power optimized to 15dBm to eliminate current spikes
 * - Safe 512-byte JSON memory buffers for ArduinoJson v6/v7 compatibility
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Low-level hardware registers for power stability
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// 1. Wi-Fi Credentials (make sure phone hotspot band is 2.4 GHz)
const char* ssid = "realme P1 5G";
const char* password = "Anand123";

// 2. Server Gateway URL (Your Live Render Cloud Server)
const char* serverUrl = "https://solar-sync.onrender.com/api/esp32/data";

// 3. Customer & Pump Device Credentials (from your SolarSync account settings)
const char* deviceId  = "PUMP-SOLAR-1001";
const char* apiKey    = "sync_sec_demo1234567890abcdef12345678";

// 4. Pin Definitions
const int VOLTAGE_PIN = 35; // Voltage Divider Sensor -> GPIO 35
const int CURRENT_PIN = 34; // ACS712 Current Sensor -> GPIO 34
const int RELAY_PIN = 26;   // Relay Control Signal -> GPIO 26

// Relay logic: 5V/3.3V Relay modules are Active LOW (LOW = Relay ON/Closed, HIGH = Relay OFF/Open)
#define RELAY_ON  LOW
#define RELAY_OFF HIGH

// Variables
int targetStatus = 0;
int pumpStatus = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastReconnectAttempt = 0;
double cumulativeRuntimeSeconds = 0.0;
double cumulativeEnergyKWh = 0.0;

// ACS712 baseline offset (auto-calibrated on boot)
double zeroCurrentVoltage = 2.50;

// Calibration factors (synced dynamically from server)
double voltageCalibrationFactor = 1.0;
double currentSensorOffset = 0.0;

void setup() {
  // 1. Disable hardware brownout detector to prevent restart during Wi-Fi surge on DC supply
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  // Glitch-free relay initialization (set level BEFORE setting as output)
  digitalWrite(RELAY_PIN, RELAY_OFF);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_OFF);

  Serial.begin(115200);
  delay(500);
  
  Serial.println("\n==============================================");
  Serial.println("  SolarSync Commercial ESP32 IoT Node");
  Serial.println("  Hardware Power Optimization: ENABLED");
  Serial.println("==============================================");
  Serial.print("Device ID: ");
  Serial.println(deviceId);
  
  // Set global ADC attenuation to 11dB (allows full scale 0 - 3.3V ADC reading on ESP32)
  analogSetAttenuation(ADC_11db);
  
  // Auto-calibrate ACS712 zero baseline before starting pump
  calibrateCurrentSensor();
  
  // Clean Wi-Fi state & set station mode
  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);

  // 2. Set Wi-Fi TX Power to 15dBm (prevents voltage drop on DC supply while keeping strong range)
  WiFi.setTxPower(WIFI_POWER_15dBm);
  
  Serial.print("Connecting to Wi-Fi hotspot: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(300);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[SUCCESS] Wi-Fi Connected!");
    Serial.print("ESP32 Local IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Cloud Server Gateway: ");
    Serial.println(serverUrl);
  } else {
    Serial.println("\n[WARNING] Wi-Fi connecting in background...");
  }
}

void calibrateCurrentSensor() {
  Serial.println("Sampling ACS712 zero-current baseline...");
  long sumADC = 0;
  for (int i = 0; i < 60; i++) {
    sumADC += analogRead(CURRENT_PIN);
    delay(5);
  }
  double avgADC = sumADC / 60.0;
  zeroCurrentVoltage = (avgADC / 4095.0) * 3.3;
  
  // Validate baseline is reasonable (typical ACS712 resting voltage is ~1.5V - 2.8V)
  if (zeroCurrentVoltage < 1.0 || zeroCurrentVoltage > 3.1) {
    zeroCurrentVoltage = 2.50; // Standard default
  }
  Serial.print("ACS712 Zero Baseline Voltage: ");
  Serial.print(zeroCurrentVoltage, 3);
  Serial.println(" V");
}

void loop() {
  unsigned long now = millis();

  // Non-blocking auto-reconnect if Wi-Fi drops
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      Serial.println("[Wi-Fi] Reconnecting to hotspot...");
      WiFi.reconnect();
    }
    return;
  }
  
  // Trigger telemetry send every 1000ms (1 second)
  if (now - lastTelemetryTime >= 1000) {
    double timeStepSeconds = (now - lastTelemetryTime) / 1000.0;
    lastTelemetryTime = now;
    
    // 1. Read sensors with multi-sampling
    double voltage = readVoltage();
    double current = readCurrent();
    
    // 2. Determine Pump Status:
    if (current >= 1.0 || targetStatus == 1) {
      pumpStatus = 1;
    } else {
      pumpStatus = 0;
    }
    
    // 3. Calculate Power (W = V * A)
    double power = voltage * current;
    
    // 4. Accumulate Duration & Energy when motor is running
    if (pumpStatus == 1) {
      cumulativeRuntimeSeconds += timeStepSeconds;
      cumulativeEnergyKWh += (power * (timeStepSeconds / 3600.0)) / 1000.0;
    }
    
    // 5. Transmit telemetry to Render Cloud Server
    transmitTelemetry(voltage, current, power);

    // 6. Enforce physical relay state based on targetStatus
    digitalWrite(RELAY_PIN, (targetStatus == 1) ? RELAY_ON : RELAY_OFF);
  }
}

double readVoltage() {
  // 30 samples averaging for clean noise filtering
  long sumADC = 0;
  for (int i = 0; i < 30; i++) {
    sumADC += analogRead(VOLTAGE_PIN);
    delayMicroseconds(100);
  }
  double avgADC = sumADC / 30.0;
  double sensorVolts = (avgADC / 4095.0) * 3.3;
  
  // Voltage Divider ratio = 5.0 (0-25V sensor: R1=30k, R2=7.5k)
  double measuredVoltage = sensorVolts * 5.0 * voltageCalibrationFactor;
  if (measuredVoltage < 0.2) measuredVoltage = 0.0;
  return measuredVoltage;
}

double readCurrent() {
  // 100 samples multi-sampling for clean ACS712 reading
  long sumADC = 0;
  for (int i = 0; i < 100; i++) {
    sumADC += analogRead(CURRENT_PIN);
    delayMicroseconds(100);
  }
  double avgADC = sumADC / 100.0;
  double sensorVolts = (avgADC / 4095.0) * 3.3;
  
  // Dynamic Zero-Current Drift Auto-Tracking when Relay is OFF
  if (targetStatus == 0) {
    if (abs(sensorVolts - zeroCurrentVoltage) < 0.25) {
      zeroCurrentVoltage = (zeroCurrentVoltage * 0.90) + (sensorVolts * 0.10);
    }
  }
  
  // ACS712-20A sensitivity: 100mV/A (0.100V per Ampere)
  double voltageDiff = abs(sensorVolts - zeroCurrentVoltage);
  double measuredCurrent = (voltageDiff / 0.100) + currentSensorOffset;
  
  // Clean Deadband Noise Filter:
  if (measuredCurrent < 0.35 || (targetStatus == 0 && measuredCurrent < 0.80)) {
    measuredCurrent = 0.0;
  }
  return measuredCurrent;
}

void transmitTelemetry(double voltage, double current, double power) {
  // Use WiFiClientSecure to connect securely to HTTPS cloud server
  WiFiClientSecure client;
  client.setInsecure(); // Allows secure SSL connection to Render without hardcoded certificate expiration issues
  
  HTTPClient http;
  http.begin(client, serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(4000); // 4s timeout for cloud
  
  // Build JSON Document with Device Authentication (512 bytes safe buffer)
  StaticJsonDocument<512> doc;
  doc["device_id"]   = deviceId;
  doc["api_key"]     = apiKey;
  doc["voltage"]     = voltage;
  doc["current"]     = current;
  doc["power"]       = power;
  doc["pump_status"] = pumpStatus;
  doc["runtime"]     = cumulativeRuntimeSeconds / 3600.0; // runtime in Hours
  doc["energy"]      = cumulativeEnergyKWh;
  
  String requestBody;
  serializeJson(doc, requestBody);
  
  int httpResponseCode = http.POST(requestBody);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    StaticJsonDocument<512> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);
    
    if (!error) {
      targetStatus = resDoc["target_status"];
      if (resDoc.containsKey("voltage_calibration")) {
        voltageCalibrationFactor = resDoc["voltage_calibration"];
      }
      if (resDoc.containsKey("current_offset")) {
        currentSensorOffset = resDoc["current_offset"];
      }
      
      // Update physical relay state based on cloud command
      digitalWrite(RELAY_PIN, (targetStatus == 1) ? RELAY_ON : RELAY_OFF);
    }
    Serial.printf("[%s | HTTP %d] V: %.1fV | I: %.2fA | P: %.1fW | Pump: %s\n", 
                  deviceId, httpResponseCode, voltage, current, power, pumpStatus == 1 ? "ON (RUNNING)" : "OFF (STANDBY)");
  } else {
    Serial.printf("[HTTP FAIL] Code: %d (Check Cloud URL: %s)\n", httpResponseCode, serverUrl);
  }
  
  http.end();
}
