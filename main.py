from machine import ADC, I2C, Pin
import _thread
import time

# ===================== LCD =====================
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

    def putchar(self, c):
        self.write_byte(ord(c), 1)

    def putstr(self, s):
        for c in s:
            self.putchar(c)

# ===================== THREAD-SAFE DISPLAY =====================
lcd_lock = _thread.allocate_lock()

class Display:
    def __init__(self, mode:str, speed:int, direction:str) -> None:
        self.mode = mode
        self.speed = speed
        self.direction = direction

        self.display_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        self.lcd = I2cLcd(self.display_i2c, 0x27, 2, 16)

    def safe_lcd_write(self, func, *args, **kwargs):
        global DISPLAY_BUSY
        if DISPLAY_BUSY:
            return  # Display ist gesperrt
        with lcd_lock:
            func(*args, **kwargs)

    def display_text(self, line1, line2):
        self.safe_lcd_write(self._display_text_impl, line1, line2)

    def _display_text_impl(self, line1, line2):
        self.lcd.clear()
        self.lcd.move_to(0, 0)
        self.lcd.putstr(line1[:16])
        self.lcd.move_to(0, 1)
        self.lcd.putstr(line2[:16])

    def display_menu(self):
        mode_fmt = (self.mode + " " * 7)[:7]
        speed_fmt = ("%02d" % min(abs(self.speed), 99)) if self.speed > 0 else "--"
        arrow = "<-" if self.direction == "left" else ("->" if self.direction == "right" else "  ")
        dir_char = "L" if self.direction == "left" else ("R" if self.direction == "right" else "-")

        header = "Modus    %    " + arrow
        line   = "{} | {} | {}".format(mode_fmt, speed_fmt, dir_char)

        self._display_text_impl(header, line)

    def display_error(self, msg1, msg2, duration=3):
        global DISPLAY_BUSY
        DISPLAY_BUSY = True

        with lcd_lock:
            self.lcd.clear()
            self.lcd.move_to(0, 0)
            self.lcd.putstr(msg1[:16])
            self.lcd.move_to(0, 1)
            self.lcd.putstr(msg2[:16])
        
        time.sleep(duration)

        with lcd_lock:
            self.lcd.clear()
            self.display_menu()

        DISPLAY_BUSY = False

    def update_mode(self, mode):
        mode_fmt = (mode + " " * 7)[:7]
        self.lcd.move_to(0, 1)
        self.lcd.putstr(mode_fmt)

    def update_speed(self, speed):
        old_fmt = ("%02d" % min(abs(self.speed), 99)) if self.speed > 0 else "--"
        new_fmt = ("%02d" % min(abs(speed), 99)) if speed > 0 else "--"

        for i, (old_c, new_c) in enumerate(zip(old_fmt, new_fmt)):
            if old_c != new_c:
                self.lcd.move_to(10 + i, 1)
                self.lcd.putchar(new_c)

    def update_direction(self, direction):
        arrow = "<-" if direction == "left" else ("->" if direction == "right" else "  ")
        dir_char = "L" if direction == "left" else ("R" if direction == "right" else "-")

        self.lcd.move_to(15, 1)
        self.lcd.putstr(dir_char)
        self.lcd.move_to(14, 0)
        self.lcd.putstr(arrow)

    def set_mode(self, mode):
        self.mode = mode
        self.safe_lcd_write(self.update_mode, mode)

    def set_speed(self, speed):
        self.safe_lcd_write(self.update_speed, speed)
        self.speed = speed

    def set_direction(self, direction):
        self.safe_lcd_write(self.update_direction, direction)

# ===================== DAC / MOTOR =====================
MCP4725_ADDR = 0x60
MOTOR_I2C = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
EN_PIN = Pin(4, Pin.OUT)
FR_PIN = Pin(5, Pin.OUT)

LEVER = Pin(22, Pin.IN, Pin.PULL_DOWN)
POTI = ADC(Pin(26))
L_BUTTON = Pin(27, Pin.IN, Pin.PULL_UP)
R_BUTTON = Pin(28, Pin.IN, Pin.PULL_UP)

STATUS_LED = Pin(7, Pin.OUT)

DEBOUNCE_MS = 300
MOTOR_RAMP_SLEEP_S = 0.25
TIME_BETWEEN_DIRECTIONS_S = 5
MOTOR_RUNNING = False
CURRENT_MOTOR_DIRECTION = None
DISPLAY_BUSY = False

