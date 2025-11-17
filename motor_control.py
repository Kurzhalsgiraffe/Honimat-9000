from machine import Pin, I2C
import time

MCP4725_ADDR = 0x60
SPEED = 0 # 0 -> 100

FR_PIN = Pin(4, Pin.IN)  # Forward/Reverse initial High-Z
EN_PIN = Pin(5, Pin.IN)  # Enable initial High-Z

# I2C initialisieren (für Pico 2: I2C1 -> SDA=Pin 2, SCL=Pin 3)
i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)

def write_dac(value: int):
    """
    value: 0–4095 (12-bit DAC)
    """
    # MCP4725 erwartet:
    #   0x40 als Command-Byte für 'Write DAC register'
    #   dann HighByte und LowByte
    high = (value >> 4) & 0xFF
    low  = (value << 4) & 0xFF
    i2c.writeto(MCP4725_ADDR, bytes([0x40, high, low]))

def set_open(pin):
    """Setzt den Pin auf High-Z (Input, kein Pull-Up)"""
    pin.init(Pin.IN)

def pull_gnd(pin):
    """Zieht den Pin auf GND (Output Low)"""
    pin.init(Pin.OUT)
    pin.value(0)

# =================================================================================

def enable_motor():
    """Motor einschalten"""
    pull_gnd(EN_PIN)

def disable_motor():
    """Motor ausschalten"""
    set_open(EN_PIN)

def set_motor_direction(direction):
    """
    Richtung setzen:
    direction = "forward" oder "reverse"
    Motor muss vorher gestoppt sein (disable)
    """
    set_open(FR_PIN)  # zuerst auf High-Z
    time.sleep(0.1)   # kleine Pause für Sicherheit

    if direction.lower() == "forward":
        set_open(FR_PIN)  # offen = forward
    elif direction.lower() == "reverse":
        pull_gnd(FR_PIN)  # GND = reverse
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


try:
    enable_motor()

    print("Motor vorwärts 25%")
    set_motor_direction("forward")
    ramp_to_speed(25, duration=2)
    time.sleep(10)
    ramp_to_speed(0, duration=2)

    print("Motor rückwärts 25%")
    set_motor_direction("reverse")
    ramp_to_speed(25, duration=2)
    time.sleep(10)
    ramp_to_speed(0, duration=2)

    print("Motor vorwärts 50%")
    set_motor_direction("forward")
    ramp_to_speed(50, duration=4)
    time.sleep(10)
    ramp_to_speed(0, duration=4)

    print("Motor rückwärts 50%")
    set_motor_direction("reverse")
    ramp_to_speed(50, duration=4)
    time.sleep(10)
    ramp_to_speed(0, duration=4)

    print("Motor vorwärts 75%")
    set_motor_direction("forward")
    ramp_to_speed(75, duration=6)
    time.sleep(10)
    ramp_to_speed(0, duration=6)

    print("Motor rückwärts 75%")
    set_motor_direction("reverse")
    ramp_to_speed(75, duration=6)
    time.sleep(10)
    ramp_to_speed(0, duration=6)

    print("Motor vorwärts 100%")
    set_motor_direction("forward")
    ramp_to_speed(100, duration=8)
    time.sleep(10)
    ramp_to_speed(0, duration=8)

    print("Motor rückwärts 100%")
    set_motor_direction("reverse")
    ramp_to_speed(100, duration=8)
    time.sleep(10)
    ramp_to_speed(0, duration=8)

finally:
    # Motor stoppen und Pins freigeben
    disable_motor()
    set_open(FR_PIN)
    print("Motor gestoppt")
