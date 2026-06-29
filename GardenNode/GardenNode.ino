#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// I2C Pins for BME280
#define I2C_SDA 21
#define I2C_SCL 22
Adafruit_BME280 bme; 

// Analog Pin for Capacitive Moisture Sensor (ADC1 pin required when using Wi-Fi)
#define MOISTURE_PIN 34 

// Your specific Garage Hub MAC Address
uint8_t hubAddress[] = {0x70, 0x4B, 0xCA, 0x6E, 0xAE, 0x84};

// Structure to hold outgoing data
typedef struct struct_message {
  int moisture;
  float temperature;
  float humidity;
  float pressure;
} struct_message;

struct_message outgoingReadings;

esp_now_peer_info_t peerInfo;

void setup() {
  Serial.begin(115200);

  // Initialize the BME280 Sensor
  Wire.begin(I2C_SDA, I2C_SCL);
  // 0x76 is the I2C address when the SDO pin is tied to GND
  if (!bme.begin(0x76, &Wire)) { 
    Serial.println("Could not find a valid BME280 sensor, check wiring!");
    while (1);
  }

  // Set ESP32 as a Wi-Fi Station (Required for ESP-NOW)
  WiFi.mode(WIFI_STA);
  
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register the Hub as a peer
  memcpy(peerInfo.peer_addr, hubAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }
}

void loop() {
  // Read Sensors
  outgoingReadings.moisture = analogRead(MOISTURE_PIN);
  outgoingReadings.temperature = bme.readTemperature();
  outgoingReadings.humidity = bme.readHumidity();
  
  // Convert pressure from Pascals to hPa (millibars)
  outgoingReadings.pressure = bme.readPressure() / 100.0F; 

  // Send Data via ESP-NOW
  esp_err_t result = esp_now_send(hubAddress, (uint8_t *) &outgoingReadings, sizeof(outgoingReadings));
  
  if (result == ESP_OK) {
    Serial.println("Sent with success");
  } else {
    Serial.println("Error sending the data");
  }

  // Wait 5 seconds before next reading (for prototype testing)
  delay(5000); 
}