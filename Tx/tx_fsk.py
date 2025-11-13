from machine import Pin, PWM
import utime

# --- Configuración Hardware ---
PWM_PIN = 16  # GP16 para salida de PWM
F0_NOMINAL = 1500  # Frecuencia para '0'
F1_NOMINAL = 2500  # Frecuencia para '1'

# Inicializar PWM
pwm = PWM(Pin(PWM_PIN))
pwm.duty_u16(0) # Apagado al inicio

def run_simple_tx():
    """Bucle principal del transmisor simple"""
    print("Iniciando transmisor simple FSK...")
    
    while True:
        # Enviar Tono F0
        print(f"Enviando Tono F0 ({F0_NOMINAL} Hz) por 3 segundos...")
        pwm.freq(F0_NOMINAL)
        pwm.duty_u16(32768) # 50% duty cycle
        utime.sleep(3)
        
        # Enviar Tono F1
        print(f"Enviando Tono F1 ({F1_NOMINAL} Hz) por 3 segundos...")
        pwm.freq(F1_NOMINAL)
        pwm.duty_u16(32768)
        utime.sleep(3)

if __name__ == "__main__":
    run_simple_tx()