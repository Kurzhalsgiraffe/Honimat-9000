from machine import ADC, I2C, Pin
import time

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

DISPLAY_I2C = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
LCD = I2cLcd(DISPLAY_I2C, 0x27, 2, 16)

MCP4725_ADDR = 0x60
MOTOR_I2C = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
EN_PIN = Pin(4, Pin.OUT)
FR_PIN = Pin(5, Pin.OUT)

LEVER = Pin(22, Pin.IN, Pin.PULL_DOWN)
POTI = ADC(Pin(26))
L_BUTTON = Pin(27, Pin.IN, Pin.PULL_UP)
R_BUTTON = Pin(28, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 250
SPEED = 0 # 0 -> 100
RUNNING = False
LAST_START_STOP_BUTTON_INTERACTION = 0
LAST_MODE_BUTTON_INTERACTION = 0

def write_dac(value: int):
    """
    value: 0–4095 (12-bit DAC)
    """
    # MCP4725 erwartet:
    #   0x40 als Command-Byte für 'Write DAC register'
    #   dann HighByte und LowByte
    high = (value >> 4) & 0xFF
    low  = (value << 4) & 0xFF
    MOTOR_I2C.writeto(MCP4725_ADDR, bytes([0x40, high, low]))

# =================================================================================

def enable_motor():
    """Motor einschalten"""
    EN_PIN.value(1)

def disable_motor():
    """Motor ausschalten"""
    EN_PIN.value(0)

def set_motor_direction(direction):
    """
    Richtung setzen:
    direction = "forward" oder "reverse"
    Motor muss vorher gestoppt sein (disable)
    """
    FR_PIN.value(0)
    time.sleep(0.1)   # kleine Pause für Sicherheit

    if direction.lower() == "forward":
        FR_PIN.value(0)
    elif direction.lower() == "reverse":
        FR_PIN.value(1)
    else:
        raise ValueError("direction muss 'forward' oder 'reverse' sein")

def set_motor_speed(speed: int):
    """Set motor speed immediately (0–100)."""
    global SPEED
    val = int((speed / 100) * 4095)  # Convert 0–100% to 0–4095
    write_dac(val)
    SPEED = speed

def ramp_to_speed(desired_speed: float, duration: float = 2.0):
    """
    Gradually ramp motor speed to desired_speed over given duration.
    :param desired_speed: Target speed (0–100)
    :param duration: Total time to reach target speed in seconds
    """
    global SPEED
    start_speed = SPEED
    steps = int(abs(desired_speed - start_speed))  # number of increments
    if steps == 0:
        return  # already at desired speed

    step_delay = duration / steps

    # Determine ramp direction
    step_sign = 1 if desired_speed > start_speed else -1

    for i in range(steps):
        SPEED += step_sign
        set_motor_speed(int(SPEED))
        time.sleep(step_delay)

# =================================================================================

def handle_start_stop_button(pin):
    global RUNNING, LAST_START_STOP_BUTTON_INTERACTION

    now = time.ticks_ms()
    if time.ticks_diff(now, LAST_START_STOP_BUTTON_INTERACTION) < DEBOUNCE_MS:
        return
    LAST_START_STOP_BUTTON_INTERACTION = now

    RUNNING = not RUNNING
    print("RUNNING =", RUNNING)

def handle_mode_button(pin):
    global LAST_MODE_BUTTON_INTERACTION

    now = time.ticks_ms()
    if time.ticks_diff(now, LAST_MODE_BUTTON_INTERACTION) < DEBOUNCE_MS:
        return
    LAST_MODE_BUTTON_INTERACTION = now

    print("lever: ",get_lever_position())
    print("poto: ",get_poti_value())
    print("Mode Pressed")

def get_poti_value() -> float:
    raw = POTI.read_u16()
    return raw / 65535

def get_lever_position() -> str:
    return "left" if LEVER.value() == 0 else "right"

# =================================================================================

L_BUTTON.irq(trigger=Pin.IRQ_FALLING, handler=handle_start_stop_button)
R_BUTTON.irq(trigger=Pin.IRQ_FALLING, handler=handle_mode_button)


while True:
    LCD.move_to(0, 0)
    LCD.putstr("Hallo Welt!")
    time.sleep(2)
    LCD.clear()

    LCD.move_to(0, 1)
    LCD.putstr("Adresse 0x27")
    time.sleep(2)
    LCD.clear()

# try:
#     enable_motor()

#     print("Motor vorwärts 25%")
#     set_motor_direction("forward")
#     ramp_to_speed(25, duration=2)
#     time.sleep(10)
#     ramp_to_speed(0, duration=2)

#     print("Motor rückwärts 25%")
#     set_motor_direction("reverse")
#     ramp_to_speed(25, duration=2)
#     time.sleep(10)
#     ramp_to_speed(0, duration=2)

#     print("Motor vorwärts 50%")
#     set_motor_direction("forward")
#     ramp_to_speed(50, duration=4)
#     time.sleep(10)
#     ramp_to_speed(0, duration=4)

#     print("Motor rückwärts 50%")
#     set_motor_direction("reverse")
#     ramp_to_speed(50, duration=4)
#     time.sleep(10)
#     ramp_to_speed(0, duration=4)

#     print("Motor vorwärts 75%")
#     set_motor_direction("forward")
#     ramp_to_speed(75, duration=6)
#     time.sleep(10)
#     ramp_to_speed(0, duration=6)

#     print("Motor rückwärts 75%")
#     set_motor_direction("reverse")
#     ramp_to_speed(75, duration=6)
#     time.sleep(10)
#     ramp_to_speed(0, duration=6)

#     print("Motor vorwärts 100%")
#     set_motor_direction("forward")
#     ramp_to_speed(100, duration=8)
#     time.sleep(10)
#     ramp_to_speed(0, duration=8)

#     print("Motor rückwärts 100%")
#     set_motor_direction("reverse")
#     ramp_to_speed(100, duration=8)
#     time.sleep(10)
#     ramp_to_speed(0, duration=8)

# finally:
#     # Motor stoppen und Pins freigeben
#     disable_motor()
#     FR_PIN.value(0)
#     print("Motor gestoppt")
