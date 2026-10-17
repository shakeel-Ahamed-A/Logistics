/*
  Smart Logistics Evidence Monitor - STM32F103C8T6 (Blue Pill)
  Arduino STM32 core 3.0.0

  Debug/Web Serial: PA2 TX -> USB-TTL RX, PA3 RX <- USB-TTL TX, GND common
  GPS Serial1: GPS TX -> PA10, GPS RX -> PA9
  I2C: PB6 SCL, PB7 SDA | MPU6050 0x69 | DS3231 0x68 | LCD 0x27
  DHT11 PB5 | SD CS/SCK/MISO/MOSI PA4/PA5/PA6/PA7
  SW420 PB15 | reed PA1 | buzzer PB0 | LEDs PB1/PB10/PB11
  Buttons PB13/PB14 to GND (INPUT_PULLUP)
*/

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <RTClib.h>
#include <TinyGPSPlus.h>

#define USE_LCD 1
#define PASSIVE_BUZZER 1
#define BUZZER_ACTIVE_HIGH 1
#define SW420_ACTIVE_LOW 1

#if USE_LCD
  #include <LiquidCrystal_I2C.h>
#endif

#define PIN_DHT PB5
#define PIN_SD_CS PA4
#define PIN_SW420 PB15
#define PIN_REED PA1
#define PIN_BUZZER PB0
#define PIN_LED_GREEN PB1
#define PIN_LED_BLUE PB10
#define PIN_LED_RED PB11
#define PIN_BUTTON_1 PB13
#define PIN_BUTTON_2 PB14

const uint8_t MPU_ADDRESS = 0x69;
const uint8_t RTC_ADDRESS = 0x68;
const uint8_t LCD_ADDRESS = 0x27;

const uint32_t DEBUG_BAUD = 115200;
const uint32_t GPS_BAUD = 9600;
const uint32_t MOTION_INTERVAL_MS = 20;
const uint32_t DHT_INTERVAL_MS = 2500;
const uint32_t TELEMETRY_INTERVAL_MS = 1000;
const uint32_t HEALTH_INTERVAL_MS = 10000;
const uint32_t LCD_INTERVAL_MS = 750;
const uint32_t SD_RETRY_INTERVAL_MS = 10000;
const uint32_t EVENT_DURATION_MS = 3000;
const uint32_t EVENT_COOLDOWN_MS = 5000;
const uint32_t BUTTON_DEBOUNCE_MS = 30;
const uint32_t BLUE_PULSE_MS = 80;
const uint32_t GPS_FIX_MAX_AGE_MS = 5000;

const float IMPACT_THRESHOLD_G = 2.50f;
const float HIGH_TEMP_C = 40.0f;
const float TEMP_HYSTERESIS_C = 2.0f;
const float HIGH_HUMIDITY = 75.0f;
const float HUMIDITY_HYSTERESIS = 5.0f;

const uint16_t PRE_EVENT_SAMPLES = 100; // 2 seconds at 50 Hz

Uart DebugSerial(PA3, PA2); // RX, TX - deliberately not Serial2
#define GPS_SERIAL Serial1

Adafruit_MPU6050 mpu;
DHT dht(PIN_DHT, DHT11);
RTC_DS3231 rtc;
TinyGPSPlus gps;
#if USE_LCD
LiquidCrystal_I2C lcd(LCD_ADDRESS, 20, 4);
#endif

enum EventType {
  EVENT_NORMAL, EVENT_IMPACT, EVENT_VIBRATION, EVENT_TAMPER,
  EVENT_HIGH_TEMP, EVENT_HIGH_HUM, EVENT_MANUAL
};

struct MotionSample {
  uint32_t ms;
  float ax, ay, az;
  float gx, gy, gz;
  float magnitudeG;
};

struct Button {
  uint32_t pin;
  bool stable;
  bool raw;
  uint32_t changedAt;
};

bool mpuOK = false, rtcOK = false, sdOK = false, dhtOK = false;
bool lcdOK = false, gpsFix = false, rtcSyncedFromGPS = false;
bool vibration = false, tamper = false;
bool previousVibration = false, previousTamper = false;
bool temperatureArmed = true, humidityArmed = true;

