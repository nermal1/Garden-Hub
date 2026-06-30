#include <esp_now.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Make sure you have the ArduinoJson library installed!

// --- CONFIGURATION ---
const char* ssid = "BSchance";
const char* password = "goldiegem66";

// Your exact brand new Render cloud URL
const char* serverName = "https://garden-data.onrender.com/api/data";

// --- DATA STRUCTURE ---
// Must match the exact structure the Garden Node is sending
typedef struct struct_message {
    int moisture;
    float temperature;
    float humidity;
    float pressure;
} struct_message;

struct_message incomingReadings;

// --- ESP-NOW CALLBACK ---
// This triggers automatically whenever the outdoor Garden Node transmits data
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  memcpy(&incomingReadings, incomingData, sizeof(incomingReadings));
  Serial.println("\n--- New Data Received via ESP-NOW ---");
  Serial.print("Raw Moisture: "); Serial.println(incomingReadings.moisture);
  Serial.print("Temperature: "); Serial.println(incomingReadings.temperature);
  Serial.print("Humidity: "); Serial.println(incomingReadings.humidity);
  Serial.print("Pressure: "); Serial.println(incomingReadings.pressure);

  // If we are connected to Wi-Fi, push this data right up to Render
  if(WiFi.status() == WL_CONNECTED){
    HTTPClient http;
    
    // Initialize secure connection to Render
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");
    
    // Measure our current Wi-Fi strength (RSSI) right before sending
    int currentRssi = WiFi.RSSI();
    
    // Construct the clean JSON payload for FastAPI
    String jsonPayload = "{\"moisture\":\"" + String(incomingReadings.moisture) + 
                         "\",\"temperature\":\"" + String(incomingReadings.temperature) + 
                         "\",\"humidity\":\"" + String(incomingReadings.humidity) + 
                         "\",\"pressure\":\"" + String(incomingReadings.pressure) + 
                         "\",\"rssi\":\"" + String(currentRssi) + "\"}";
                         
    Serial.print("Sending payload to Render: ");
    Serial.println(jsonPayload);
    
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode > 0) {
      Serial.print("Cloud Upload Success! Response code: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Cloud Upload Error: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  } else {
    Serial.println("Cannot upload: Wi-Fi Disconnected!");
  }
}

void setup() {
  Serial.begin(115200);
  
  // 1. Start Wi-Fi in Station Mode
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to home network!");
  Serial.print("Hub IP Address: ");
  Serial.println(WiFi.localIP());

  // 2. Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // 3. Register the incoming data callback function
  esp_now_register_recv_cb(esp_now_recv_cb_t(OnDataRecv));
}
 
void loop() {
  // Keep loop empty! ESP-NOW operates entirely on background interrupts.
}