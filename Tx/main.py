import machine

import utime

import math

from pico_i2c_lcd import I2cLcd



# --- Configuración ---

ADC_PIN = 26

I2C_SDA_PIN = 4

I2C_SCL_PIN = 5

I2C_ADDR = 0x27



N_SAMPLES = 205

FS_REAL = 8350



# --- ¡¡¡CAMBIO IMPORTANTE!!! ---

# Tu Threshold anterior (1,000,000,000) era para una señal PWM

# de amplitud completa. Ahora, la señal está MEZCLADA y sumada,

# por lo que la amplitud de CADA componente es diferente.

# Este valor casi seguro necesita ser MÁS BAJO.

# Empezamos con 500 Millones. Es probable que tengas que

# reducirlo (o aumentarlo) probando.

#

# CÓMO CALIBRARLO:

# 1. Ejecuta el transmisor enviando "HOLA" y un tono de 880 Hz.

# 2. Mira la consola de Thonny del PICO.

# 3. Si NUNCA detecta un bit (no dice "Start bit detectado"),

#    el THRESHOLD es MUY ALTO. Bájalo (ej: 200000000).

# 4. Si detecta bits FALSOS constantemente (recibe basura),

#    el THRESHOLD es MUY BAJO. Súbelo (ej: 700000000).

THRESHOLD = 150000000000 # 500 Millones (¡AJUSTAR!)

# --- FIN DEL CAMBIO ---



TARGET_F0 = 2100

k_F0 = 52

coeff_F0 = 2.0 * math.cos(2.0 * math.pi * k_F0 / N_SAMPLES)



TARGET_F1 = 3100

k_F1 = 77

coeff_F1 = 2.0 * math.cos(2.0 * math.pi * k_F1 / N_SAMPLES)



print("Receptor FDM v1.1 (ASCII en señal mezclada)")

print("Canal F0 (k={}) @ {:.0f} Hz".format(k_F0, k_F0 * FS_REAL / N_SAMPLES))

print("Canal F1 (k={}) @ {:.0f} Hz".format(k_F1, k_F1 * FS_REAL / N_SAMPLES))

print(">>> Umbral de Detección: {} <<<".format(THRESHOLD))

print("Ajusta el THRESHOLD si no recibes nada o recibes basura.")



# --- Variables globales ---

adc = None

lcd = None

ascii_state = "IDLE"

current_byte = 0

bit_count = 0

BIT_PERIOD_MS = 190 # Dejar como estaba, es la temporización

last_bit_time = 0

received_string = ""



# --- init_hardware() (Sin cambios) ---

def init_hardware():

    global adc, lcd, I2C_ADDR

    try:

        adc = machine.ADC(machine.Pin(ADC_PIN))

        i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA_PIN), scl=machine.Pin(I2C_SCL_PIN), freq=400000)

        devices = i2c.scan()

        if not devices: raise OSError("No I2C device found.")

        I2C_ADDR = devices[0]

        print("LCD encontrada en {}".format(hex(I2C_ADDR)))

        lcd = I2cLcd(i2c, I2C_ADDR, 2, 16)

        lcd.clear()

        return True

    except Exception as e:

        print("Error fatal de Hardware: {}".format(e))

        return False



# --- process_ascii() (Sin cambios) ---

def process_ascii(bit_detected):

    global ascii_state, current_byte, bit_count, last_bit_time, received_string, lcd, utime

    

    current_time = utime.ticks_ms()

    

    # bit_detected: 0 (F0), 1 (F1), o -1 (Ruido)



    if ascii_state == "IDLE":

        if bit_detected == 1: # START BIT! (F1)

            ascii_state = "RECEIVING"

            bit_count = 0

            current_byte = 0

            last_bit_time = current_time # Empezamos a contar el tiempo

            print("Start bit detectado!")

        # Si es 0 o -1, no hacemos nada.

            

    elif ascii_state == "RECEIVING":

        # ¿Ha pasado el tiempo de 1 bit?

        if utime.ticks_diff(current_time, last_bit_time) > BIT_PERIOD_MS:

            last_bit_time = current_time # Reiniciar el contador

            

            # ¡SOLO LEEMOS SI LA SEÑAL NO ES RUIDO!

            if bit_detected == -1:

                # ¡Error de bit! La señal se perdió. Abortar.

                print("Error de bit (Ruido detectado). Abortando.")

                ascii_state = "IDLE"

                return # Salir de la función



            # Si llegamos aquí, el bit es 0 o 1

            if bit_detected == 1:

                current_byte |= (1 << bit_count)

            

            bit_count += 1

            

            if bit_count == 8:

                # Terminamos.

                char = chr(current_byte)

                print("Byte Recibido: {} -> '{}'".format(current_byte, char))

                

                received_string += char

                if len(received_string) > 16:

                    received_string = received_string[1:]

                

                lcd.clear()

                lcd.putstr("ASCII Recibido:")

                lcd.move_to(0, 1)

                lcd.putstr(received_string)

                

                ascii_state = "IDLE" # Volver a buscar un Start Bit



# --- run_detector() (Sin cambios en la lógica) ---

def run_detector():

    global lcd, coeff_F0, coeff_F1, THRESHOLD

    if not init_hardware():

        print("Fallo al inicializar hardware.")

        return



    lcd.putstr("Receptor FDM v1.1\nEsperando ASCII...")

    

    while True:

        q1_F0 = 0.0

        q2_F0 = 0.0

        q1_F1 = 0.0

        q2_F1 = 0.0

        

        t_start = utime.ticks_us()

        

        for i in range(N_SAMPLES):

            sample = float(adc.read_u16())

            q0_F0 = coeff_F0 * q1_F0 - q2_F0 + sample

            q2_F0 = q1_F0

            q1_F0 = q0_F0

            q0_F1 = coeff_F1 * q1_F1 - q2_F1 + sample

            q2_F1 = q1_F1

            q1_F1 = q0_F1

            

            # Temporización del muestreo (Sin cambios)

            next_sample_time = utime.ticks_add(t_start, (i + 1) * 120)

            while utime.ticks_diff(next_sample_time, utime.ticks_us()) > 0:

                pass



        mag_F0 = (q1_F0 * q1_F0) + (q2_F0 * q2_F0) - (coeff_F0 * q1_F0 * q2_F0)

        mag_F1 = (q1_F1 * q1_F1) + (q2_F1 * q2_F1) - (coeff_F1 * q1_F1 * q2_F1)

        

        # --- Lógica de Decisión (Sin cambios) ---

        current_bit = -1 # Por defecto, es RUIDO

        

        if mag_F0 > THRESHOLD and mag_F0 > mag_F1:

            current_bit = 0

        elif mag_F1 > THRESHOLD and mag_F1 > mag_F0:

            current_bit = 1

        

        # Pasamos el bit (0, 1, o -1) a la máquina de estados

        process_ascii(current_bit)



if __name__ == "__main__":

    run_detector()
