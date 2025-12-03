from machine import Pin
import time

button = Pin(22, Pin.IN, Pin.PULL_UP)

while True:
    if button.value() == 0:     # 0 = gedrückt
        print("Button gedrückt!")
    else:
        print("Button nicht gedrückt.")
    
    time.sleep(0.1)
