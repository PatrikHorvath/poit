#include <OneWire.h>
#include <DallasTemperature.h>

const int PELTIER = 5;   
const int TEMP_PIN = 2;  

OneWire oneWire(TEMP_PIN);
DallasTemperature sensors(&oneWire);

int peltierPWM = 0;
int pwmPercent = 0;
bool isSystemActive = false;
bool debugActive = false;
unsigned long lastTempCheck = 0;

String inputBuffer = "";

float setpoint = 20.0;
float integralSum = 0.0;

const float Kp = 30;
const float Ki = 10; 
const float Ts = 2.0;

void setup() {
  pinMode(PELTIER, OUTPUT);
  analogWrite(PELTIER, 0);

  Serial.begin(115200);
  inputBuffer.reserve(32);
  
  sensors.begin();
  stopAll();
  
  Serial.println("ARDUINO_READY");
}

void loop() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    if (inChar == '\n' || inChar == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += inChar;
    }
  }

  if (debugActive) {
    analogWrite(PELTIER, peltierPWM);
  }

  if (isSystemActive && (millis() - lastTempCheck >= 2000)) {
    sensors.requestTemperatures();
    float celsius = sensors.getTempCByIndex(0);
    
    if (celsius != DEVICE_DISCONNECTED_C) {
      if (isSystemActive && !debugActive) {
        float error = celsius - setpoint;

        if (error > 0.5) {
          pwmPercent = 100;
          integralSum = 0.0;
        } else if (error < -0.5) {
          pwmPercent = 0;
          integralSum = 0.0;
        } else {
          integralSum += error * Ts;
          integralSum = constrain(integralSum, 0.0, 100.0 / Ki);

          float output = (Kp * error) + (Ki * integralSum);
          pwmPercent = constrain((int)output, 0, 100);
        }

        peltierPWM = map(pwmPercent, 0, 100, 0, 255);
        analogWrite(PELTIER, peltierPWM);
      }

      Serial.print("DATA:");
      Serial.print(celsius);
      Serial.print(",");
      Serial.print(pwmPercent);
      Serial.print(",");
      Serial.println(setpoint);
    }
    lastTempCheck = millis();
  }
}

void processCommand(String cmd) {
  cmd.trim();
  
  if (cmd == "ON") {
    isSystemActive = true;
  } 
  else if (cmd == "OFF") {
    isSystemActive = false;
    stopAll();
  } 
  else if (cmd.startsWith("DEBUG:")) {
    int val = cmd.substring(6).toInt();
    debugActive = (val == 1);
  }
  else if (cmd.startsWith("PWM:")) {
    pwmPercent = cmd.substring(4).toInt();
    pwmPercent = constrain(pwmPercent, 0, 100);
    peltierPWM = map(pwmPercent, 0, 100, 0, 255);
  }
  else if (cmd.startsWith("SP:")) {
    setpoint = cmd.substring(3).toFloat();
  }
}

void stopAll() {
  isSystemActive = false;
  peltierPWM = 0;
  pwmPercent = 0;
  integralSum = 0.0;
  analogWrite(PELTIER, 0);
}