#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  
  // Turn on the Wi-Fi hardware
  WiFi.mode(WIFI_STA);
  WiFi.begin(); 
  
  // Wait 1 second for the radio to fully boot
  delay(1000); 

  Serial.println();
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
}

void loop() {}