float temperatureC = NAN, humidityPct = NAN;
MotionSample latest = {0, 0, 0, 0, 0, 0, 0, 1};
MotionSample preBuffer[PRE_EVENT_SAMPLES];
uint16_t preHead = 0, preCount = 0;

EventType activeEvent = EVENT_NORMAL;
uint32_t eventNumber = 0, eventStartedAt = 0, eventEndsAt = 0;
uint32_t lastEventEndedAt = 0;
bool eventActive = false, alarmSilenced = false;
float eventPeakG = 0;
File eventFile;
uint16_t eventSamplesSinceFlush = 0;

Button button1 = {PIN_BUTTON_1, HIGH, HIGH, 0};
Button button2 = {PIN_BUTTON_2, HIGH, HIGH, 0};

uint32_t lastMotionAt = 0, lastDHTAt = 0, lastTelemetryAt = 0;
uint32_t lastHealthAt = 0, lastLCDAt = 0, lastSDRetryAt = 0;
uint32_t blueOffAt = 0, buzzerTestEndsAt = 0, sirenChangedAt = 0;
bool sirenHighTone = false;
uint8_t lcdPage = 0;

const char *eventName(EventType type) {
  switch (type) {
    case EVENT_IMPACT: return "IMPACT";
    case EVENT_VIBRATION: return "VIBRATION";
    case EVENT_TAMPER: return "TAMPER";
    case EVENT_HIGH_TEMP: return "HIGH_TEMP";
    case EVENT_HIGH_HUM: return "HIGH_HUM";
    case EVENT_MANUAL: return "MANUAL";
    default: return "NORMAL";
  }
}

bool i2cPresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool cooldownComplete(uint32_t now) {
  return eventNumber == 0 || (uint32_t)(now - lastEventEndedAt) >= EVENT_COOLDOWN_MS;
}

void setActiveBuzzer(bool on) {
  digitalWrite(PIN_BUZZER,
    on ? (BUZZER_ACTIVE_HIGH ? HIGH : LOW)
       : (BUZZER_ACTIVE_HIGH ? LOW : HIGH));
}

void stopBuzzer() {
#if PASSIVE_BUZZER
  noTone(PIN_BUZZER);
#else
  setActiveBuzzer(false);
#endif
}

void serviceBuzzer(uint32_t now) {
  bool requested = (eventActive && !alarmSilenced) || (buzzerTestEndsAt != 0);
  if (buzzerTestEndsAt != 0 && (int32_t)(now - buzzerTestEndsAt) >= 0) {
    buzzerTestEndsAt = 0;
    requested = eventActive && !alarmSilenced;
  }
  if (!requested) { stopBuzzer(); return; }
#if PASSIVE_BUZZER
  if ((uint32_t)(now - sirenChangedAt) >= 250) {
    sirenChangedAt = now;
    sirenHighTone = !sirenHighTone;
    tone(PIN_BUZZER, sirenHighTone ? 2200 : 1400);
  }
#else
  setActiveBuzzer(true);
#endif
}

void updateOutputs(uint32_t now) {
  digitalWrite(PIN_LED_GREEN, eventActive ? LOW : HIGH);
  digitalWrite(PIN_LED_RED, eventActive ? HIGH : LOW);
  if (blueOffAt != 0 && (int32_t)(now - blueOffAt) >= 0) {
    digitalWrite(PIN_LED_BLUE, LOW);
    blueOffAt = 0;
  }
  serviceBuzzer(now);
}

void pulseBlue(uint32_t now) {
  digitalWrite(PIN_LED_BLUE, HIGH);
  blueOffAt = now + BLUE_PULSE_MS;
}

void formatDateTime(char *dateOut, size_t dateLen, char *timeOut, size_t timeLen) {
  if (!rtcOK) {
    snprintf(dateOut, dateLen, "NO_RTC");
    snprintf(timeOut, timeLen, "NO_RTC");
    return;
  }
  DateTime n = rtc.now();
  snprintf(dateOut, dateLen, "%04u-%02u-%02u", n.year(), n.month(), n.day());
  snprintf(timeOut, timeLen, "%02u:%02u:%02u", n.hour(), n.minute(), n.second());
}

