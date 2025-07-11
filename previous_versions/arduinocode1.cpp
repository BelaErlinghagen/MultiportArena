#include <CapacitiveSensor.h>

// ------------------- CONFIGURATION -------------------
const int NUM_RELAYS = 8;
const int LED_PIN = 10;

// Capacitive sensors
CapacitiveSensor cs_2_3 = CapacitiveSensor(2, 3);  // For relay 1
CapacitiveSensor cs_4_7 = CapacitiveSensor(4, 7);  // For relay 2

const int RELAY_PINS[NUM_RELAYS] = {
  23, 22, 24, 25, 26, 27, 28, 29
};

// ------------------- STATE -------------------
bool relayControlEnabled = false;
bool relayActive[NUM_RELAYS] = { false };

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH);  // OFF (active LOW)
  }

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  // Sensor readings
  long cs1 = cs_2_3.capacitiveSensor(80);
  long cs2 = cs_4_7.capacitiveSensor(80);

  Serial.println(cs1);
  Serial.println(cs2);
  delay(10);
  // Serial input handling
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
      int relayIndex = c - '1';  // Convert char to int (0-based)
      // Toggle the relay ON (true) if it was OFF, and vice versa
      relayActive[relayIndex] = true;
    }
  }

  // Relay logic for sensors
  if (relayControlEnabled) {
    if (relayActive[0]) {
      digitalWrite(RELAY_PINS[0], cs1 > 2500 ? LOW : HIGH);
    }
    if (relayActive[1]) {
      digitalWrite(RELAY_PINS[1], cs2 > 2500 ? LOW : HIGH);
    }
  }
}