// ===== FSR I2C + Vibration Motor (STIM trigger) Full Sketch =====
// ref: your arduino_Final.ino style (Wire/I2C, motor pins 3,4,5,6)
//
// Serial TX (to Python):   "FSR: v1,v2,v3,v4\n"   // ←従来どおり
// Serial RX (from Python): "STIM:n\n"             // n = 1..4 → そのレーンの振動モーターを短時間ON
//                          "STOP\n"               // 任意: 全レーン停止
//
// Note:
//  - I2Cアドレス 0x05..0x08 のセンサから 6バイト読出し、下位2バイトを生値として送出
//  - サンプリングは SAMPLE_HZ で周期送信
//  - STIMは非ブロッキング（millis管理）で一定時間だけON→自動OFF
//  - PWM非対応のピン（UNOのD4など）でも analogWrite 呼び出しで実質ON/OFFとして動作（振動用途OK）
//  - 実機駆動は必ずトランジスタ/MOSFET＋フライバックダイオードを使用（直結NG）

#include <Wire.h>

//  I2C sensor addresses (from your code) 
#define FSR1 0x05
#define FSR2 0x06
#define FSR3 0x07
#define FSR4 0x08

//  Motor pins (from your code) 
#define MOTOR_1 3
#define MOTOR_2 4   // 非PWM（UNO）※振動ON/OFFならOK
#define MOTOR_3 5
#define MOTOR_4 6

//  Sampling / STIM settings 
const unsigned long SAMPLE_HZ   = 200;   // 送信レート（Hz）
const unsigned long STIM_ON_MS  = 150;   // 刺激ON時のモーター駆動時間（ms）
const uint8_t       STIM_PWM    = 200;   // 0..255（振動の強さ目安）

//  I2C read frame spec (from your code style) 
#define READ_OFFSET  128       // 読み出し開始オフセット
#define READ_LENGTH  6         // 要求バイト数（最低6バイト必要）

//  Arrays 
const uint8_t sensorAddresses[4] = {FSR1, FSR2, FSR3, FSR4};
const uint8_t motorPins[4]       = {MOTOR_1, MOTOR_2, MOTOR_3, MOTOR_4};
const bool sensorEnabled[4] = {true, true, true, true}; //CHANGE #1

//  Internal state 
static unsigned long nextSampleAt = 0;
static unsigned long sampleIntervalMs = 1000UL / SAMPLE_HZ;

static unsigned long stimOffAt[4] = {0,0,0,0};  // STIMの自動OFF予定時刻（0=OFF中）

// RX line buffer
static char rxLine[64];
static uint8_t rxLen = 0;

//  Forward decl 
int  readForceRaw(uint8_t addr);
void handleSerial();
void processLine(const char* s);
void triggerStimMotor(int laneIdx);
void updateStimMotors();

void setup() {
  Wire.begin();
  Serial.begin(115200);  // ← Python側と合わせる

  // Motor init
  for (int i=0; i<4; ++i) {
    pinMode(motorPins[i], OUTPUT);
    analogWrite(motorPins[i], 0);
  }

  // 初回送信タイミング
  nextSampleAt = millis();
}

void loop() {
  handleSerial();      // STIM/STOP 受信
  updateStimMotors();  // STIMの自動OFF

  // 周期サンプリングして "FSR: v1,v2,v3,v4" を送出
  unsigned long now = millis();
  if ((long)(now - nextSampleAt) >= 0) {
    int v[4];

    for (int i=0; i<4; ++i) { //ADDED BY RAY
      if (!sensorEnabled[i]) { v[i] = 0; continue; }  // skip — no I2C attempt
      int raw = readForceRaw(sensorAddresses[i]);
      if (raw < 0) raw = 0;
      v[i] = raw;
    }

    // 出力：従来どおり "FSR: 123,456,..."（空白無しでもOK）
    Serial.print(F("FSR: "));
    Serial.print(v[0]); Serial.print(',');
    Serial.print(v[1]); Serial.print(',');
    Serial.print(v[2]); Serial.print(',');
    Serial.println(v[3]);

    nextSampleAt += sampleIntervalMs;
    // 大きく遅延したら仕切り直し
    if ((long)(now - nextSampleAt) > (long)(5 * sampleIntervalMs)) {
      nextSampleAt = now + sampleIntervalMs;
    }
  }
}

//  I2C: raw 16-bit読出し（下位2Bを合成） 
int readForceRaw(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(READ_OFFSET);
  // repeated start
  if (Wire.endTransmission(false) != 0) {
    return -1; // NACK/エラー
  }

  int req = READ_LENGTH;
  int n = Wire.requestFrom((int)addr, req, (int)true);
  if (n < 6) return -2;

  uint8_t buf[READ_LENGTH];
  int count = 0;
  while (Wire.available() && count < READ_LENGTH) {
    buf[count++] = Wire.read();
  }
  if (count < 6) return -3;

  // あなたの元コード同様に [4],[5] を結合
  int forceRaw = ((int)buf[4] << 8) | (int)buf[5];
  return forceRaw;  // Python側で後段処理（EMA/閾値）を実施
}

//  STIM control 
void triggerStimMotor(int laneIdx) {
  if (laneIdx < 0 || laneIdx > 3) return;
  analogWrite(motorPins[laneIdx], STIM_PWM);           // 即時起動
  stimOffAt[laneIdx] = millis() + STIM_ON_MS;          // 一定時間後に自動OFF
}

void updateStimMotors() {
  unsigned long now = millis();
  for (int i=0; i<4; ++i) {
    if (stimOffAt[i] && (long)(now - stimOffAt[i]) >= 0) {
      analogWrite(motorPins[i], 0);
      stimOffAt[i] = 0;
    }
  }
}

//  Serial RX (line based) 
void handleSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxLen > 0) {
        rxLine[rxLen] = '\0';
        processLine(rxLine);
        rxLen = 0;
      }
    } else {
      if (rxLen < sizeof(rxLine) - 1) {
        rxLine[rxLen++] = c;
      } else {
        // overflow -> reset
        rxLen = 0;
      }
    }
  }
}

void processLine(const char* s) {
  // "STIM:n"
  if (strncmp(s, "STIM:", 5) == 0) {
    int lane = atoi(s + 5);
    if (lane >= 1 && lane <= 4) {
      triggerStimMotor(lane - 1);
    }
    return;
  }

  // 任意: 全停止
  if (strcmp(s, "STOP") == 0) {
    for (int i=0; i<4; ++i) {
      analogWrite(motorPins[i], 0);
      stimOffAt[i] = 0;
    }
    return;
  }
  // それ以外は無視
}