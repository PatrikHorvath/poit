#include <OneWire.h>
#include <DallasTemperature.h>

const int PUMP_ENB = 6;  
const int PUMP_IN3 = 8;  
const int PUMP_IN4 = 9;  

const int PELTIER = 5;   

const int TEMP_PIN = 2;  

OneWire oneWire(TEMP_PIN);
DallasTemperature sensors(&oneWire);

int peltierPWM = 0;
int pwmPercent = 0;
bool isPumpRunning = false;
bool isSystemActive = false;
bool debugActive = false;
unsigned long lastTempCheck = 0;

void setup() {
  pinMode(PUMP_ENB, OUTPUT);
  pinMode(PUMP_IN3, OUTPUT);
  pinMode(PUMP_IN4, OUTPUT);
  pinMode(PELTIER, OUTPUT);

  digitalWrite(PUMP_IN3, HIGH);
  digitalWrite(PUMP_IN4, LOW);

  analogWrite(PUMP_ENB, 0);
  analogWrite(PELTIER, 0);

  Serial.begin(115200);
  
  sensors.begin();
  stopAll();
}

void loop() {
  if (isSystemActive && (millis() - lastTempCheck >= 2000)) {
    sensors.requestTemperatures();
    float celsius = sensors.getTempCByIndex(0);
    
    if (celsius != -127.00) {
      // int pwmPercent = map(peltierPWM, 0, 255, 0, 100);
      Serial.print("DATA:");
      Serial.print(celsius);
      Serial.print(",");
      Serial.println(pwmPercent);
    }
    lastTempCheck = millis();
  }

  if (Serial.available() > 0) {
    String inputString = Serial.readStringUntil('\n');
    inputString.trim();
    
    if (inputString == "ON") {
      coolMode();
    } 
    else if (inputString == "OFF") {
      stopAll();
    } 
    else if (inputString.startsWith("DEBUG:")) {
      int val = inputString.substring(6).toInt();
      debugActive = (val == 1);
    }
    else if (inputString.startsWith("PWM:")) {
      if (debugActive) {
        pwmPercent = inputString.substring(4).toInt();
        pwmPercent = constrain(pwmPercent, 0, 100);
        peltierPWM = map(pwmPercent, 0, 100, 0, 255);
        analogWrite(PELTIER, peltierPWM);
      }
    }
  }
}

void coolMode() {
  isSystemActive = true;
  if (!isPumpRunning) {
    analogWrite(PUMP_ENB, 255); 
    delay(150);                 
    isPumpRunning = true;
  }
  analogWrite(PELTIER, peltierPWM);  
}

void stopAll() {
  analogWrite(PELTIER, 0);
  analogWrite(PUMP_ENB, 0);
  isPumpRunning = false;
  isSystemActive = false;
}
