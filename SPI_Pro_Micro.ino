#include <Arduino.h>
#include <avr/interrupt.h>
#include <ctype.h>
#include <string.h>
#include <Keyboard.h>

static const int ARM_PIN = 2;            // D2 -> GND to arm
static const int LED_PIN = LED_BUILTIN;  // on-board LED

static bool hid_allowed = true;          // disabled if ARM held at boot

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

static void apply_default_delay() {
  if (defaultDelayMs > 0) delay((unsigned long)defaultDelayMs);
}

// ---------- KEY NAME -> HID mapping ----------
static uint8_t keycode_for_name(const char* tok) {
  // common specials
  if (!strcmp(tok, "ENTER"))     return KEY_RETURN;
  if (!strcmp(tok, "TAB"))       return KEY_TAB;
  if (!strcmp(tok, "ESC"))       return KEY_ESC;
  if (!strcmp(tok, "ESCAPE"))    return KEY_ESC;
  if (!strcmp(tok, "BACKSPACE")) return KEY_BACKSPACE;
  if (!strcmp(tok, "DELETE"))    return KEY_DELETE;
  if (!strcmp(tok, "SPACE"))     return ' ';

  // arrows
  if (!strcmp(tok, "UP"))    return KEY_UP_ARROW;
  if (!strcmp(tok, "DOWN"))  return KEY_DOWN_ARROW;
  if (!strcmp(tok, "LEFT"))  return KEY_LEFT_ARROW;
  if (!strcmp(tok, "RIGHT")) return KEY_RIGHT_ARROW;

  // nav
  if (!strcmp(tok, "HOME"))     return KEY_HOME;
  if (!strcmp(tok, "END"))      return KEY_END;
  if (!strcmp(tok, "PAGEUP"))   return KEY_PAGE_UP;
  if (!strcmp(tok, "PAGEDOWN")) return KEY_PAGE_DOWN;

  // function keys
  if (tok[0] == 'F' && isdigit((unsigned char)tok[1])) {
    int n = atoi(tok + 1);
    if (n >= 1 && n <= 12) return (uint8_t)(KEY_F1 + (n - 1));
  }

  // single-char key names like "Y"
  if (tok[0] && !tok[1]) {
    char c = tok[0];
    if (isalpha((unsigned char)c)) return (uint8_t)tolower((unsigned char)c);
    if (isdigit((unsigned char)c)) return (uint8_t)c;
  }

  // fallthrough: try first char if printable
  if (tok[0] && tok[1] == 0 && tok[0] >= 32 && tok[0] <= 126) return (uint8_t)tok[0];

  return 0; // unknown
}

static bool is_modifier(const char* tok, uint8_t& modKey) {
  if (!strcmp(tok, "CTRL") || !strcmp(tok, "CONTROL")) { modKey = KEY_LEFT_CTRL; return true; }
  if (!strcmp(tok, "SHIFT"))                            { modKey = KEY_LEFT_SHIFT; return true; }
  if (!strcmp(tok, "ALT") || !strcmp(tok, "OPTION"))    { modKey = KEY_LEFT_ALT; return true; }
  if (!strcmp(tok, "GUI") || !strcmp(tok, "WINDOWS") || !strcmp(tok, "WIN") || !strcmp(tok, "COMMAND")) {
    modKey = KEY_LEFT_GUI; return true;
  }
  return false;
}

// ---------- safety / arming ----------
static bool armed_for_this_payload() {
  if (!hid_allowed) return false;

  // If already held, execute immediately
  if (digitalRead(ARM_PIN) == LOW) return true;

  Serial.println("[HID] Hold ARM (D2->GND) within 5s to EXECUTE...");
  unsigned long start = millis();
  while (millis() - start < 5000) {
    if (digitalRead(ARM_PIN) == LOW) return true;
  }
  return false;
}

// ---------- HID executor ----------
static void hid_press_and_release(uint8_t k) {
  if (!k) return;
  Keyboard.press(k);
  delay(5);
  Keyboard.release(k);
}

static void hid_exec_combo(char* lineUpper) {
  // Parse tokens from uppercase line: MOD MOD KEY [KEY...]
  uint8_t mods[6];
  uint8_t modCount = 0;

  uint8_t keys[6];
  uint8_t keyCount = 0;

  char* p = lineUpper;
  while (*p) {
    while (*p == ' ') p++;
    if (!*p) break;

    char* tok = p;
    while (*p && *p != ' ') p++;
    if (*p) { *p = 0; p++; }
    if (!*tok) continue;

    uint8_t mk = 0;
    if (is_modifier(tok, mk)) {
      if (modCount < 6) mods[modCount++] = mk;
      continue;
    }

    // normalize a couple names
    if (!strcmp(tok, "RETURN")) tok = (char*)"ENTER";
    if (!strcmp(tok, "DEL"))    tok = (char*)"DELETE";

    uint8_t kc = keycode_for_name(tok);
    if (kc && keyCount < 6) keys[keyCount++] = kc;
  }

  if (keyCount == 0 && modCount > 0) {
    Serial.println("[HID][WARN] Modifiers with no key");
    apply_default_delay();
    return;
  }

  // Hold modifiers
  for (uint8_t i = 0; i < modCount; i++) Keyboard.press(mods[i]);

  // Press keys (or write chars)
  for (uint8_t i = 0; i < keyCount; i++) {
    uint8_t k = keys[i];
    // For printable ascii, press/release works fine
    Keyboard.press(k);
  }
  delay(10);

  // Release everything
  Keyboard.releaseAll();

  apply_default_delay();
}