# ===================== FLAG REQUESTS =====================
RUNNING_FLAG = False
RUNNING_REQUEST = False
MODE_REQUEST = False
MODE_PRESSED_FLAG = False
CURRENT_MODE = 0

MODES = ["A-4-100", "A-3-75", "Manuell"]

# ===================== Display Init =====================
DISPLAY = Display(MODES[0], 0, None)

# ===================== DAC =====================
def write_dac(value: int):
    high = (value >> 4) & 0xFF
    low  = (value << 4) & 0xFF
    MOTOR_I2C.writeto(MCP4725_ADDR, bytes([0x40, high, low]))

# ===================== MOTOR CONTROL =====================
def enable_motor():
    EN_PIN.value(1)

def disable_motor():
    EN_PIN.value(0)

def set_motor_direction(direction):
    global CURRENT_MOTOR_DIRECTION
    direction = direction.lower()
    if direction not in ("left", "right"):
        raise ValueError("direction must be 'right' or 'left'")

    if CURRENT_MOTOR_DIRECTION == direction:
        return  # Richtung schon korrekt, nichts tun

    FR_PIN.value(0 if direction == "right" else 1)
    CURRENT_MOTOR_DIRECTION = direction

def set_motor_speed(speed: int):
    val = int((speed / 100) * 4095)
    write_dac(val)

def safe_motor_ramp_up(current_speed:int, max_speed:int, direction:str, sleep_interval:float) -> bool:
    set_motor_direction(direction)
    DISPLAY.set_direction(direction)

    for speed in range(current_speed, max_speed+1):
        if not RUNNING_FLAG:
            gentle_break(speed)
            return False
        set_motor_speed(speed)
        DISPLAY.set_speed(speed)
        time.sleep(sleep_interval)
    return True

def motor_ramp_down(current_speed:int, desired_speed:int, sleep_interval:float):
    for speed in range(current_speed,desired_speed-1,-1):
        set_motor_speed(speed)
        DISPLAY.set_speed(speed)
        time.sleep(sleep_interval)
    DISPLAY.set_direction(None)

def gentle_break(current_speed):
    global MOTOR_RUNNING
    motor_ramp_down(current_speed, 0, MOTOR_RAMP_SLEEP_S)
    disable_motor()
    MOTOR_RUNNING = False

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
def get_poti_value() -> int:
    return int((POTI.read_u16() / 65535) * 100)

def get_lever_position() -> str:
    return "left" if LEVER.value() == 0 else "right"

# ===================== MOTOR AUTO MODES =====================
def run_motor_mode_0():
    global MOTOR_RUNNING, RUNNING_FLAG
    MOTOR_RUNNING = True
    enable_motor()
    hold_time_s = 60
    sleep_interval = 0.1
    speed_list = [25, 50, 75, 100]

    for max_speed in speed_list:
        # Right
        if not safe_motor_ramp_up(0, max_speed, "right", MOTOR_RAMP_SLEEP_S):
            return
        for _ in range(hold_time_s * (1/sleep_interval)):
            if not RUNNING_FLAG:
                gentle_break(max_speed)
                return
            time.sleep(sleep_interval)
        motor_ramp_down(max_speed, 0, MOTOR_RAMP_SLEEP_S)

        time.sleep(TIME_BETWEEN_DIRECTIONS_S)

        # Left
        if not safe_motor_ramp_up(0, max_speed, "left", MOTOR_RAMP_SLEEP_S):
            return
        for _ in range(hold_time_s * (1/sleep_interval)):
            if not RUNNING_FLAG:
                gentle_break(max_speed)
                return
            time.sleep(sleep_interval)
        motor_ramp_down(max_speed, 0, MOTOR_RAMP_SLEEP_S)

        if max_speed != speed_list[-1]:
            time.sleep(TIME_BETWEEN_DIRECTIONS_S)

    disable_motor()
    MOTOR_RUNNING = False
    RUNNING_FLAG = False