void ensureCSVHeaders() {
  if (!sdOK) return;
  File f = SD.open("TELEM.CSV", FILE_WRITE);
  if (!f) { sdOK = false; return; }
  if (f.size() == 0) {
    f.println(F("millis,date,time,temperature,humidity,accelG,latitude,longitude,gpsFix,satellites,vibration,tamper,event,eventActive,eventNumber,alarmSilenced,sdOK,rtcOK,mpuOK,dhtOK"));
  }
  f.close();
  f = SD.open("EVENTS.CSV", FILE_WRITE);
  if (!f) { sdOK = false; return; }
  if (f.size() == 0) {
    f.println(F("eventNumber,event,phase,millis,date,time,ax,ay,az,gx,gy,gz,magnitudeG,temperature,humidity,latitude,longitude,gpsFix"));
  }
  f.close();
}

bool initializeSD() {
  bool ok = SD.begin(PIN_SD_CS);
  if (ok) { sdOK = true; ensureCSVHeaders(); }
  return sdOK;
}

void writeEventSample(const MotionSample &s, const char *phase) {
  if (!sdOK || !eventFile) return;
  char dateText[12], timeText[10];
  formatDateTime(dateText, sizeof(dateText), timeText, sizeof(timeText));
  eventFile.print(eventNumber); eventFile.print(',');
  eventFile.print(eventName(activeEvent)); eventFile.print(',');
  eventFile.print(phase); eventFile.print(','); eventFile.print(s.ms); eventFile.print(',');
  eventFile.print(dateText); eventFile.print(','); eventFile.print(timeText); eventFile.print(',');
  eventFile.print(s.ax, 4); eventFile.print(','); eventFile.print(s.ay, 4); eventFile.print(','); eventFile.print(s.az, 4); eventFile.print(',');
  eventFile.print(s.gx, 4); eventFile.print(','); eventFile.print(s.gy, 4); eventFile.print(','); eventFile.print(s.gz, 4); eventFile.print(',');
  eventFile.print(s.magnitudeG, 4); eventFile.print(',');
  if (dhtOK) eventFile.print(temperatureC, 1); eventFile.print(',');
  if (dhtOK) eventFile.print(humidityPct, 1); eventFile.print(',');
  if (gpsFix) eventFile.print(gps.location.lat(), 6); eventFile.print(',');
  if (gpsFix) eventFile.print(gps.location.lng(), 6); eventFile.print(',');
  eventFile.println(gpsFix ? 1 : 0);
  eventSamplesSinceFlush++;
  if (eventSamplesSinceFlush >= 25) {
    eventFile.flush();
    eventSamplesSinceFlush = 0;
  }
}

void dumpPreEvidence() {
  uint16_t start = (preCount == PRE_EVENT_SAMPLES) ? preHead : 0;
  for (uint16_t i = 0; i < preCount && sdOK; i++) {
    writeEventSample(preBuffer[(start + i) % PRE_EVENT_SAMPLES], "PRE");
  }
}

void storePreSample(const MotionSample &s) {
  preBuffer[preHead] = s;
  preHead = (preHead + 1) % PRE_EVENT_SAMPLES;
  if (preCount < PRE_EVENT_SAMPLES) preCount++;
}

void startEvent(EventType type, const MotionSample &trigger) {
  uint32_t now = millis();
  if (eventActive) {
    if (type == activeEvent && (type == EVENT_IMPACT || type == EVENT_VIBRATION)) {
      eventEndsAt = now + EVENT_DURATION_MS;
      if (trigger.magnitudeG > eventPeakG) eventPeakG = trigger.magnitudeG;
    }
    return;
  }
  if (!cooldownComplete(now)) {
    DebugSerial.println(F("[EVENT] Trigger ignored during cooldown"));
    return;
  }
  eventActive = true;
  activeEvent = type;
  eventNumber++;
  eventStartedAt = now;
  eventEndsAt = now + EVENT_DURATION_MS;
  alarmSilenced = false;
  eventPeakG = trigger.magnitudeG;
  sirenChangedAt = 0;
  if (sdOK) {
    eventFile = SD.open("EVENTS.CSV", FILE_WRITE);
    if (!eventFile) {
      sdOK = false;
    } else {
      eventSamplesSinceFlush = 0;
      dumpPreEvidence();
      writeEventSample(trigger, "TRIGGER");
      eventFile.flush();
    }
  }
  DebugSerial.print(F("[EVENT START] #")); DebugSerial.print(eventNumber);
  DebugSerial.print(' '); DebugSerial.println(eventName(activeEvent));
}

