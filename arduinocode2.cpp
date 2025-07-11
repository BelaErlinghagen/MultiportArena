#include <CapacitiveSensor.h>

// ------------------- CONFIGURATION -------------------
const int NUM_RELAYS = 8;
const int NUM_SENSORS = 1;  // ← Change this to add more sensors
const int LED_PIN = 9;

// Define sensor pin pairs here
int sendPins[NUM_SENSORS] = {2};
int receivePins[NUM_SENSORS] = {3};

// Relay control pins
const int RELAY_PINS[NUM_RELAYS] = {
  26, 28, 23, 25, 26, 27, 24, 29
};

// Create sensor objects
CapacitiveSensor* sensors[NUM_SENSORS];

// ------------------- STATE -------------------
bool relayControlEnabled = false;
bool relayActive[NUM_RELAYS] = { false };

void setup() {
  Serial.begin(9600);

  // Initialize relay pins
  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH);  // OFF (active LOW)
  }

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize sensor objects
  for (int i = 0; i < NUM_SENSORS; i++) {
    sensors[i] = new CapacitiveSensor(sendPins[i], receivePins[i]);
  }
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();

    if (c == 'r') {
      relayControlEnabled = true;
      digitalWrite(LED_PIN, HIGH);
    } else if (c == 'i') {
      relayControlEnabled = false;
      digitalWrite(LED_PIN, LOW);
      for (int i = 0; i < NUM_RELAYS; i++) {
        relayActive[i] = false;
        digitalWrite(RELAY_PINS[i], HIGH);  // OFF
      }
    } else if (c >= '1' && c <= '8') {
      int relayIndex = c - '1';
      relayActive[relayIndex] = true;
    } else if (c == 's') {
      // On-demand sensor reading
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
  }

  // Relay control logic (optional to expand)
  if (relayControlEnabled) {
    long readings[NUM_SENSORS];
    for (int i = 0; i < NUM_SENSORS; i++) {
      readings[i] = sensors[i]->capacitiveSensor(80);
    }

    if (relayActive[0]) digitalWrite(RELAY_PINS[0], readings[0] > 2500 ? LOW : HIGH);
    if (relayActive[1]) digitalWrite(RELAY_PINS[1], readings[1] > 2500 ? LOW : HIGH);
    // Add logic here for additional relays/sensors as needed
  }
}