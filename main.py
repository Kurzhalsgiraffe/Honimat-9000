from machine import ADC, I2C, Pin
import _thread
import time

# ===================== LCD CLASS =====================
class I2cLcd:
    RS = 0
    RW = 1
    EN = 2
    BL = 3
    D4 = 4
    D5 = 5
    D6 = 6
    D7 = 7

    def __init__(self, i2c, addr, lines=2, cols=16):
        self.i2c = i2c
        self.addr = addr
        self.lines = lines
        self.cols = cols
        self.backlight = True
        self.init_lcd()

    def write_byte(self, value, mode=0):
        self.write_nibble((value >> 4) & 0x0F, mode)
        self.write_nibble(value & 0x0F, mode)

    def write_nibble(self, nibble, mode):
        byte = 0
        if mode:
            byte |= 1 << self.RS
        if self.backlight:
            byte |= 1 << self.BL

        if nibble & 1: byte |= 1 << self.D4
        if nibble & 2: byte |= 1 << self.D5
        if nibble & 4: byte |= 1 << self.D6
        if nibble & 8: byte |= 1 << self.D7

        en = 1 << self.EN
        self.i2c.writeto(self.addr, bytes([byte | en]))
        time.sleep_ms(1)
        self.i2c.writeto(self.addr, bytes([byte]))
        time.sleep_ms(1)

    def init_lcd(self):
        time.sleep_ms(20)
        self.write_nibble(0x03, 0)
        time.sleep_ms(5)
        self.write_nibble(0x03, 0)
        time.sleep_ms(1)
        self.write_nibble(0x03, 0)
        self.write_nibble(0x02, 0)

        self.write_byte(0x28, 0)
        self.write_byte(0x0C, 0)
        self.write_byte(0x01, 0)
        time.sleep_ms(2)
        self.write_byte(0x06, 0)

    def clear(self):
        self.write_byte(0x01, 0)
        time.sleep_ms(2)

    def move_to(self, col, row):
        addr = col + (0x40 * row)
        self.write_byte(0x80 | addr, 0)

    def putstr(self, s):
        for c in s:
            self.write_byte(ord(c), 1)

# ===================== INIT LCD =====================
DISPLAY_I2C = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
LCD = I2cLcd(DISPLAY_I2C, 0x27, 2, 16)

# ===================== DAC / MOTOR =====================
MCP4725_ADDR = 0x60
MOTOR_I2C = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
EN_PIN = Pin(4, Pin.OUT)
FR_PIN = Pin(5, Pin.OUT)