void finishEvent(uint32_t now) {
  DebugSerial.print(F("[EVENT END] #")); DebugSerial.println(eventNumber);
  eventActive = false;
  activeEvent = EVENT_NORMAL;
  alarmSilenced = false;
  lastEventEndedAt = now;
  if (eventFile) { eventFile.flush(); eventFile.close(); }
  stopBuzzer();
}

bool buttonPressed(Button &b, uint32_t now) {
  bool reading = digitalRead(b.pin);
  if (reading != b.raw) { b.raw = reading; b.changedAt = now; }
  if ((uint32_t)(now - b.changedAt) >= BUTTON_DEBOUNCE_MS && reading != b.stable) {
    b.stable = reading;
    return b.stable == LOW;
  }
  return false;
}

void serviceButtons(uint32_t now) {
  if (buttonPressed(button1, now)) {
    if (eventActive) {
      alarmSilenced = true;
      stopBuzzer();
      DebugSerial.println(F("ALARM ACKNOWLEDGED | BUZZER SILENCED | EVENT STILL ACTIVE"));
    } else {
      buzzerTestEndsAt = now + 1000;
      sirenChangedAt = 0;
      DebugSerial.println(F("[TEST] Buzzer test for 1 second"));
    }
  }
  if (buttonPressed(button2, now)) startEvent(EVENT_MANUAL, latest);
}

void serviceDigitalTriggers(uint32_t now) {
  vibration = digitalRead(PIN_SW420) == (SW420_ACTIVE_LOW ? LOW : HIGH);
  tamper = digitalRead(PIN_REED) == HIGH;
  if (vibration && !previousVibration) startEvent(EVENT_VIBRATION, latest);
  if (tamper && !previousTamper) startEvent(EVENT_TAMPER, latest);
  if (eventActive && activeEvent == EVENT_VIBRATION && vibration) eventEndsAt = now + EVENT_DURATION_MS;
  previousVibration = vibration;
  previousTamper = tamper;
}

void serviceGPS() {
  while (GPS_SERIAL.available()) gps.encode(GPS_SERIAL.read());
  gpsFix = gps.location.isValid() && gps.location.age() < GPS_FIX_MAX_AGE_MS;
  if (!rtcSyncedFromGPS && rtcOK && gps.date.isValid() && gps.time.isValid() && gps.date.age() < 5000) {
    rtc.adjust(DateTime(gps.date.year(), gps.date.month(), gps.date.day(),
                        gps.time.hour(), gps.time.minute(), gps.time.second()));
    rtcSyncedFromGPS = true; // GPS time is UTC.
    DebugSerial.println(F("[RTC] Synchronized once from GPS UTC"));
  }
}

void readMotion(uint32_t now) {
  if (!mpuOK) return;
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  MotionSample s;
  s.ms = now;
  s.ax = a.acceleration.x; s.ay = a.acceleration.y; s.az = a.acceleration.z;
  s.gx = g.gyro.x; s.gy = g.gyro.y; s.gz = g.gyro.z;
  s.magnitudeG = sqrtf(s.ax*s.ax + s.ay*s.ay + s.az*s.az) / 9.80665f;
  latest = s;
  bool wasActive = eventActive;
  if (s.magnitudeG >= IMPACT_THRESHOLD_G) startEvent(EVENT_IMPACT, s);
  if (eventActive && wasActive) {
    if (s.magnitudeG > eventPeakG) eventPeakG = s.magnitudeG;
    writeEventSample(s, "POST");
  }
  storePreSample(s);
}

