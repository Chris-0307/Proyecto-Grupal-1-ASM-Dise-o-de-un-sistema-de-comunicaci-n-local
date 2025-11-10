# main.py (Transmisor ESP32 v11.2 - ASCII Robusto)
from machine import Pin, PWM
import utime

# --- Frecuencias de PRUEBA (F0 y F1) ---
F_ASCII_0 = 2100
F_ASCII_1 = 3100
PIN_SALIDA = 26
# CAMBIO: Aumentamos el período para más robustez
BIT_PERIOD_MS = 200 # 200ms por bit

print("Transmisor FSK v11.2 (ASCII Robusto)")

# Primero creamos el objeto PWM
pwm = PWM(Pin(PIN_SALIDA))
# Iniciamos en F0 (idle)
pwm.freq(F_ASCII_0)
pwm.duty(512)

def send_byte(byte_val):
    """Envía 1 byte de datos (8 bits LSB primero) + Start/Stop bits."""
    global pwm
    
    # 1. Start Bit (F1)
    pwm.freq(F_ASCII_1)
    # CAMBIO: Usar sleep_ms
    utime.sleep_ms(BIT_PERIOD_MS)
    
    # 2. Enviar 8 bits de datos (LSO a MSO)
    for i in range(8):
        bit = (byte_val >> i) & 1
        if bit == 1:
            pwm.freq(F_ASCII_1)
        else:
            pwm.freq(F_ASCII_0)
        # CAMBIO: Usar sleep_ms
        utime.sleep_ms(BIT_PERIOD_MS)
        
    # 3. Stop Bit (F0)
    pwm.freq(F_ASCII_0)
    # CAMBIO: Usar sleep_ms
    utime.sleep_ms(BIT_PERIOD_MS)

def send_string(s):
    """Envía un string, caracter por caracter."""
    print("Transmitiendo: '{}'".format(s))
    for char in s:
        send_byte(ord(char))
    print("Transmisión completa. Volviendo a 'idle' (F0).")
    pwm.freq(F_ASCII_0)

# Bucle principal: Enviar "HOLA" cada 5 segundos
while True:
    send_string("HOLA")
    utime.sleep(5)
