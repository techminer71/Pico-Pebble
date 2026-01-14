#include <Arduino.h>
#include <avr/interrupt.h>
#include <ctype.h>
#include <string.h>
#include <Keyboard.h>

static const int ARM_PIN = 2;
static bool hid_enabled = true;

static constexpr uint8_t  EOT    = 0x04;
static constexpr uint16_t BUF_SZ = 256;

volatile uint8_t  rxBuf[BUF_SZ];
volatile uint16_t rxIdx = 0;
volatile uint16_t msgLen = 0;
volatile bool     msgReady = false;
volatile bool     overflowed = false;

static uint8_t localBuf[BUF_SZ + 1];
static char    upperLine[140];
static char    lastCmd[140];
static long    defaultDelayMs = 0;

// ---------- helpers ----------
static uint16_t sum16(const uint8_t* b, uint16_t n) {
  uint32_t s = 0;
  for (uint16_t i = 0; i < n; i++) s += b[i];
  return (uint16_t)(s & 0xFFFF);
}

static char* trim(char* s) {
  while (*s && isspace((unsigned char)*s)) s++;
  char* end = s + strlen(s);
  while (end > s && isspace((unsigned char)end[-1])) end--;
  *end = 0;
  return s;
}

static void toUpperCopy(const char* in, char* out, size_t outsz) {
  size_t i = 0;
  for (; i + 1 < outsz && in[i]; i++) out[i] = (char)toupper((unsigned char)in[i]);
  out[i] = 0;
}

// ---------- event emitter (debug only) ----------
static void evt_keydown(const char* k)  { Serial.print("[EVT] KEYDOWN  "); Serial.println(k); }
static void evt_keyup(const char* k)    { Serial.print("[EVT] KEYUP    "); Serial.println(k); }
static void evt_keypress(const char* k) { Serial.print("[EVT] KEYPRESS "); Serial.println(k); }
static void evt_type(const char* s)     { Serial.print("[EVT] TYPE     \""); Serial.print(s); Serial.println("\""); }
static void evt_delay(long ms)          { Serial.print("[EVT] DELAY    "); Serial.print(ms); Serial.println(" ms"); }

static void apply_default_delay() {
  if (defaultDelayMs > 0) evt_delay(defaultDelayMs);
}

static bool is_modifier(const char* tok, const char** norm) {
  if (!strcmp(tok, "CTRL") || !strcmp(tok, "CONTROL")) { *norm = "CTRL"; return true; }
  if (!strcmp(tok, "SHIFT"))                           { *norm = "SHIFT"; return true; }
  if (!strcmp(tok, "ALT") || !strcmp(tok, "OPTION"))   { *norm = "ALT"; return true; }
  if (!strcmp(tok, "GUI") || !strcmp(tok, "WINDOWS") || !strcmp(tok, "WIN") || !strcmp(tok, "COMMAND")) {
    *norm = "GUI"; return true;
  }
  return false;
}

static void normalize_key(const char* tok, char* out, size_t outsz) {
  // minimal: pass-through with a few normalizations
  if (!strcmp(tok, "RETURN")) tok = "ENTER";
  if (!strcmp(tok, "ESCAPE")) tok = "ESC";
  if (!strcmp(tok, "DEL"))    tok = "DELETE";
  strncpy(out, tok, outsz - 1);
  out[outsz - 1] = 0;
}

static void emit_combo(char* lineUpper) {
  // lineUpper is mutable, uppercase, trimmed
  const char* mods[6];
  uint8_t modCount = 0;

  char keys[4][16];
  uint8_t keyCount = 0;

  // Split by spaces manually
  char* p = lineUpper;
  while (*p) {
    while (*p == ' ') p++;
    if (!*p) break;

    char* tok = p;
    while (*p && *p != ' ') p++;
    if (*p) { *p = 0; p++; }

    if (!*tok) continue;

    const char* m = nullptr;
    if (is_modifier(tok, &m)) {
      if (modCount < 6) mods[modCount++] = m;
      continue;
    }

    if (keyCount < 4) {
      normalize_key(tok, keys[keyCount], sizeof(keys[keyCount]));
      keyCount++;
    }
  }

  if (keyCount == 0 && modCount > 0) {
    Serial.println("[EVT][WARN] modifiers with no key");
    apply_default_delay();
    return;
  }

  // Hold modifiers
  for (uint8_t i = 0; i < modCount; i++) evt_keydown(mods[i]);

  // Press keys
  for (uint8_t i = 0; i < keyCount; i++) evt_keypress(keys[i]);

  // Release modifiers
  for (int i = (int)modCount - 1; i >= 0; i--) evt_keyup(mods[i]);

  apply_default_delay();
}

static void simulate_line(const char* raw) {
  // trim in-place caller provides mutable line; here we only read it
  char lineBuf[140];
  strncpy(lineBuf, raw, sizeof(lineBuf) - 1);
  lineBuf[sizeof(lineBuf) - 1] = 0;

  char* line = trim(lineBuf);
  if (!*line) return;

  // Comment
  if (!strncmp(line, "REM ", 4)) {
    Serial.print("[REM] ");
    Serial.println(line + 4);
    return;
  }

  // Save for REPEAT
  strncpy(lastCmd, line, sizeof(lastCmd) - 1);
  lastCmd[sizeof(lastCmd) - 1] = 0;

  // Uppercase copy for command detection
  toUpperCopy(line, upperLine, sizeof(upperLine));

  if (!strncmp(upperLine, "STRING ", 7)) {
    evt_type(line + 7);  // keep original casing for typed text
    apply_default_delay();
    return;
  }

  if (!strncmp(upperLine, "DELAY ", 6)) {
    long ms = atol(upperLine + 6);
    evt_delay(ms);
    apply_default_delay();
    return;
  }

  if (!strncmp(upperLine, "DEFAULT_DELAY ", 14) || !strncmp(upperLine, "DEFAULTDELAY ", 13)) {
    const char* sp = strchr(upperLine, ' ');
    defaultDelayMs = sp ? atol(sp + 1) : 0;
    Serial.print("[EVT] SET DEFAULT_DELAY "); Serial.print(defaultDelayMs); Serial.println(" ms");
    return;
  }

  if (!strncmp(upperLine, "REPEAT ", 7)) {
    int n = atoi(upperLine + 7);
    Serial.print("[EVT] REPEAT "); Serial.println(n);
    if (n <= 0 || !lastCmd[0]) return;
    for (int i = 0; i < n; i++) simulate_line(lastCmd);
    return;
  }

  // Otherwise treat as key / combo line
  // Make upperLine mutable for splitting:
  emit_combo(upperLine);
}

