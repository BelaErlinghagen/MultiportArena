#include <CapacitiveSensor.h>

// ------------------- CONFIGURATION -------------------
const int NUM_RELAYS = 8;
const int NUM_SENSORS = 2;  // ← Change this to add more sensors
const int NUM_LEDS = 1;
int RELAY_TO_REWARD[NUM_RELAYS] = {0};  // 0 = unassigned, 1 = reward1, 2 = reward2
int pwmReward1 = 255;
int pwmReward2 = 255;

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
      
      // Reset relays
      for (int i = 0; i < NUM_RELAYS; i++) {
        relayActive[i] = false;
        digitalWrite(RELAY_PINS[i], HIGH);  // OFF (active LOW)
      }

      // Turn off all LEDs
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
      while (!Serial.available()) {}
      int ledIndex = Serial.read() - '1';  // '1' → index 0
      if (ledIndex >= 0 && ledIndex < NUM_LEDS) {
        digitalWrite(LED_PINS[ledIndex], HIGH);
      }
    }

    else if (c == 'l') {
      while (!Serial.available()) {}
      int ledIndex = Serial.read() - '1';
      if (ledIndex >= 0 && ledIndex < NUM_LEDS) {
        digitalWrite(LED_PINS[ledIndex], LOW);
      }
    }

    else if (c == 'P') {
      while (Serial.available() < 2) {}
      char rewardChannel = Serial.read();       // '1' or '2'
      int pwmVal = Serial.read();               // 0–255
      pwmVal = constrain(pwmVal, 0, 255);

      if (rewardChannel == '1') {
        pwmReward1 = pwmVal;
        Serial.print("PWM1 set to ");
        Serial.println(pwmReward1);
      }
      else if (rewardChannel == '2') {
        pwmReward2 = pwmVal;
        Serial.print("PWM2 set to ");
        Serial.println(pwmReward2);
      }
    }

    else if (c == 'M') {
      while (Serial.available() < 2) {}
      int relayIndex = Serial.read() - '1';     // 1-based to 0-based
      int rewardGroup = Serial.read() - '0';    // '1' or '2'

      if (relayIndex >= 0 && relayIndex < NUM_RELAYS && (rewardGroup == 1 || rewardGroup == 2)) {
        RELAY_TO_REWARD[relayIndex] = rewardGroup;
        Serial.print("Mapped Relay ");
        Serial.print(relayIndex + 1);
        Serial.print(" to Reward ");
        Serial.println(rewardGroup);
      }
    }
  }

  // Relay activation logic based on reward group
  if (relayControlEnabled) {
    long readings[NUM_SENSORS];
    for (int i = 0; i < NUM_SENSORS; i++) {
      readings[i] = sensors[i]->capacitiveSensor(80);
    }

    for (int i = 0; i < NUM_RELAYS; i++) {
      if (relayActive[i]) {
        int rewardGroup = RELAY_TO_REWARD[i];
        if (rewardGroup == 1) {
          digitalWrite(RELAY_PINS[i], pwmReward1 > 0 ? LOW : HIGH);
        }
        else if (rewardGroup == 2) {
          digitalWrite(RELAY_PINS[i], pwmReward2 > 0 ? LOW : HIGH);
        }
        else {
          digitalWrite(RELAY_PINS[i], HIGH);  // Default: OFF
        }
      }
    }
  }
}
