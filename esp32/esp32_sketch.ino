/*
 * SolarSync AI - Commercial ESP32 IoT Node Controller
 * 
 * Hardware Wiring Map:
 * - Voltage Sensor (0-25V Divider): Signal Pin -> GPIO 35 (ADC1_CH7)
 * - ACS712 Current Sensor (20A Mod): Signal Pin -> GPIO 34 (ADC1_CH6)
 * - 5V SPDT Relay Control Module: Signal Pin -> GPIO 26
 * - DC Water Pump: Connected in-line with Relay COM/NO contacts.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// 1. Wi-Fi Credentials
const char* ssid = "realme P1 5G";
const char* password = "Anand123";

// 2. Server Gateway URL (Laptop Hotspot IP: 10.250.93.242 on Port 5000)
const char* serverUrl = "http://10.250.93.242:5000/api/esp32/data";

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
double cumulativeRuntimeSeconds = 0.0;
double cumulativeEnergyKWh = 0.0;

// ACS712 baseline offset (auto-calibrated on boot)
double zeroCurrentVoltage = 2.50;

// Calibration factors (synced dynamically from server)
double voltageCalibrationFactor = 1.0;
double currentSensorOffset = 0.0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n--- SolarSync AI ESP32 Initializing ---");
  Serial.print("Device ID: ");
  Serial.println(deviceId);
  
  // Initialize Relay pin and turn OFF immediately on boot
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_OFF); // HIGH = Relay is OFF (Open)
  
  // Set ADC attenuation to 11dB (allows full scale 0 - 3.3V ADC reading on ESP32)
  analogSetPinAttenuation(VOLTAGE_PIN, ADC_11db);
  analogSetPinAttenuation(CURRENT_PIN, ADC_11db);
  
  // Auto-calibrate ACS712 zero baseline before starting pump
  calibrateCurrentSensor();
  
  // Clean Wi-Fi state & set station mode
  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  
  Serial.print("Connecting to Wi-Fi hotspot: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[SUCCESS] Wi-Fi Connected!");
    Serial.print("ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Target Server: ");
    Serial.println(serverUrl);
  } else {
    Serial.println("\n[ERROR] Could not connect to Wi-Fi hotspot.");
    Serial.println("-> Please check: 1) Phone Hotspot band MUST be 2.4 GHz.");
    Serial.println("-> Please check: 2) Hotspot Security is WPA2-Personal.");
    Serial.println("-> Please check: 3) Password 'Anand123' and SSID 'realme P1 5G' match exactly.");
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
  // If disconnected, attempt auto-reconnect
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Reconnecting to Wi-Fi...");
    WiFi.reconnect();
    delay(3000);
    return;
  }
  
  unsigned long now = millis();
  
  // Trigger telemetry send every 1000ms (1 second)
  if (now - lastTelemetryTime >= 1000) {
    double timeStepSeconds = (now - lastTelemetryTime) / 1000.0;
    lastTelemetryTime = now;
    
    // 1. Read sensors with multi-sampling
    double voltage = readVoltage();
    double current = readCurrent();
    
    // 2. Determine Pump Status:
    // When current is 1.0 Amp or more, status is RUNNING (1)
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
    
    // 5. Transmit telemetry to Cloud / Flask Server
    transmitTelemetry(voltage, current, power);
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
  // 50 samples averaging for clean ACS712 reading
  long sumADC = 0;
  for (int i = 0; i < 50; i++) {
    sumADC += analogRead(CURRENT_PIN);
    delayMicroseconds(150);
  }
  double avgADC = sumADC / 50.0;
  double sensorVolts = (avgADC / 4095.0) * 3.3;
  
  // ACS712-20A sensitivity: 100mV/A (0.100V per Ampere)
  // Use abs() to handle any wire polarity in the ACS712 screw terminals
  double voltageDiff = abs(sensorVolts - zeroCurrentVoltage);
  double measuredCurrent = (voltageDiff / 0.100) + currentSensorOffset;
  
  // Filter out tiny noise jitter
  if (measuredCurrent < 0.10) {
    measuredCurrent = 0.0;
  }
  return measuredCurrent;
}

void transmitTelemetry(double voltage, double current, double power) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000); // 3s timeout
  
  // Build JSON Document with Device Authentication
  StaticJsonDocument<256> doc;
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
    StaticJsonDocument<256> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);
    
    if (!error) {
      targetStatus = resDoc["target_status"];
      if (resDoc.containsKey("voltage_calibration")) {
        voltageCalibrationFactor = resDoc["voltage_calibration"];
      }
      if (resDoc.containsKey("current_offset")) {
        currentSensorOffset = resDoc["current_offset"];
      }
      
      // Update physical relay state based on server command
      digitalWrite(RELAY_PIN, (targetStatus == 1) ? RELAY_ON : RELAY_OFF);
    }
    Serial.printf("[%s | HTTP %d] V: %.1fV | I: %.2fA | P: %.1fW | Pump: %s\n", 
                  deviceId, httpResponseCode, voltage, current, power, pumpStatus == 1 ? "ON (RUNNING)" : "OFF (STANDBY)");
  } else {
    Serial.printf("[HTTP FAIL] Code: %d (Check server URL: %s)\n", httpResponseCode, serverUrl);
  }
  
  http.end();
}