LEVER = Pin(22, Pin.IN, Pin.PULL_DOWN)
POTI = ADC(Pin(26))
L_BUTTON = Pin(27, Pin.IN, Pin.PULL_UP)
R_BUTTON = Pin(28, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 200
MOTOR_RUNNING = False

# ===================== FLAG REQUESTS =====================
RUNNING_FLAG = False
RUNNING_REQUEST = False
MODE_REQUEST = False
MODE_PRESSED_FLAG = False
CURRENT_MODE = 0

MODES = ["Auto 100", "Auto 50", "Manuell"]

# ===================== DAC =====================
def write_dac(value: int):
    """ value: 0–4095 (12-bit DAC) """
    high = (value >> 4) & 0xFF
    low  = (value << 4) & 0xFF
    MOTOR_I2C.writeto(MCP4725_ADDR, bytes([0x40, high, low]))

# ===================== MOTOR CONTROL =====================
def enable_motor():
    EN_PIN.value(1)

def disable_motor():
    EN_PIN.value(0)

def set_motor_direction(direction):
    FR_PIN.value(0)
    time.sleep(0.1)
    if direction.lower() == "forward":
        FR_PIN.value(0)
    elif direction.lower() == "reverse":
        FR_PIN.value(1)
    else:
        raise ValueError("direction muss 'forward' oder 'reverse' sein")

def set_motor_speed(speed: int):
    val = int((speed / 100) * 4095)
    write_dac(val)

def gentle_break(current_speed):
    global MOTOR_RUNNING
    for j in range(current_speed,0,-1):
        set_motor_speed(int(j))
        time.sleep(0.1)
    disable_motor()
    MOTOR_RUNNING = False

# ===================== LCD DISPLAY =====================
def display_text(line1, line2):
    line1 = line1[:16]
    line2 = line2[:16]
    LCD.clear()
    LCD.move_to(0, 0)
    LCD.putstr(line1)
    LCD.move_to(0, 1)
    LCD.putstr(line2)

# ===================== ISR HANDLER =====================
last_start_stop = 0
last_mode_button = 0

def handle_start_stop_button(pin):
    global RUNNING_REQUEST, last_start_stop
    now = time.ticks_ms()
    if time.ticks_diff(now, last_start_stop) > DEBOUNCE_MS:
        RUNNING_REQUEST = True
        last_start_stop = now

def handle_mode_button(pin):
    global MODE_REQUEST, last_mode_button
    now = time.ticks_ms()
    if time.ticks_diff(now, last_mode_button) > DEBOUNCE_MS:
        MODE_REQUEST = True
        last_mode_button = now

L_BUTTON.irq(trigger=Pin.IRQ_FALLING, handler=handle_start_stop_button)
R_BUTTON.irq(trigger=Pin.IRQ_FALLING, handler=handle_mode_button)

# ===================== UTILS =====================
def get_poti_value() -> float:
    return POTI.read_u16() / 65535

def get_lever_position() -> str:
    return "left" if LEVER.value() == 0 else "right"

# ===================== MOTOR MODE 0 =====================
def run_motor_mode_0():
    global MOTOR_RUNNING, RUNNING_FLAG
    MOTOR_RUNNING = True
    enable_motor()
    set_motor_direction("forward")

    # ramp up
    for speed in range(25):
        if not RUNNING_FLAG:
            gentle_break(speed)
            return
        set_motor_speed(speed)
        time.sleep(0.1)

    # 10 Sekunden
    for _ in range(100):
        if not RUNNING_FLAG:
            gentle_break(25)
            return
        time.sleep(0.1)

    # ramp down
    for j in range(25,0,-1):
        set_motor_speed(j)
        time.sleep(0.1)

    # reverse
    set_motor_direction("reverse")
    for speed in range(25):
        if not RUNNING_FLAG:
            gentle_break(speed)
            return
        set_motor_speed(speed)
        time.sleep(0.1)

    for _ in range(100):
        if not RUNNING_FLAG:
            gentle_break(25)
            return
        time.sleep(0.1)

    for j in range(25,0,-1):
        set_motor_speed(j)
        time.sleep(0.1)

    disable_motor()
    MOTOR_RUNNING = False
    RUNNING_FLAG = False

# ===================== MAIN LOOP =====================
last_displayed_mode = None

while True:
    # ===== HANDLE REQUESTS =====
    if RUNNING_REQUEST:
        RUNNING_REQUEST = False
        RUNNING_FLAG = not RUNNING_FLAG

    if MODE_REQUEST:
        MODE_REQUEST = False
        if MOTOR_RUNNING:
            display_text("Nicht moeglich", "Programm laeuft")
            time.sleep(3)
            last_displayed_mode = None
        else:
            CURRENT_MODE = (CURRENT_MODE + 1) % len(MODES)
    
    current_display = MODES[CURRENT_MODE % len(MODES)]

    # Update LCD only if changed
    if last_displayed_mode != current_display:
        display_text("Modus", current_display)
        last_displayed_mode = current_display

    # Motor starten
    if RUNNING_FLAG and not MOTOR_RUNNING:
        if CURRENT_MODE == 0:
            _thread.start_new_thread(run_motor_mode_0, ())

    time.sleep(0.05)