def run_motor_mode_1():
    global MOTOR_RUNNING, RUNNING_FLAG
    MOTOR_RUNNING = True
    enable_motor()
    hold_time_s = 60
    sleep_interval = 0.1
    speed_list = [25, 50, 75]

    for max_speed in speed_list:
        if not safe_motor_ramp_up(0, max_speed, "right", MOTOR_RAMP_SLEEP_S):
            return
        for _ in range(hold_time_s * (1/sleep_interval)):
            if not RUNNING_FLAG:
                gentle_break(max_speed)
                return
            time.sleep(sleep_interval)
        motor_ramp_down(max_speed, 0, MOTOR_RAMP_SLEEP_S)

        time.sleep(TIME_BETWEEN_DIRECTIONS_S)

        if not safe_motor_ramp_up(0, max_speed, "left", MOTOR_RAMP_SLEEP_S):
            return
        for _ in range(hold_time_s * (1/sleep_interval)):
            if not RUNNING_FLAG:
                gentle_break(max_speed)
                return
            time.sleep(sleep_interval)
        motor_ramp_down(max_speed, 0, MOTOR_RAMP_SLEEP_S)

        if max_speed != speed_list[-1]:
            time.sleep(TIME_BETWEEN_DIRECTIONS_S)

    disable_motor()
    MOTOR_RUNNING = False
    RUNNING_FLAG = False

# ===================== MOTOR MANUAL MODE =====================
def run_motor_manual(current_speed, current_direction):
    global MOTOR_RUNNING, RUNNING_FLAG
    MOTOR_RUNNING = True
    enable_motor()
    speed = 0
    
    # -- initial ramp up
    set_motor_direction(current_direction)
    DISPLAY.set_direction(current_direction)

    while speed != current_speed:
        if not RUNNING_FLAG:
            gentle_break(speed)
            return
        
        if speed < current_speed:
            speed += 1

        set_motor_speed(speed)
        DISPLAY.set_speed(speed)
        time.sleep(MOTOR_RAMP_SLEEP_S)

        current_speed = get_poti_value()
    # --

    while RUNNING_FLAG:
        speed = get_poti_value()
        direction = get_lever_position()

        # Richtungswechsel
        if direction != current_direction:
            motor_ramp_down(current_speed, 0, MOTOR_RAMP_SLEEP_S)
            time.sleep(TIME_BETWEEN_DIRECTIONS_S)
            direction = get_lever_position()
            current_speed = 0
            current_direction = direction
            set_motor_direction(current_direction)
            DISPLAY.set_direction(current_direction)

        # Speed-Anpassung
        if speed > current_speed:
            if not safe_motor_ramp_up(current_speed, speed, current_direction, MOTOR_RAMP_SLEEP_S):
                return
        elif speed < current_speed:
            motor_ramp_down(current_speed, speed, MOTOR_RAMP_SLEEP_S)

        # Nach der Rampenlogik erst current_speed aktualisieren
        current_speed = speed

        time.sleep(0.05)

    motor_ramp_down(current_speed, 0, MOTOR_RAMP_SLEEP_S)

    MOTOR_RUNNING = False
    RUNNING_FLAG = False
    disable_motor()

# ===================== MAIN LOOP =====================
DISPLAY.display_menu()
last_displayed_mode = None
manual_speed = None
manual_direction = None

while True:
    STATUS_LED.value(1 if MOTOR_RUNNING else 0)
    
    # ===== HANDLE REQUESTS =====
    if RUNNING_REQUEST:
        RUNNING_REQUEST = False
        RUNNING_FLAG = not RUNNING_FLAG

    if MODE_REQUEST:
        MODE_REQUEST = False
        if MOTOR_RUNNING:
            DISPLAY.display_error("Nicht moeglich", "Programm laeuft")
            last_displayed_mode = None
        else:
            CURRENT_MODE = (CURRENT_MODE + 1) % len(MODES)

    
    current_mode = MODES[CURRENT_MODE % len(MODES)]

    # Update LCD only if changed
    if last_displayed_mode != current_mode:
        DISPLAY.set_mode(current_mode)
        last_displayed_mode = current_mode

    # ===== MANUAL MODE DISPLAY =====
    if CURRENT_MODE == 2:  # manual mode
        manual_speed = get_poti_value()
        manual_direction = get_lever_position()
        DISPLAY.set_speed(manual_speed)
        DISPLAY.set_direction(manual_direction)

        if RUNNING_FLAG and not MOTOR_RUNNING:
            _thread.start_new_thread(run_motor_manual, (manual_speed, manual_direction))

    # ===== AUTOMATIC MODES =====
    else:
        if not RUNNING_FLAG and not MOTOR_RUNNING:
            DISPLAY.set_speed(0)
            DISPLAY.set_direction(None)
        if RUNNING_FLAG and not MOTOR_RUNNING:
            if CURRENT_MODE == 0:
                _thread.start_new_thread(run_motor_mode_0, ())
            elif CURRENT_MODE == 1:
                _thread.start_new_thread(run_motor_mode_1, ())

    time.sleep(0.05)
