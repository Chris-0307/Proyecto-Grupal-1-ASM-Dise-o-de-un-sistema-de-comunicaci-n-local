from machine import Pin, PWM

import utime

import _thread



# --- Configuración de Pines ---

PIN_ASCII = 26  # Pin para la FSK ASCII (sumador R1)

PIN_BUZZER = 25 # Pin para el Tono Piloto (sumador R2)



# --- Frecuencias FSK ASCII ---

F_ASCII_0 = 2100

F_ASCII_1 = 3100

BIT_PERIOD_MS = 200 # 200ms por bit



print("Transmisor FDM v1.0 (Multihilo PWM)")



# --- Variables Globales y Locks (para comunicación entre hilos) ---

g_ascii_message = None

g_buzzer_freq = 0

ascii_lock = _thread.allocate_lock()

buzzer_lock = _thread.allocate_lock()



# --- Tarea 1: Transmisor ASCII (Correrá en Core 1) ---



def send_byte_ascii(pwm_obj, byte_val):

    """Envía 1 byte de datos (8 bits LSB primero) + Start/Stop bits."""

    # 1. Start Bit (F1)

    pwm_obj.freq(F_ASCII_1)

    utime.sleep_ms(BIT_PERIOD_MS)

    

    # 2. Enviar 8 bits de datos (LSO a MSO)

    for i in range(8):

        bit = (byte_val >> i) & 1

        if bit == 1:

            pwm_obj.freq(F_ASCII_1)

        else:

            pwm_obj.freq(F_ASCII_0)

        utime.sleep_ms(BIT_PERIOD_MS)

        

    # 3. Stop Bit (F0)

    pwm_obj.freq(F_ASCII_0)

    utime.sleep_ms(BIT_PERIOD_MS)



def ascii_task():

    """Hilo dedicado a manejar la transmisión ASCII."""

    global g_ascii_message

    

    # Inicializamos el PWM para ESTE hilo

    pwm_ascii = PWM(Pin(PIN_ASCII))

    pwm_ascii.freq(F_ASCII_0)

    pwm_ascii.duty(512) # 50% duty cycle

    

    # CAMBIO: .format()

    print("[ASCII Thread] Iniciado en Pin {}".format(PIN_ASCII))

    

    while True:

        local_message = None

        

        # Revisamos si hay un nuevo mensaje (zona crítica)

        with ascii_lock:

            if g_ascii_message is not None:

                local_message = g_ascii_message # Copiamos el mensaje

                g_ascii_message = None        # Lo borramos de la cola

        

        if local_message:

            # Si hay mensaje, lo enviamos

            # CAMBIO: .format()

            print("[ASCII Thread] Transmitiendo: '{}'".format(local_message))

            for char in local_message:

                send_byte_ascii(pwm_ascii, ord(char))

            print("[ASCII Thread] Transmisión completa. Volviendo a 'idle'.")

            pwm_ascii.freq(F_ASCII_0) # Volver a idle

            

        utime.sleep_ms(100) # Dormir un poco para ceder el paso



# --- Tarea 2: Generador de Tono (Correrá en Core 1) ---



def buzzer_task():

    """Hilo dedicado a manejar el tono del buzzer."""

    global g_buzzer_freq

    

    # Inicializamos el PWM para ESTE hilo

    pwm_buzzer = PWM(Pin(PIN_BUZZER))

    pwm_buzzer.duty(0) # Empezar apagado

    

    # CAMBIO: .format()

    print("[Buzzer Thread] Iniciado en Pin {}".format(PIN_BUZZER))

    

    current_freq = 0

    

    while True:

        target_freq = 0

        

        # Revisamos la frecuencia deseada (zona crítica)

        with buzzer_lock:

            target_freq = g_buzzer_freq

            

        if target_freq != current_freq:

            # Si la frecuencia cambió, la actualizamos

            current_freq = target_freq

            if current_freq > 0:

                # CAMBIO: .format()

                print("[Buzzer Thread] Tono cambiado a {} Hz".format(current_freq))

                pwm_buzzer.freq(current_freq)

                pwm_buzzer.duty(512) # 50% duty cycle

            else:

                print("[Buzzer Thread] Tono apagado")

                pwm_buzzer.duty(0) # Apagar

                

        utime.sleep_ms(50) # Dormir un poco



# --- Hilo Principal (Core 0): Recepción de Comandos ---



def main_loop():

    global g_ascii_message, g_buzzer_freq

    

    print("Iniciando hilos de transmisión en Core 1...")

    _thread.start_new_thread(ascii_task, ())

    _thread.start_new_thread(buzzer_task, ())

    

    utime.sleep(1) # Dar tiempo a que los hilos arranquen

    print("\n--- Transmisor FDM Listo ---")

    print("El sistema está enviando señales simultáneamente.")

    print("Ingrese los datos cuando se le pida.")

    

    while True:

        try:

            # Pedir frecuencia

            # Usamos 880 Hz: Sus armónicos (3*f = 2640 Hz) están

            # lejos de 2100 y 3100. ¡NO USAR 440 Hz! (5*f=2200, 7*f=3080)

            frec_str = input("\nFrecuencia de buzzer (Recomendado: 880): ")

            target_freq = int(frec_str)

            

            # Pedir mensaje

            msg_str = input("Mensaje ASCII (ej: HOLA: ")

            

            # Actualizar las variables globales (con locks)

            with buzzer_lock:

                g_buzzer_freq = target_freq

            

            with ascii_lock:

                g_ascii_message = msg_str

            

            # CAMBIO: .format()

            print("Comandos recibidos: Freq={} Hz, Msg='{}'".format(target_freq, msg_str))

            print("Los hilos se encargarán de la transmisión...")



        except ValueError:

            print("Error: Ingrese un número válido para la frecuencia.")

        except Exception as e:

            # CAMBIO: .format()

            print("Error en bucle principal: {}".format(e))



# Iniciar el programa

if __name__ == "__main__":

    main_loop()


