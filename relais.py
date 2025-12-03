from machine import Pin
import time

pin = Pin(4, Pin.OUT)

while True:
    pin.value(1)   # HIGH
    time.sleep(1)

    pin.value(0)   # LOW
    time.sleep(1)
