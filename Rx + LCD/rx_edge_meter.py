# rx_edge_meter.py (RX) -- estima frecuencia en GP15
from machine import Pin
import time

rx = Pin(15, Pin.IN, Pin.PULL_DOWN)  # misma config que tu RX
def quick_edge_freq(ms=500):
    start = time.ticks_us()
    prev = rx.value()
    edges = 0
    while time.ticks_diff(time.ticks_us(), start) < ms*1000:
        v = rx.value()
        if v != prev:
            edges += 1
            prev = v
    cyc = edges // 2
    return (cyc * 1000) // ms

while True:
    f = quick_edge_freq(500)
    print("GP15 ~", f, "Hz")
    time.sleep_ms(500)
