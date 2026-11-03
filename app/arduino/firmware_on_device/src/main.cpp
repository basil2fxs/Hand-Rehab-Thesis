// ===== FSR I2C + Vibration Motor (STIM trigger) Full Sketch =====
// ref: your arduino_Final.ino style (Wire/I2C)
//
// Serial TX (to Python):   "FSR: v1,v2,v3,v4\n"   // ← Same as before
// Serial RX (from Python): "STIM:n\n"             // n = 1..4 → Turn on the vibration motor for that lane for a short time
//                          "STOP\n"               // Optional: Stop all lanes
//
// Note:
// Read 6 bytes from sensors with I²C addresses 0x05 to 0x08, and output the lower 2 bytes as raw values.
// Sampling is transmitted periodically at SAMPLE_HZ
// STIM is non-blocking (managed with millis), turns ON for a fixed time → then automatically OFF
// 

// Go to Include/Config.cpp for changing the overall behaviour of this project

#include "main.h"


// only one can be on at a time for proper debugging/testing
/*
#define TESTING
*/
#define MOTOR_TESTING
#define NORMAL_OPERATION

// Main variables //
uint8_t sampleIntervalMs = 1000 / sampleRate;
uint32_t currentSample = 0; uint32_t lastSample = 0;
char serialTXToPython[32];

#ifdef MOTOR_TESTING
// The motor self-test buzzes each motor for 200 ms in turn, 200 ms apart.
// It ran in setup() before the stream, which held the first sample back
// 2.6 s after every reset (opening the port resets the Nano), so the game
// waited 4.2 s for its first sample against a 2 s target. It now runs
// beside the stream: the first sample goes out 0.1 s after the bootloader
// hands over and the four buzzes follow over the next 1.6 s (3 Nov 2026).
const unsigned long SELF_TEST_ON_MS = 200;
const unsigned long SELF_TEST_GAP_MS = 200;
unsigned long selfTestStart = 0;
int selfTestMotor = 0;        // the motor buzzing or next to buzz; 4 when done
bool selfTestOn = false;

void runSelfTest()
{
  if (selfTestMotor > 3) return;
  unsigned long t = millis() - selfTestStart;
  unsigned long slot = (unsigned long)selfTestMotor * (SELF_TEST_ON_MS + SELF_TEST_GAP_MS);
  if (!selfTestOn && t >= slot) {
    individualMotorOn(selfTestMotor);
    selfTestOn = true;
  } else if (selfTestOn && t >= slot + SELF_TEST_ON_MS) {
    individualMotorOff(selfTestMotor);
    selfTestOn = false;
    selfTestMotor++;
  }
}
#endif

void setup()
{
  // Function Calls for setup // 
  Wire.begin();
  Serial.begin(115200);  // ← Match with the Python side
  motorInit();

  delay(100);   // the pads' boards settle before the first read

  Serial.println("### Setup Complete ###");

  #ifdef MOTOR_TESTING
  selfTestStart = millis();   // runSelfTest() buzzes the motors from loop()
  #endif
}

void loop(){ 
  handleSerial();   
  updateStimMotors();  
  #ifdef MOTOR_TESTING
  runSelfTest();
  #endif
  
  // Periodic sampling of Force Sensors //
  currentSample = millis();
  if ((currentSample - lastSample) >= sampleIntervalMs) 
  {
    #ifdef NORMAL_OPERATION
    uint16_t readings[4];
    for (int sensor = 0; sensor < 4; sensor++) 
    {
      int16_t raw = readForceRaw(sensor);  
      if (raw < 0) {raw = 0;} // Handle Negative values as failures
      readings[sensor] = raw;
    }
    #endif
    
    Serial.print(F("FSR: "));
    Serial.print(readings[0]); Serial.print(',');
    Serial.print(readings[1]); Serial.print(',');
    Serial.print(readings[2]); Serial.print(',');
    Serial.println(readings[3]);
      
    lastSample = currentSample;
  } // End sample if
}// End loop

