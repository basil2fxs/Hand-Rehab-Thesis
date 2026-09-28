const int IN1 = 8;
const int IN2 = 9;
const int ENA = 10;

const int BTN_EXTEND = 2;
const int BTN_RETRACT = 3;

const int MOTOR_SPEED = 255;   // 0 to 255

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENA, OUTPUT);

  pinMode(BTN_EXTEND, INPUT_PULLUP);
  pinMode(BTN_RETRACT, INPUT_PULLUP);

  stopActuator();
}

void loop() {
  bool extendPressed = (digitalRead(BTN_EXTEND) == LOW);
  bool retractPressed = (digitalRead(BTN_RETRACT) == LOW);

  // Only extend if extend button is pressed by itself
  if (extendPressed && !retractPressed) {
    extendActuator();
  }
  // Only retract if retract button is pressed by itself
  else if (retractPressed && !extendPressed) {
    retractActuator();
  }
  // If neither or both are pressed, stop
  else {
    stopActuator();
  }
}

void extendActuator() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, MOTOR_SPEED);
}

void retractActuator() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  analogWrite(ENA, MOTOR_SPEED);
}

void stopActuator() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, 0);
}
