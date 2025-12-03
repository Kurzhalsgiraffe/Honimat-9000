from machine import Pin, I2C
from time import sleep_ms

# diese Varianten decken ALLE gängigen 1602IIC ohne sichtbaren Poti ab
PINMAPS = [
    # Klassisch
    {"RS":0,"RW":1,"EN":2,"BL":3,"D4":4,"D5":5,"D6":6,"D7":7},
    # Alternative Boards
    {"RS":0,"RW":2,"EN":1,"BL":3,"D4":4,"D5":5,"D6":6,"D7":7},
    {"RS":0,"RW":1,"EN":2,"BL":3,"D4":6,"D5":5,"D6":4,"D7":7},
    {"RS":1,"RW":2,"EN":3,"BL":0,"D4":4,"D5":5,"D6":6,"D7":7},
]

I2C_ADDR = 0x27
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

def writenibble(map, nib, mode=0):
    byte = 0
    pins = map
    if mode == 1:
        byte |= 1 << pins["RS"]
    if pins["BL"] >= 0:
        byte |= 1 << pins["BL"]
    # Bits zuordnen
    for i,bit in enumerate(["D4","D5","D6","D7"]):
        if nib & (1 << i):
            byte |= 1 << pins[bit]
    # Enable toggeln
    enable = 1 << map["EN"]
    i2c.writeto(I2C_ADDR, bytes([byte | enable]))
    sleep_ms(1)
    i2c.writeto(I2C_ADDR, bytes([byte]))
    sleep_ms(1)

def writebyte(map, value, mode=0):
    writenibble(map, (value >> 4) & 0x0F, mode)
    writenibble(map, value & 0x0F, mode)

def init(map):
    sleep_ms(20)
    writenibble(map, 0x03)
    sleep_ms(5)
    writenibble(map, 0x03)
    sleep_ms(1)
    writenibble(map, 0x03)
    writenibble(map, 0x02)

    writebyte(map, 0x28)  # 4-bit, 2-Zeilen
    writebyte(map, 0x0C)  # Display ON
    writebyte(map, 0x01)  # Clear
    sleep_ms(2)
    writebyte(map, 0x06)  # entry mode

def test_map(map):
    try:
        init(map)
        writebyte(map, 0x80)  # pos 0
        for c in "TEST MAP":
            writebyte(map, ord(c), 1)
        return True
    except:
        return False


print("Starte autodetect...")

for idx, m in enumerate(PINMAPS):
    print("Teste Mapping", idx+1)
    try:
        init(m)
        writebyte(m, 0x80)
        for c in ("Map %d" % (idx+1)):
            writebyte(m, ord(c), 1)
        print("→ Bitte Display prüfen!")
        sleep_ms(2000)
    except Exception as e:
        print("Fehler:", e)

print("Fertig. Merke dir, welche Map lesbaren Text zeigt.")
