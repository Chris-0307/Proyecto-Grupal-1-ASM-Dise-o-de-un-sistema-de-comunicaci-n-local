# tx_fsk.py — Transmisor BFSK con PWM (MicroPython, RP2040)
from machine import Pin, PWM
import time

# ====== Parámetros ======
TX_PIN = 16                # GP16 -> cable -> GP15 del RX
BIT_RATE = 25
Tbit_ms = int(1000 / BIT_RATE)

BANDS = [
    (1200, 500),
    (2000, 500),  
    (2800, 500),
]
BAND_INDEX = 1
fc, dev = BANDS[BAND_INDEX]
f0 = fc - dev
f1 = fc + dev


BEACON_MS = 800     
PREAMBLE_REP = 24    
SEND_PERIOD_S = 5.0   
AUTO_MSG = "H"

# ====== PWM ======
pwm = PWM(Pin(TX_PIN))
pwm.duty_u16(0)  # apagado al inicio

def _tone_pwm(freq_hz: int, dur_ms: int):
    if freq_hz <= 0 or dur_ms <= 0:
        pwm.duty_u16(0)
        time.sleep_ms(max(1, dur_ms))
        return
    pwm.freq(freq_hz)          # el hardware hace la frecuencia exacta
    pwm.duty_u16(32768)        # ~50% duty
    time.sleep_ms(dur_ms)
    pwm.duty_u16(0)            # silencio entre segmentos (evita colas)

def send_bit(b: int):
    _tone_pwm(f1 if b else f0, Tbit_ms)

def send_byte(byte_val: int):
    for i in range(8):  # LSB primero
        send_bit((byte_val >> i) & 1)

def send_preamble(rep=PREAMBLE_REP):
    for _ in range(rep):
        send_byte(0x55)  # 01010101

def checksum_xor(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c


def send_frame(payload_ascii: str):
    data = payload_ascii.encode('ascii')
    _tone_pwm(f1, BEACON_MS)  # beacon
    _tone_pwm(0, 40)          # ← gap de 40 ms para separar del preámbulo
    send_preamble(PREAMBLE_REP)
    SYNC = 0x7E
    print("TX envia SYNC (0x7E), LEN =", len(data), "bytes =", list(data))

    send_byte(SYNC)
    send_byte(len(data))
    for b in data:
        send_byte(b)
    chk = checksum_xor(bytes([SYNC, len(data)]) + data)
    send_byte(chk)



# TX: usa la trama completa (beacon + preámbulo + SYNC/LEN/PAYLOAD/CHK)
def send_message_loop():
    try:
        while True:
            print(f"Enviando: {AUTO_MSG} (fc={fc}, f0={f0}, f1={f1}, Rb={BIT_RATE})")
            send_frame(AUTO_MSG)        # ← ¡esto ya incluye BEACON y PREAMBLE!
            time.sleep(SEND_PERIOD_S)
    except KeyboardInterrupt:
        pwm.duty_u16(0)

if __name__ == "__main__":
    send_message_loop()
