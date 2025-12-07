from machine import Pin, I2C
from time import sleep_ms

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
        sleep_ms(1)
        self.i2c.writeto(self.addr, bytes([byte]))
        sleep_ms(1)

    def init_lcd(self):
        sleep_ms(20)
        self.write_nibble(0x03, 0)
        sleep_ms(5)
        self.write_nibble(0x03, 0)
        sleep_ms(1)
        self.write_nibble(0x03, 0)
        self.write_nibble(0x02, 0)

        self.write_byte(0x28, 0)
        self.write_byte(0x0C, 0)
        self.write_byte(0x01, 0)
        sleep_ms(2)
        self.write_byte(0x06, 0)

    def clear(self):
        self.write_byte(0x01, 0)
        sleep_ms(2)

    def move_to(self, col, row):
        addr = col + (0x40 * row)
        self.write_byte(0x80 | addr, 0)

    def putstr(self, s):
        for c in s:
            self.write_byte(ord(c), 1)



i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
lcd = I2cLcd(i2c, 0x27, 2, 16)

while True:
    lcd.move_to(0, 0)
    lcd.putstr("Hallo Welt!")
    sleep_ms(2000)
    lcd.clear()

    lcd.move_to(0, 1)
    lcd.putstr("Adresse 0x27")
    sleep_ms(2000)
    lcd.clear()