static void hid_exec_line(const char* raw) {
  char lineBuf[140];
  strncpy(lineBuf, raw, sizeof(lineBuf) - 1);
  lineBuf[sizeof(lineBuf) - 1] = 0;

  char* line = trim(lineBuf);
  if (!*line) return;

  // Comments
  if (!strncmp(line, "REM ", 4)) return;

  // Save for REPEAT
  strncpy(lastCmd, line, sizeof(lastCmd) - 1);
  lastCmd[sizeof(lastCmd) - 1] = 0;

  toUpperCopy(line, upperLine, sizeof(upperLine));

  if (!strncmp(upperLine, "STRING ", 7)) {
    Keyboard.print(line + 7);  // original casing
    apply_default_delay();
    return;
  }

  if (!strncmp(upperLine, "DELAY ", 6)) {
    long ms = atol(upperLine + 6);
    delay((unsigned long)ms);
    apply_default_delay();
    return;
  }

  if (!strncmp(upperLine, "DEFAULT_DELAY ", 14) || !strncmp(upperLine, "DEFAULTDELAY ", 13)) {
    const char* sp = strchr(upperLine, ' ');
    defaultDelayMs = sp ? atol(sp + 1) : 0;
    return;
  }

  if (!strncmp(upperLine, "REPEAT ", 7)) {
    int n = atoi(upperLine + 7);
    if (n <= 0 || !lastCmd[0]) return;
    for (int i = 0; i < n; i++) hid_exec_line(lastCmd);
    return;
  }

  // Otherwise treat as combo / key
  hid_exec_combo(upperLine);
}

static void hid_execute_payload(const uint8_t* payload, uint16_t len) {
  digitalWrite(LED_PIN, HIGH);
  Keyboard.begin();

  defaultDelayMs = 0;
  lastCmd[0] = 0;

  // Copy into a temp mutable buffer for splitting
  static char buf[BUF_SZ + 1];
  if (len > BUF_SZ) len = BUF_SZ;
  memcpy(buf, payload, len);
  buf[len] = 0;

  // Normalize CR->LF
  for (uint16_t i = 0; i < len; i++) if (buf[i] == '\r') buf[i] = '\n';

  char* s = buf;
  char* end = buf + len;

  while (s < end) {
    char* line = s;
    while (s < end && *s != '\n' && *s != 0) s++;
    if (s < end) { *s = 0; s++; }
    char* t = trim(line);
    if (*t) hid_exec_line(t);
  }

  Keyboard.end();
  digitalWrite(LED_PIN, LOW);
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

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  pinMode(SS, INPUT_PULLUP);
  pinMode(MISO, OUTPUT);
  pinMode(ARM_PIN, INPUT_PULLUP);

  if (digitalRead(ARM_PIN) == LOW) {
    hid_allowed = false;
    Serial.println("[HID] Disabled (ARM held at boot). Simulation-only.");
  } else {
    Serial.println("[HID] Ready (will require ARM hold per payload).");
  }

  SPCR = _BV(SPE) | _BV(SPIE);
  sei();

  Serial.println("SPI Ducky HID ready.");
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
  if (!firstNL) {
    Serial.println("[META] missing newline");
    return;
  }

  *firstNL = 0;
  long expLen = -1, expSum = -1;

  if (sscanf((char*)localBuf, "REM META LEN=%ld SUM16=%ld", &expLen, &expSum) != 2) {
    *firstNL = '\n';
    Serial.println("[META] header missing or invalid");
    return;
  }

  uint8_t* payloadStart = (uint8_t*)(firstNL + 1);
  uint16_t payloadLen   = (uint16_t)(len - (payloadStart - localBuf));
  uint16_t payloadSum   = sum16(payloadStart, payloadLen);

  bool pass = ((long)payloadLen == expLen && (long)payloadSum == expSum);

  Serial.print("[META] expected len="); Serial.print(expLen);
  Serial.print(" sum16="); Serial.print(expSum);
  Serial.print(" | actual len="); Serial.print(payloadLen);
  Serial.print(" sum16="); Serial.print(payloadSum);
  Serial.println(pass ? "  ✅ PASS" : "  ❌ FAIL");

  *firstNL = '\n';

  if (!pass) return;

  // Execute only if armed
  if (armed_for_this_payload()) {
    Serial.println("[HID] ARMED. Executing payload...");
    delay(500); // tiny settle before typing
    hid_execute_payload(payloadStart, payloadLen);
    Serial.println("[HID] Done.");
  } else {
    Serial.println("[HID] Not armed. Skipping execution.");
  }
}

