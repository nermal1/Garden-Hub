#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// --- DEEP SLEEP CONFIGURATION ---
#define uS_TO_S_FACTOR 1000000ULL  /* Conversion factor for micro seconds to seconds */
#define TIME_TO_SLEEP  900        /* Time ESP32 will go to sleep (in seconds) -> 15 minutes */

// --- HARDWARE PINS ---
const int MOISTURE_PIN = 34;       /* Analog pin for soil moisture sensor */

// --- SENSOR CONFIGURATION ---
Adafruit_BME280 bme; 

// --- RECEIVER MAC ADDRESS ---
// Replace with your Garage Hub's exact MAC address
uint8_t broadcastAddress[] = {0x70, 0x4B, 0xCA, 0x6E, 0xAE, 0x84};

// --- DATA STRUCTURE ---
// Must match the Garage Hub exactly
typedef struct struct_message {
    int moisture;
    float temperature;
    float humidity;
    float pressure;
} struct_message;

struct_message myData;

esp_now_peer_info_t peerInfo;

// Callback function to verify if the data was successfully sent
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
  
  // CRITICAL: Once the transmission attempt is done, force deep sleep immediately
  Serial.println("Going to sleep now...");
  Serial.flush(); 
  esp_deep_sleep_start();
}
 
void setup() {
  Serial.begin(115200);
  
  // 1. Configure the wakeup timer
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
  Serial.println("Setup started. Woke up from sleep.");

  // 2. Initialize Sensors & Read Data
  pinMode(MOISTURE_PIN, INPUT);
  myData.moisture = analogRead(MOISTURE_PIN);
  
  if (bme.begin(0x76)) { // Initialize BME280
    myData.temperature = bme.readTemperature();
    myData.humidity = bme.readHumidity();
    myData.pressure = bme.readPressure() / 100.0F;
  } else {
    Serial.println("Could not find a valid BME280 sensor, sending defaults.");
    myData.temperature = 0.0;
    myData.humidity = 0.0;
    myData.pressure = 0.0;
  }

  // 3. Start Wi-Fi in Station Mode for ESP-NOW
  WiFi.mode(WIFI_STA);

  // 4. Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW. Force sleeping to protect battery.");
    esp_deep_sleep_start();
  }

  // 5. Register Send Callback
  esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);
  
  // 6. Register Peer
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer. Force sleeping.");
    esp_deep_sleep_start();
  }
  
  // 7. Fire off the data package
  Serial.println("Transmitting sensor data...");
  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  if (result == ESP_OK) {
    Serial.println("Packet handed off to radio.");
  } else {
    Serial.println("Error sending the data. Force sleeping.");
    esp_deep_sleep_start();
  }

  // Safety timeout: If for some crazy reason OnDataSent callback doesn't trigger,
  // ensure the board sleeps anyway after 5 seconds so it doesn't drain the battery.
  delay(5000);
  Serial.println("Safety timeout reached. Going to sleep.");
  esp_deep_sleep_start();
}
 
void loop() {
  // This remains completely empty!
}