// ---------- SPI ISR ----------
ISR(SPI_STC_vect) {
  uint8_t b = SPDR;

  if (msgReady) return;

  if (b == EOT) {
    msgLen = rxIdx;
    rxIdx = 0;
    msgReady = true;
    return;
  }

  if (rxIdx < BUF_SZ) rxBuf[rxIdx++] = b;
  else { overflowed = true; rxIdx = 0; }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(SS, INPUT_PULLUP);
  pinMode(MISO, OUTPUT);
  pinMode(ARM_PIN, INPUT_PULLUP);

  if (digitalRead(ARM_PIN) == LOW) {
    hid_enabled = false;
    Serial.println("[HID] Disabled (ARM held at boot).");
  } else {
    Serial.println("[HID] Enabled (debug-typing mode)");
  }

  SPCR = _BV(SPE) | _BV(SPIE);
  sei();

  Serial.println("SPI Ducky DEBUG (Low-RAM Event Emitter) ready.");
}

static void hid_type_payload_as_text(const uint8_t* data, uint16_t len) {
  if (!hid_enabled) {
    Serial.println("[HID] Not typing: HID disabled.");
    return;
  }

  // Require a deliberate press to type
  Serial.println("[HID] Press and HOLD ARM (D2->GND) to type payload as text...");
  unsigned long start = millis();
  while (millis() - start < 5000) {           // 5s window to arm
    if (digitalRead(ARM_PIN) == LOW) break;
  }
  if (digitalRead(ARM_PIN) != LOW) {
    Serial.println("[HID] Not armed. Skipping typing.");
    return;
  }

  Serial.println("[HID] Armed. Typing in 3 seconds...");
  delay(3000);

  Keyboard.begin();

  for (uint16_t i = 0; i < len; i++) {
    uint8_t b = data[i];

    // keep it tame: printable + newline + tab
    if (b == '\n') {
      Keyboard.write(KEY_RETURN);
    } else if (b == '\t') {
      Keyboard.write('\t');
    } else if (b >= 32 && b <= 126) {
      Keyboard.write(b);
    } else {
      // skip other control bytes
    }
  }

  Keyboard.end();
  Serial.println("[HID] Done typing.");
}


void loop() {
  if (!msgReady) return;

  uint16_t len;
  bool of;

  noInterrupts();
  len = msgLen;
  of = overflowed;
  overflowed = false;

  if (len > BUF_SZ) len = BUF_SZ;
  for (uint16_t i = 0; i < len; i++) localBuf[i] = rxBuf[i];
  localBuf[len] = 0;
  msgReady = false;
  interrupts();

  Serial.println();
  Serial.print("[RX] len="); Serial.print(len);
  Serial.print(" sum16="); Serial.print(sum16(localBuf, len));
  if (of) Serial.print(" [OVERFLOW]");
  Serial.println();

  // Normalize CR->LF
  for (uint16_t i = 0; i < len; i++) if (localBuf[i] == '\r') localBuf[i] = '\n';

  // META verify (first line)
  char* firstNL = (char*)memchr(localBuf, '\n', len);
  if (firstNL) {
    *firstNL = 0;
    long expLen = -1, expSum = -1;

    if (sscanf((char*)localBuf, "REM META LEN=%ld SUM16=%ld", &expLen, &expSum) == 2) {
      uint8_t* payloadStart = (uint8_t*)(firstNL + 1);
      uint16_t payloadLen   = (uint16_t)(len - (payloadStart - localBuf));
      uint16_t payloadSum   = sum16(payloadStart, payloadLen);

      bool pass = ((long)payloadLen == expLen && (long)payloadSum == expSum);

      Serial.print("[META] expected len="); Serial.print(expLen);
      Serial.print(" sum16="); Serial.print(expSum);
      Serial.print(" | actual len="); Serial.print(payloadLen);
      Serial.print(" sum16="); Serial.print(payloadSum);
      Serial.println(pass ? "  ✅ PASS" : "  ❌ FAIL");

      // Restore the newline before we do anything slow
      *firstNL = '\n';

      // Only type if META passes (and only payload body)
      if (pass) {
        hid_type_payload_as_text(payloadStart, payloadLen);
      }
    } else {
      *firstNL = '\n';
    }
  }




  Serial.println("---- EVENTS ----");
  defaultDelayMs = 0;
  lastCmd[0] = 0;

  // Manual line split
  char* s = (char*)localBuf;
  char* end = s + len;

  while (s < end) {
    char* line = s;
    while (s < end && *s != '\n' && *s != 0) s++;
    if (s < end) { *s = 0; s++; } // terminate line
    char* t = trim(line);
    if (*t) simulate_line(t);
  }

  Serial.println("---- END ----");
  Serial.println("[DBG] done parsing");
}

