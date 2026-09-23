#include <Wire.h>

void setup()
{
  Wire.begin();
  Serial.begin(115200);
  Serial.println("Scanning...");
}

void loop()
{
  for (byte addr = 1; addr < 127; addr++)
  {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0)
    {
      Serial.print("Found device at 0x");
      Serial.println(addr, HEX);
    }
  }
  delay(2000);
}