void readEnvironment() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (isnan(h) || isnan(t)) { dhtOK = false; return; }
  humidityPct = h; temperatureC = t; dhtOK = true;
  if (temperatureArmed && t >= HIGH_TEMP_C) {
    startEvent(EVENT_HIGH_TEMP, latest); temperatureArmed = false;
  } else if (!temperatureArmed && t <= HIGH_TEMP_C - TEMP_HYSTERESIS_C) temperatureArmed = true;
  if (humidityArmed && h >= HIGH_HUMIDITY) {
    startEvent(EVENT_HIGH_HUM, latest); humidityArmed = false;
  } else if (!humidityArmed && h <= HIGH_HUMIDITY - HUMIDITY_HYSTERESIS) humidityArmed = true;
}

void writeTelemetryCSV(uint32_t now) {
  if (!sdOK) return;
  File f = SD.open("TELEM.CSV", FILE_WRITE);
  if (!f) { sdOK = false; return; }
  char dateText[12], timeText[10];
  formatDateTime(dateText, sizeof(dateText), timeText, sizeof(timeText));
  f.print(now); f.print(','); f.print(dateText); f.print(','); f.print(timeText); f.print(',');
  if (dhtOK) f.print(temperatureC, 1); f.print(',');
  if (dhtOK) f.print(humidityPct, 1); f.print(',');
  f.print(latest.magnitudeG, 3); f.print(',');
  if (gpsFix) f.print(gps.location.lat(), 6); f.print(',');
  if (gpsFix) f.print(gps.location.lng(), 6); f.print(',');
  f.print(gpsFix ? 1 : 0); f.print(',');
  f.print(gps.satellites.isValid() ? gps.satellites.value() : 0); f.print(',');
  f.print(vibration ? 1 : 0); f.print(','); f.print(tamper ? 1 : 0); f.print(',');
  f.print(eventName(activeEvent)); f.print(','); f.print(eventActive ? 1 : 0); f.print(',');
  f.print(eventNumber); f.print(','); f.print(alarmSilenced ? 1 : 0); f.print(',');
  f.print(sdOK ? 1 : 0); f.print(','); f.print(rtcOK ? 1 : 0); f.print(',');
  f.print(mpuOK ? 1 : 0); f.print(','); f.println(dhtOK ? 1 : 0);
  f.close();
  pulseBlue(now);
}

void printJSON(uint32_t now) {
  char dateText[12], timeText[10];
  formatDateTime(dateText, sizeof(dateText), timeText, sizeof(timeText));
  DebugSerial.print(F("{\"type\":\"telemetry\",\"ms\":")); DebugSerial.print(now);
  DebugSerial.print(F(",\"date\":\"")); DebugSerial.print(dateText);
  DebugSerial.print(F("\",\"time\":\"")); DebugSerial.print(timeText);
  DebugSerial.print(F("\",\"temperature\":")); if (dhtOK) DebugSerial.print(temperatureC,1); else DebugSerial.print(F("null"));
  DebugSerial.print(F(",\"humidity\":")); if (dhtOK) DebugSerial.print(humidityPct,1); else DebugSerial.print(F("null"));
  DebugSerial.print(F(",\"ax\":")); DebugSerial.print(latest.ax,3);
  DebugSerial.print(F(",\"ay\":")); DebugSerial.print(latest.ay,3);
  DebugSerial.print(F(",\"az\":")); DebugSerial.print(latest.az,3);
  DebugSerial.print(F(",\"accelG\":")); DebugSerial.print(latest.magnitudeG,3);
  DebugSerial.print(F(",\"latitude\":")); if (gpsFix) DebugSerial.print(gps.location.lat(),6); else DebugSerial.print(F("null"));
  DebugSerial.print(F(",\"longitude\":")); if (gpsFix) DebugSerial.print(gps.location.lng(),6); else DebugSerial.print(F("null"));
  DebugSerial.print(F(",\"gpsFix\":")); DebugSerial.print(gpsFix ? F("true") : F("false"));
  DebugSerial.print(F(",\"gpsBytes\":")); DebugSerial.print(gps.charsProcessed());
  DebugSerial.print(F(",\"satellites\":")); DebugSerial.print(gps.satellites.isValid() ? gps.satellites.value() : 0);
  DebugSerial.print(F(",\"vibration\":")); DebugSerial.print(vibration ? F("true") : F("false"));
  DebugSerial.print(F(",\"tamper\":")); DebugSerial.print(tamper ? F("true") : F("false"));
  DebugSerial.print(F(",\"event\":\"")); DebugSerial.print(eventName(activeEvent));
  DebugSerial.print(F("\",\"eventActive\":")); DebugSerial.print(eventActive ? F("true") : F("false"));
  DebugSerial.print(F(",\"eventNumber\":")); DebugSerial.print(eventNumber);
  DebugSerial.print(F(",\"alarmSilenced\":")); DebugSerial.print(alarmSilenced ? F("true") : F("false"));
  DebugSerial.print(F(",\"peakG\":")); DebugSerial.print(eventPeakG,3);
  DebugSerial.print(F(",\"health\":{\"mpu\":")); DebugSerial.print(mpuOK ? F("true") : F("false"));
  DebugSerial.print(F(",\"rtc\":")); DebugSerial.print(rtcOK ? F("true") : F("false"));
  DebugSerial.print(F(",\"sd\":")); DebugSerial.print(sdOK ? F("true") : F("false"));
  DebugSerial.print(F(",\"dht\":")); DebugSerial.print(dhtOK ? F("true") : F("false"));
  DebugSerial.print(F(",\"lcd\":")); DebugSerial.print(lcdOK ? F("true") : F("false"));
  DebugSerial.println(F("}}"));
}

