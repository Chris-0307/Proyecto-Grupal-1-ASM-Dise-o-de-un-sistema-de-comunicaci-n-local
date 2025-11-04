# rx_fsk_fft.py — Receptor BFSK con FFT (ulab) + LCD I2C (MicroPython, RP2040)
# Requiere: firmware MicroPython con 'ulab' integrado (np.fft.fft/ifft)
# Conecta: señal digital a GP15 (RX_PIN), LCD I2C a GP4/GP5 (0x27)

from machine import Pin, SoftI2C
import time
from pico_i2c_lcd import I2cLcd

try:
    from ulab import numpy as np
except Exception as e:
    raise RuntimeError("Este script requiere 'ulab' en MicroPython") from e


LAST_BIT = 0  


NOISE_FLOOR = 1.0  
DEBUG_PREAMBLE = False
BIT_RATE    = 25
SAMPLE_RATE = 12800    
NFFT        = 512
HOP = NFFT                      

SPREAD_HZ = 120        
MEASURE_TIME = 0.25      
PREAMBLE_REP = 12        
CALIB_DONE = False

# Ventana Hann (fallback manual por si no existe np.hanning en tu build)
def hann(N):
    n = np.arange(N)
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * n / (N - 1))
try:
    WIN = np.hanning(NFFT)       # algunos builds lo traen
except Exception:
    WIN = hann(NFFT)

# Candidatas de banda (puedes agregar más pares f0/f1 para “más mensajes” a futuro)
# Formato: (fc, dev)
BANDS = [
    (2000, 500),   # f0=1500, f1=2500
    # (1200, 500),
    # (2800, 500),
]

# Trama (idéntica a la usada en TX y en tu simulador de PC)
PREAMBLE_BYTE = 0x55
SYNC          = 0x7E

# LCD
LCD_ADDR = 0x27
LCD_ROWS, LCD_COLS = 2, 16

# ========= Pines =========
RX_PIN = 15
rx = Pin(RX_PIN, Pin.IN, Pin.PULL_DOWN)

i2c = SoftI2C(sda=Pin(4), scl=Pin(5), freq=400000)
lcd = I2cLcd(i2c, LCD_ADDR, LCD_ROWS, LCD_COLS)

def lcd_msg(line1="", line2=""):
    lcd.clear()
    lcd.move_to(0,0); lcd.putstr((line1 or "")[:LCD_COLS])
    lcd.move_to(0,1); lcd.putstr((line2 or "")[:LCD_COLS])

