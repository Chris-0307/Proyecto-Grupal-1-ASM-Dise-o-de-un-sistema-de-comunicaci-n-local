from machine import Pin
import time
p = Pin(16, Pin.OUT)
def tone(freq, ms):
    half = max(1, int(500_000 // freq))
    cycles = (ms*1000) // (2*half)
    v = 0
    for _ in range(cycles):
        v^=1; p.value(v); time.sleep_us(half)
        v^=1; p.value(v); time.sleep_us(half)
    p.value(0)
while True:
    tone(1000,1000); time.sleep_ms(200)
    tone(2000,1000); time.sleep_ms(200)
    tone(500,1000);  time.sleep_ms(600)
