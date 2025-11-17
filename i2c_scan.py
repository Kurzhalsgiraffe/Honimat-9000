from machine import Pin, I2C

i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
print("I2C scan:", i2c.scan())
