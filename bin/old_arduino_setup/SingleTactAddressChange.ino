#include <Wire.h>

bool addressChanged = false;

void setup() {
  Wire.begin();
  Serial.begin(57600);
  Serial.println("PPS UK: Changing SingleTact slave address.");
}

void loop() {
  if (!addressChanged) {
    byte oldAddress = 0x04;  // Current address of sensor
    byte newAddress = 0x05;  // Desired new address

    changeSensorAddress(oldAddress, newAddress);
    Serial.print("Sent command to change address from 0x");
    Serial.print(oldAddress, HEX);
    Serial.print(" to 0x");
    Serial.println(newAddress, HEX);

    addressChanged = true;
  }

  delay(1000);  // Wait before looping again
}

void changeSensorAddress(byte oldAddress, byte newAddress) {
  byte buf[5];
  buf[0] = 0x02;       // Write command
  buf[1] = 0x00;       // Address pointer
  buf[2] = 0x01;       // Write 1 byte
  buf[3] = newAddress; // New address
  buf[4] = 0xFF;       // Write to non-volatile memory

  Wire.beginTransmission(oldAddress);
  Wire.write(buf, 5);
  Wire.endTransmission();
}