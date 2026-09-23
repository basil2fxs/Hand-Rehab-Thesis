// SingleTact address tool. Flashed in place of the game firmware for
// one job: move a sensor from one I2C address to another, then get
// replaced by the game firmware again.
//
// Serial, 115200, one command per line:
//   SCAN              -> FOUND: 0x04,0x05,0x06   (or FOUND: none)
//   CHANGE:0x04,0x05  -> OK: 0x04 -> 0x05        (or ERR: reason)
//   VERSION           -> ADDRTOOL 1
//
// Why a scan comes back with 0x04 whenever any sensor is attached:
// every SingleTact interface answers 0x04 as well as the address held
// in its flash (manual section 2.3). A write to 0x04 therefore reaches
// every sensor on the bus at once, which is why the host refuses to
// change "0x04" while any other address is visible.
//
// The write packet is the manual's Table 3: 0x02 (write), register
// offset 0 (the I2C address), one byte, the new address, 0xFF end of
// packet. The sensor saves every register write to its own flash, so
// nothing else is needed to make the change stick.

#include <Arduino.h>
#include <Wire.h>

static const uint8_t SCAN_FIRST = 0x03;
static const uint8_t SCAN_LAST = 0x77;
static const uint8_t ADDR_MIN = 0x04;   // manual: 4 to 127
static const uint8_t ADDR_MAX = 0x7F;

static char line[48];
static uint8_t lineLen = 0;

static bool acks(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static void printHex(uint8_t v) {
  Serial.print(F("0x"));
  if (v < 0x10) Serial.print('0');
  Serial.print(v, HEX);
}

static void scan() {
  bool any = false;
  Serial.print(F("FOUND: "));
  for (uint8_t a = SCAN_FIRST; a <= SCAN_LAST; a++) {
    if (acks(a)) {
      if (any) Serial.print(',');
      printHex(a);
      any = true;
    }
  }
  if (!any) Serial.print(F("none"));
  Serial.println();
}

// Accepts 0x05, 05 (hex) or 5 (decimal). Returns -1 on junk.
static int parseAddr(const char* s) {
  while (*s == ' ') s++;
  char* end = nullptr;
  long v;
  if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
    v = strtol(s + 2, &end, 16);
  } else {
    v = strtol(s, &end, 10);
  }
  if (end == s || v < 0 || v > 0x7F) return -1;
  return (int)v;
}

static void change(const char* args) {
  const char* comma = strchr(args, ',');
  if (comma == nullptr) {
    Serial.println(F("ERR: usage CHANGE:old,new"));
    return;
  }
  int oldA = parseAddr(args);
  int newA = parseAddr(comma + 1);
  if (oldA < ADDR_MIN || oldA > ADDR_MAX || newA < ADDR_MIN || newA > ADDR_MAX) {
    Serial.println(F("ERR: addresses must be 0x04 to 0x7F"));
    return;
  }
  if (oldA == newA) {
    Serial.println(F("ERR: old and new are the same"));
    return;
  }
  if (!acks((uint8_t)oldA)) {
    Serial.print(F("ERR: nothing answers at "));
    printHex((uint8_t)oldA);
    Serial.println();
    return;
  }
  uint8_t packet[5] = {0x02, 0x00, 0x01, (uint8_t)newA, 0xFF};
  Wire.beginTransmission((uint8_t)oldA);
  Wire.write(packet, sizeof(packet));
  uint8_t rc = Wire.endTransmission();
  if (rc != 0) {
    Serial.print(F("ERR: write to "));
    printHex((uint8_t)oldA);
    Serial.print(F(" failed, Wire code "));
    Serial.println(rc);
    return;
  }
  // The manual gives no settle time for the flash write; a quarter
  // second is far more than any register write on this part needs
  // and keeps the whole change under a second.
  delay(250);
  bool newSeen = acks((uint8_t)newA);
  // 0x04 always answers while any sensor is attached, so "old gone"
  // can only be checked for a real configured address.
  bool oldGone = (oldA == 0x04) ? true : !acks((uint8_t)oldA);
  if (newSeen && oldGone) {
    Serial.print(F("OK: "));
    printHex((uint8_t)oldA);
    Serial.print(F(" -> "));
    printHex((uint8_t)newA);
    Serial.println();
  } else if (!newSeen) {
    Serial.print(F("ERR: nothing answers at "));
    printHex((uint8_t)newA);
    Serial.println(F(" after the write"));
  } else {
    Serial.print(F("ERR: "));
    printHex((uint8_t)oldA);
    Serial.println(F(" still answers after the write"));
  }
}

static void handle(const char* cmd) {
  if (strcmp(cmd, "SCAN") == 0) {
    scan();
  } else if (strncmp(cmd, "CHANGE:", 7) == 0) {
    change(cmd + 7);
  } else if (strcmp(cmd, "VERSION") == 0) {
    Serial.println(F("ADDRTOOL 1"));
  } else {
    Serial.println(F("ERR: unknown command"));
  }
}

void setup() {
  Wire.begin();
  Serial.begin(115200);
  delay(200);
  Serial.println(F("### ADDR TOOL 1 ###"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) {
        line[lineLen] = '\0';
        handle(line);
        lineLen = 0;
      }
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = c;
    } else {
      lineLen = 0;
    }
  }
}
