from machine import ADC, Pin
import time

# ADC0 = GP26
poti = ADC(Pin(26))

while True:
    raw = poti.read_u16()       # Wert von 0 bis 65535
    print("Rohwert:", raw)
    time.sleep(0.1)
