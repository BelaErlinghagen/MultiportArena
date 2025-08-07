#include <CapacitiveSensor.h>

// ------------------- CONFIGURATION -------------------
const int NUM_RELAYS = 8;
const int NUM_SENSORS = 2;  // ← Change this to add more sensors
const int NUM_LEDS = 1;


// Define sensor pin pairs here
int sendPins[NUM_SENSORS] = {2, 4};
int receivePins[NUM_SENSORS] = {3, 7};

// Relay control pins
const int RELAY_PINS[NUM_RELAYS] = {
  23, 22, 24, 25, 26, 27, 28, 29
};

// Define LED pins here: const int NUM_LEDS = 8;
const int LED_PINS[NUM_LEDS] = {10};

// Create sensor objects
CapacitiveSensor* sensors[NUM_SENSORS];

// ------------------- STATE -------------------
bool relayControlEnabled = false;
bool relayActive[NUM_RELAYS] = { false };

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH); // OFF
  }

  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    digitalWrite(LED_PINS[i], LOW);  // default OFF
  } 

  for (int i = 0; i < NUM_SENSORS; i++) {
    sensors[i] = new CapacitiveSensor(sendPins[i], receivePins[i]);
  }

  // Send handshake
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();

    if (c == 'r') {
      relayControlEnabled = true;
    } 
    
    else if (c == 'i') {
      relayControlEnabled = false;
      for (int i = 0; i < NUM_RELAYS; i++) {
        relayActive[i] = false;
        digitalWrite(RELAY_PINS[i], HIGH);  // OFF (active LOW)
      }

      // Turn off all LEDs during intertrial (optional)
      for (int i = 0; i < NUM_LEDS; i++) {
        digitalWrite(LED_PINS[i], LOW);
      }
    }

    else if (c >= '1' && c <= '8') {
      int relayIndex = c - '1';
      if (relayIndex >= 0 && relayIndex < NUM_RELAYS) {
        relayActive[relayIndex] = true;
      }
    }

    else if (c == 's') {
      // Sensor read on request
      unsigned long timestamp = millis();
      Serial.print("ts:");
      Serial.print(timestamp);
      Serial.print(" cs:");
      for (int i = 0; i < NUM_SENSORS; i++) {
        long reading = sensors[i]->capacitiveSensor(80);
        Serial.print(reading);
        if (i < NUM_SENSORS - 1) Serial.print(",");
      }
      Serial.println();
    }

    else if (c == 'L') {
      // Turn ON individual LED
      while (!Serial.available()) {}
      int ledIndex = Serial.read() - '1';  // '1' → 0
      if (ledIndex >= 0 && ledIndex < NUM_LEDS) {
        digitalWrite(LED_PINS[ledIndex], HIGH);
      }
    }

    else if (c == 'l') {
      // Turn OFF individual LED
      while (!Serial.available()) {}
      int ledIndex = Serial.read() - '1';  // '1' → 0
      if (ledIndex >= 0 && ledIndex < NUM_LEDS) {
        digitalWrite(LED_PINS[ledIndex], LOW);
      }
    }
  }

  // Relay control logic (placeholder)
  if (relayControlEnabled) {
    long readings[NUM_SENSORS];
    for (int i = 0; i < NUM_SENSORS; i++) {
      readings[i] = sensors[i]->capacitiveSensor(80);
    }

    // Example: activate relays based on sensor 0
    if (relayActive[0]) digitalWrite(RELAY_PINS[0], readings[0] > 2500 ? LOW : HIGH);
    if (relayActive[1]) digitalWrite(RELAY_PINS[1], readings[0] > 2500 ? LOW : HIGH);
    // Add more relay logic if needed
  }
}