#if USE_LCD
void lcdLine(uint8_t row, const char *text) {
  lcd.setCursor(0, row);
  char line[21]; snprintf(line, sizeof(line), "%-20.20s", text); lcd.print(line);
}

void updateLCD() {
  if (!lcdOK) return;
  char line[21];
  if (eventActive) {
    snprintf(line, sizeof(line), "*** %-12s", eventName(activeEvent)); lcdLine(0, line);
    snprintf(line, sizeof(line), "Peak: %.2fg  Event:%lu", eventPeakG, (unsigned long)eventNumber); lcdLine(1, line);
    lcdLine(2, alarmSilenced ? "ALARM: ACKNOWLEDGED" : "BUZZER: ALARM");
    lcdLine(3, "BTN1 = SILENCE");
    return;
  }
  if (lcdPage == 0) {
    lcdLine(0, "SMART LOGISTICS");
    if (dhtOK) snprintf(line, sizeof(line), "T:%.1fC H:%.0f%%", temperatureC, humidityPct); else snprintf(line,sizeof(line),"T:-- H:-- DHT ERR"); lcdLine(1,line);
    snprintf(line,sizeof(line),"ACC:%.2fg GPS:%s",latest.magnitudeG,gpsFix?"FIX":"NO"); lcdLine(2,line);
    lcdLine(3, "STATE: NORMAL");
  } else {
    snprintf(line,sizeof(line),"RTC:%s SD:%s",rtcOK?"OK":"ERR",sdOK?"OK":"ERR"); lcdLine(0,line);
    snprintf(line,sizeof(line),"GPS:%s SAT:%lu",gpsFix?"FIX":"NO FIX",(unsigned long)(gps.satellites.isValid()?gps.satellites.value():0)); lcdLine(1,line);
    snprintf(line,sizeof(line),"VIB:%s",vibration?"ACTIVE":"NORMAL"); lcdLine(2,line);
    snprintf(line,sizeof(line),"SEAL:%s",tamper?"OPEN/TAMPER":"CLOSED/SAFE"); lcdLine(3,line);
  }
  lcdPage ^= 1;
}
#endif

void recoverModules(uint32_t now) {
  if (!mpuOK && i2cPresent(MPU_ADDRESS)) {
    mpuOK = mpu.begin(MPU_ADDRESS, &Wire);
    if (mpuOK) { mpu.setAccelerometerRange(MPU6050_RANGE_8_G); mpu.setGyroRange(MPU6050_RANGE_500_DEG); mpu.setFilterBandwidth(MPU6050_BAND_21_HZ); }
  }
  if (!rtcOK && i2cPresent(RTC_ADDRESS)) rtcOK = rtc.begin(&Wire);
  if (!sdOK && (uint32_t)(now - lastSDRetryAt) >= SD_RETRY_INTERVAL_MS) { lastSDRetryAt = now; initializeSD(); }
}