# ========= Utilidades =========
def checksum_xor(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c

def byte_to_bits_lsb_first(b: int):
    return [(b >> i) & 1 for i in range(8)]

def idx_for_freq(f_hz):
    """Índice de bin para frecuencia f_hz dado SAMPLE_RATE y NFFT."""
    k = int(round(f_hz * NFFT / SAMPLE_RATE))
    # limitar a rango de mitad positiva [0..NFFT//2]
    k = max(0, min(NFFT//2, k))
    return k


def band_power_bins(fft_mag2_pos, f_center, spread_hz=SPREAD_HZ):
    dk = max(2, int(round(spread_hz * NFFT / SAMPLE_RATE)))  # al menos ±2 bins
    kc = idx_for_freq(f_center)
    k0 = max(0, kc - dk)
    k1 = min(NFFT//2, kc + dk)
    return float(np.sum(fft_mag2_pos[k0:k1+1]))

def acquire_block(buf):
    """
    Adquiere NFFT muestras a SAMPLE_RATE con bucle cronometrado.
    Para enlaces alámbricos y BFSK a ~kHz suele bastar. Para SR más altos, usar PIO.
    """
    dt_us = int(round(1_000_000 / SAMPLE_RATE))  # evita drift por truncado

    tnext = time.ticks_us()
    for i in range(NFFT):
        while time.ticks_diff(tnext, time.ticks_us()) > 0:
            pass
        buf[i] = rx.value()  # 0/1
        tnext = time.ticks_add(tnext, dt_us)


SWAP_DETECT = False  # si True, invierte E0/E1 al decidir
static_swap = None  # ← definida a nivel global




def decide_bit_fft(f0, f1, bit_duration_s):
    global LAST_BIT, SWAP_DETECT
    # 1 bloque por bit cuando Tbit ≈ NFFT/SR; si es mayor, ajusta
    blocks = max(1, int(round(bit_duration_s * SAMPLE_RATE / NFFT)))

    E0 = 0.0; E1 = 0.0
    temp = np.zeros(NFFT)
    for _ in range(blocks):
        acquire_block(temp)
        x  = (temp * 2.0) - 1.0
        x *= WIN
        X    = np.fft.fft(x)
        Xpos = X[:NFFT//2 + 1]
        mag2 = (Xpos.real * Xpos.real) + (Xpos.imag * Xpos.imag)
        E0  += band_power_bins(mag2, f0)
        E1  += band_power_bins(mag2, f1)

   
    if (E0 + E1) < NOISE_FLOOR:
        return -1, E0, E1


    margin = 1.15
    if E1 > E0 * margin:
        raw = 1
    elif E0 > E1 * margin:
        raw = 0
    else:
        raw = LAST_BIT

   
    b = raw ^ (1 if SWAP_DETECT else 0)
    LAST_BIT = b
    return b, E0, E1



def read_byte_fft(f0, f1):
    Tbit = 1.0 / BIT_RATE
    val = 0
    last = 0
    for i in range(8):
        # reintento corto si hay silencio
        for _ in range(3):
            b, e0, e1 = decide_bit_fft(f0, f1, Tbit)
            if b != -1:
                break
        if b == -1:
            b = last  # último recurso

        print(f"bit {i}: b={b}  E0={e0:.1f}  E1={e1:.1f}")
        last = b
        val |= (b & 1) << i   # LSB-first
    return val


def find_band_lock():
    """
    Escanea todas las BANDS y elige la 'más prometedora' midiendo
    potencia combinada en (f0, f1) durante un pequeño tiempo.
    """
    lcd_msg("Escaneando FFT", "buscando banda")
    best_idx = None
    best_pow = -1.0
    measure_time = MEASURE_TIME


    for idx, (fc, dev) in enumerate(BANDS):
        f0, f1 = fc - dev, fc + dev
        collected = 0.0
        total = 0.0
        block_time = NFFT / SAMPLE_RATE
        temp = np.zeros(NFFT)

        while collected + 1e-9 < measure_time:
            acquire_block(temp)
            x = (temp * 2.0) - 1.0
            xw = x * WIN
            X = np.fft.fft(xw)
            Xpos = X[:NFFT//2 + 1]
            mag2 = (Xpos.real * Xpos.real) + (Xpos.imag * Xpos.imag)
            total += band_power_bins(mag2, f0) + band_power_bins(mag2, f1)
            collected += block_time

        if total > best_pow:
            best_pow = total
            best_idx = idx

    fc, dev = BANDS[best_idx]
    lcd_msg("Banda bloqueada", f"fc~{fc}Hz")
    return best_idx



def wait_preamble(f0, f1, max_bits=160, needed_toggles=16):
    lcd_msg("FFT: preamble", "esperando...")
    last = None; toggles = 0; bits_seen = 0
    Tbit = 1.0 / BIT_RATE
    f_est = quick_edge_freq(300)
    print("Freq estimada en GP15 ~", f_est, "Hz")

    while bits_seen < max_bits:
        b, e0, e1 = decide_bit_fft(f0, f1, Tbit)  # ahora promedia 2 ventanas/bit
        if b < 0:
            continue
        if DEBUG_PREAMBLE:
            print("E0=", e0, "E1=", e1, "bit?", b)
        if last is not None and b != last:
            toggles += 1
            if toggles >= needed_toggles:
                return True
        last = b
        bits_seen += 1
    return False

def quick_edge_freq(ms=200):
    # Mide frecuencia contando transiciones (muy útil para saber si hay señal)
    start = time.ticks_us()
    prev = rx.value()
    edges = 0
    while time.ticks_diff(time.ticks_us(), start) < ms*1000:
        v = rx.value()
        if v != prev:
            edges += 1
            prev = v
    cyc = edges // 2
    freq = (cyc * 1000) // ms  # aprox Hz
    return freq

def read_bits(f0, f1, n_bits, Tbit):
    """Lee n_bits con decide_bit_fft y devuelve lista de 0/1."""
    out = []
    for _ in range(n_bits):
        b, _, _ = decide_bit_fft(f0, f1, Tbit)
        if b < 0:  # sin energía → conserva último o 0
            b = 0
        out.append(1 if b else 0)
    return out

def bits_to_byte_lsb_first(bits, start):
    """Convierte 8 bits desde 'start' (LSB primero) a entero."""
    v = 0
    for i in range(8):
        v |= (bits[start + i] & 1) << i
    return v

def popcount8(x):
    x &= 0xFF
    c = 0
    for _ in range(8):
        c += (x & 1)
        x >>= 1
    return c






def seek_sync_and_read_len(f0, f1, SYNC=0x7E, max_extra_bits=512, ham_tol=2):
    lcd_msg("Buscando SYNC", "ventana 8 bits")
    Tbit = 1.0 / BIT_RATE

    time.sleep_us(int(0.4 * Tbit * 1_000_000))  # mini delay para evitar borde

    window = []
    # precargar 7 bits
    for _ in range(7):
        b, _, _ = decide_bit_fft(f0, f1, Tbit)
        window.append(b & 1)

    for _ in range(max_extra_bits + 1):
        b, _, _ = decide_bit_fft(f0, f1, Tbit)
        window.append(b & 1)

        # reconstruir valor de la ventana (LSB-first)
        bits = window[-8:]
        val = 0
        for j in range(8):
            val |= (bits[j] & 1) << j
        print("Ventana actual =", bits, "→", f"{val:#04x}")

        # ¿coincide con SYNC (exacto o por Hamming)?
        if (val == SYNC) or (popcount8(val ^ SYNC) <= ham_tol):
            print("SYNC detectado con bits =", bits, f"(val = {val:#04x})")

            # *centrarse* un poco dentro del siguiente bit antes de leer LEN
            time.sleep_us(int(0.5 * Tbit * 1_000_000))

            # leer 8 bits de LEN (LSB-first para coincidir con el TX)
            bits_len = []
            L = 0
            for i in range(8):
                bi, e0, e1 = decide_bit_fft(f0, f1, Tbit)
                bits_len.append(bi & 1)
                L |= ((bi & 1) << i)
                print(f"LEN bit {i}: b={bi}, E0={e0:.1f}, E1={e1:.1f}")

            print("LEN bits =", bits_len, "->", L)
            print("LEN binario =", ''.join(str(b) for b in bits_len))
            print("SYNC+LEN bruteforce:", [(bits, val), (bits_len, L)])

            return True, L

    return False, 0

# --- añade estas utilidades ---
def dominant_bin_hz(mag2_pos):
    kmax = int(np.argmax(mag2_pos[1:])) + 1  # evita DC
    return int((kmax * SAMPLE_RATE) // NFFT)

def measure_band_power_once(f0, f1):
    temp = np.zeros(NFFT)
    acquire_block(temp)
    x = (temp * 2.0) - 1.0
    xw = x * WIN
    X = np.fft.fft(xw)
    Xpos = X[:NFFT//2 + 1]
    mag2 = (Xpos.real * Xpos.real) + (Xpos.imag * Xpos.imag)
    p = band_power_bins(mag2, f0) + band_power_bins(mag2, f1)
    return p, dominant_bin_hz(mag2)


def wait_for_energy(f0, f1, timeout_s=4.0, thresh_mult=1.8):
    # baseline 0.5 s
    t0 = time.ticks_ms()
    samples = 0
    acc = 0.0
    while time.ticks_diff(time.ticks_ms(), t0) < 500:
        p, _ = measure_band_power_once(f0, f1)
        acc += p; samples += 1
    baseline = (acc / max(1, samples))
    threshold = baseline * thresh_mult

    # espera hasta timeout
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < int(timeout_s*1000):
        p, fpk = measure_band_power_once(f0, f1)
        if p > threshold:
            print("ENERGY OK  p=", p, " thr=", threshold, " fpk~", fpk)
            return True
    return False


# Calibración rápida (200–300 ms de beacon)
def quick_calibrate(f0, f1, ms=300, factor=1.6):
    global SWAP_DETECT
    t0 = time.ticks_ms()
    sum0 = 0.0; sum1 = 0.0
    temp = np.zeros(NFFT)
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        acquire_block(temp)
        x  = (temp * 2.0) - 1.0
        x *= WIN
        X    = np.fft.fft(x)
        Xpos = X[:NFFT//2 + 1]
        mag2 = (Xpos.real * Xpos.real) + (Xpos.imag * Xpos.imag)
        sum0 += band_power_bins(mag2, f0)
        sum1 += band_power_bins(mag2, f1)
    # Si en beacon (tono alto f1) “gana” f0, invierte
    if sum0 > factor*sum1:
        SWAP_DETECT = True
    elif sum1 > factor*sum0:
        SWAP_DETECT = False






def main():
    print("RX FFT listo. Escaneo inicial")
    global static_swap, SWAP_DETECT
    static_swap = None
    SWAP_DETECT = False

    while True:
        # 1) Escanear banda
        idx = find_band_lock()
        fc, dev = BANDS[idx]
        f0, f1 = fc - dev, fc + dev

        # 1.5) Esperar energía real (beacon)
        print("Esperando señal en banda bloqueada")
        if not wait_for_energy(f0, f1, timeout_s=6.0, thresh_mult=1.8):
            time.sleep(0.3)
            continue

        print("Energía detectada. Calibrando...")
        

        
        if static_swap is None:
            quick_calibrate(f0, f1, ms=350, factor=1.35)
            static_swap = SWAP_DETECT
        else:
            SWAP_DETECT = static_swap

        print("SWAP_DETECT =", SWAP_DETECT)

        time.sleep_ms(10)

        print("Buscando SYNC en ventana deslizante...")

        
        ok, length = seek_sync_and_read_len(f0, f1, SYNC=SYNC, max_extra_bits=512, ham_tol=1)

        # Auto-swap si LEN es sospechoso
        if ok and (length == 0 or length == 255 or length > 80):
            print("LEN sospechoso:", length, "→ intento auto-swap y reintento LEN")
            SWAP_DETECT = not SWAP_DETECT
            ok2, length2 = seek_sync_and_read_len(f0, f1, SYNC=SYNC, max_extra_bits=384, ham_tol=1)
            if ok2:
                ok, length = ok2, length2
            else:
                # si no mejoró, revierte swap y reescanea
                SWAP_DETECT = not SWAP_DETECT

        if not ok or length > 80 or length == 0:
            print("SYNC o LEN inválido, reescaneando...")
            time.sleep_ms(50)
            continue
        print("LEN OK =", length)
        
        time.sleep_us(int(0.2 * 1_000_000 / BIT_RATE))  # delay ≈ 20% del bit


        buf = bytearray()
        for _ in range(length):
            buf.append(read_byte_fft(f0, f1))
            
        print("BYTE recibido:", buf)

        print("Esperado:", [ord(c) for c in 'H'])
        print("Recibido (bin):", [f"{b:08b}" for b in buf])


        chk = read_byte_fft(f0, f1)
        if chk != checksum_xor(bytes([SYNC, length]) + buf):
            print("Error de checksum")
            time.sleep(0.5)
            continue

        try:
            text = buf.decode('ascii', errors='ignore')
        except:
            text = "<binario>"
        lcd_msg("Msg:", text)
        print("PAYLOAD:", text)

        time.sleep(0.4)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        lcd_msg("RX detenido", "")
