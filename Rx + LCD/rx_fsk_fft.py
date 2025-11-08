# rx_simple_fft.py
# V8 - Versión Exposición (LCD "Sticky" + Consola de Proceso)

import machine
import utime
from ulab import numpy as np
from pico_i2c_lcd import I2cLcd

# --- Configuración Hardware RX ---
ADC_PIN = 26  # GP26 (ADC0)
I2C_SDA_PIN = 4 # GP4
I2C_SCL_PIN = 5 # GP5
I2C_ADDR = 0x27 

# --- Configuración de Muestreo y FFT ---
FS = 12800      # Frecuencia de muestreo
NFFT = 512      # Tamaño de la FFT
DF = FS / NFFT    # Resolución de frecuencia (25 Hz por bin)

print(f"Fs={FS}, NFFT={NFFT}, Res={DF} Hz")

# --- Ventanas de Búsqueda (Basadas en tus datos) ---
BIN_F0_START = 80  # 2000 Hz
BIN_F0_END = 100   # 2500 Hz
FREQ_F0_DISPLAY = 2200 # Frecuencia a mostrar

BIN_F1_START = 140 # 3500 Hz
BIN_F1_END = 160   # 4000 Hz
FREQ_F1_DISPLAY = 3675 # Frecuencia a mostrar

NOISE_THRESHOLD = 100000.0

print(f"Buscando F0 en Bins {BIN_F0_START}-{BIN_F0_END}")
print(f"Buscando F1 en Bins {BIN_F1_START}-{BIN_F1_END}")

# --- Buffers (Pre-alocados) ---
samples_f = np.zeros(NFFT, dtype=np.float)

# --- Ventana Blackman Manual ---
print("Generando ventana Blackman manual...")
N = NFFT
n = np.arange(N)
window = 0.42 - 0.5 * np.cos(2 * np.pi * n / (N - 1)) + \
         0.08 * np.cos(4 * np.pi * n / (N - 1))
print("Ventana OK.")

# Variables globales para hardware
adc = None
lcd = None

def init_hardware():
    """Inicializa ADC y LCD"""
    global adc, lcd, I2C_ADDR
    try:
        adc = machine.ADC(machine.Pin(ADC_PIN))
        i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA_PIN), scl=machine.Pin(I2C_SCL_PIN), freq=400000)
        devices = i2c.scan()
        if not devices: raise OSError("No I2C device found.")
        if I2C_ADDR not in devices:
            if 0x3F in devices: I2C_ADDR = 0x3F
            else: I2C_ADDR = devices[0]
        
        print(f"LCD encontrada en {hex(I2C_ADDR)}")
        lcd = I2cLcd(i2c, I2C_ADDR, 2, 16) 
        lcd.clear()
        return True
    except Exception as e:
        print(f"Error fatal de Hardware: {e}")
        return False

def capture_and_window():
    """Captura NFFT muestras, resta DC y aplica ventana"""
    global samples_f, window, adc
    for i in range(NFFT):
        samples_f[i] = float(adc.read_u16())
    mean_val = np.mean(samples_f)
    samples_f = samples_f - mean_val
    return samples_f * window

def run_detector():
    """Bucle principal del detector FFT con pantalla 'sticky'"""
    global lcd
    
    if not init_hardware():
        print("Fallo al inicializar hardware.")
        return

    # --- Lógica de Pantalla "Sticky" ---
    # 0 = Buscando, 1 = F0, 2 = F1
    current_lcd_state = -1 
    
    # --- NUEVO: Contadores para "throttling" de prints ---
    loop_counter = 0
    PRINT_EVERY_N_LOOPS = 10 # Imprime 1 de cada 10 análisis (aprox 2-3 por seg)
    
    # Mensaje inicial en LCD
    lcd.putstr("Iniciando...")
    utime.sleep(1)

    while True:
        # --- 1. PROCESO DE DEMODULACIÓN (EL TRABAJO REAL) ---
        windowed_samples = capture_and_window()
        fft_complex = np.fft.fft(windowed_samples)
        spectrum = abs(fft_complex)
        
        mag_f0 = np.max(spectrum[BIN_F0_START : BIN_F0_END + 1])
        mag_f1 = np.max(spectrum[BIN_F1_START : BIN_F1_END + 1])
        
        # --- 2. PRINT DE PROCESO (PARA EL PROFESOR) ---
        loop_counter += 1
        if loop_counter % PRINT_EVERY_N_LOOPS == 0:
            # Este print se ejecuta CADA 10 bucles
            # Demuestra que el RX sigue "vivo" y analizando
            print(f"Analizando... [Mag F0: {mag_f0:.0f}] [Mag F1: {mag_f1:.0f}]")
        
        # --- 3. LÓGICA DE DECISIÓN ---
        new_state = 0 # Por defecto, 'Buscando'
        if mag_f0 > NOISE_THRESHOLD or mag_f1 > NOISE_THRESHOLD:
            if mag_f0 > mag_f1:
                new_state = 1 # F0
            else:
                new_state = 2 # F1
        
        # --- 4. LÓGICA DE LCD "STICKY" (SOLO SE ACTUALIZA SI HAY CAMBIOS) ---
        if new_state != current_lcd_state:
            lcd.clear()
            
            # Este print es el más importante, solo se ejecuta
            # cuando se toma una *nueva decisión*.
            print("\n------------------------------------")
            
            if new_state == 0:
                lcd.putstr("Buscando Tono..")
                print("DECISIÓN: Ruido detectado. Buscando...")
            elif new_state == 1:
                lcd.putstr(f"TONO F0 DETECTADO")
                lcd.move_to(0, 1)
                lcd.putstr(f"{FREQ_F0_DISPLAY} Hz")
                print(f"DECISIÓN: Tono F0 Detectado! ({FREQ_F0_DISPLAY} Hz)")
            elif new_state == 2:
                lcd.putstr(f"TONO F1 DETECTADO")
                lcd.move_to(0, 1)
                lcd.putstr(f"{FREQ_F1_DISPLAY} Hz")
                print(f"DECISIÓN: Tono F1 Detectado! ({FREQ_F1_DISPLAY} Hz)")
            
            print("------------------------------------\n")
            
            # Actualizar el estado y reiniciar el contador
            current_lcd_state = new_state
            loop_counter = 0

if __name__ == "__main__":
    run_detector()