void startupSelfTest() {
  const uint32_t leds[] = {PIN_LED_GREEN, PIN_LED_BLUE, PIN_LED_RED};
  for (uint8_t i=0; i<3; i++) { digitalWrite(leds[i], HIGH); delay(120); digitalWrite(leds[i], LOW); }
#if PASSIVE_BUZZER
  tone(PIN_BUZZER, 1800); delay(100); noTone(PIN_BUZZER);
#else
  setActiveBuzzer(true); delay(100); setActiveBuzzer(false);
#endif
}

void setup() {
  pinMode(PIN_LED_GREEN, OUTPUT); pinMode(PIN_LED_BLUE, OUTPUT); pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT); pinMode(PIN_SW420, INPUT); pinMode(PIN_REED, INPUT_PULLUP);
  pinMode(PIN_BUTTON_1, INPUT_PULLUP); pinMode(PIN_BUTTON_2, INPUT_PULLUP);
  digitalWrite(PIN_LED_GREEN, LOW); digitalWrite(PIN_LED_BLUE, LOW); digitalWrite(PIN_LED_RED, LOW); stopBuzzer();
  DebugSerial.begin(DEBUG_BAUD); GPS_SERIAL.begin(GPS_BAUD);
  delay(250); DebugSerial.println(F("\nSMART LOGISTICS - STARTUP SELF TEST")); startupSelfTest();
  Wire.setSDA(PB7); Wire.setSCL(PB6); Wire.begin(); Wire.setClock(100000);
  mpuOK = i2cPresent(MPU_ADDRESS) && mpu.begin(MPU_ADDRESS, &Wire);
  if (mpuOK) { mpu.setAccelerometerRange(MPU6050_RANGE_8_G); mpu.setGyroRange(MPU6050_RANGE_500_DEG); mpu.setFilterBandwidth(MPU6050_BAND_21_HZ); }
  rtcOK = i2cPresent(RTC_ADDRESS) && rtc.begin(&Wire);
  if (rtcOK && rtc.lostPower()) rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  dht.begin(); SPI.begin(); initializeSD();
#if USE_LCD
  lcdOK = i2cPresent(LCD_ADDRESS);
  if (lcdOK) { lcd.init(); lcd.backlight(); lcd.clear(); lcdLine(0,"SMART LOGISTICS"); lcdLine(1,"SELF TEST COMPLETE"); }
#endif
  previousTamper = tamper = digitalRead(PIN_REED) == HIGH;
  previousVibration = vibration = digitalRead(PIN_SW420) == (SW420_ACTIVE_LOW ? LOW : HIGH);
  button1.raw = button1.stable = digitalRead(PIN_BUTTON_1);
  button2.raw = button2.stable = digitalRead(PIN_BUTTON_2);
  DebugSerial.print(F("MPU:")); DebugSerial.print(mpuOK?F("OK"):F("ERR"));
  DebugSerial.print(F(" RTC:")); DebugSerial.print(rtcOK?F("OK"):F("ERR"));
  DebugSerial.print(F(" SD:")); DebugSerial.print(sdOK?F("OK"):F("ERR"));
  DebugSerial.print(F(" LCD:")); DebugSerial.println(lcdOK?F("OK"):F("OFF/ERR"));
  digitalWrite(PIN_LED_GREEN, HIGH);
}

void loop() {
  uint32_t now = millis();
  serviceGPS();
  serviceButtons(now);
  serviceDigitalTriggers(now);
  if ((uint32_t)(now - lastMotionAt) >= MOTION_INTERVAL_MS) { lastMotionAt += MOTION_INTERVAL_MS; readMotion(now); }
  if ((uint32_t)(now - lastDHTAt) >= DHT_INTERVAL_MS) { lastDHTAt = now; readEnvironment(); }
  if (eventActive && (int32_t)(now - eventEndsAt) >= 0) finishEvent(now);
  if ((uint32_t)(now - lastTelemetryAt) >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryAt = now; writeTelemetryCSV(now); printJSON(now);
  }
  if ((uint32_t)(now - lastHealthAt) >= HEALTH_INTERVAL_MS) { lastHealthAt = now; recoverModules(now); }
#if USE_LCD
  if ((uint32_t)(now - lastLCDAt) >= LCD_INTERVAL_MS) { lastLCDAt = now; updateLCD(); }
#endif
  updateOutputs(now);
}
