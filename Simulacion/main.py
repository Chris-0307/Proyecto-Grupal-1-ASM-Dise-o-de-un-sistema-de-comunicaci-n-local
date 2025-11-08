from audio_fft import AudioFFT
from pathlib import Path
import numpy as np

# Nuevos import requeridos
from modulacion import TransmisorFSK
from receptores import receptor_audio, receptor_texto

if __name__ == "__main__":
    
    BASE_DIR = Path(__file__).resolve().parent
    AUDIO_PATH = BASE_DIR / "Audios" / "TimeLeaper.mp3"

    # ==============================================================
    # === PUNTO 2: Análisis FFT del archivo de audio (sin cambios) ===
    # ==============================================================
    print("================================================")
    print("=== PUNTO 2: Cargando datos del archivo de audio ===")
    print("================================================")
    
    fft_analyzer = AudioFFT(
        audio_path=str(AUDIO_PATH),
        sr_target=44100,
        n_fft=65536
    )    

    punto2_data = None
    punto2_title = "Punto 2: Análisis FFT del archivo 'TimeLeaper.mp3'"

    try:
        if not AUDIO_PATH.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {AUDIO_PATH}")
        punto2_data = fft_analyzer.analyze(window_title=punto2_title, show_plot=False)
    except FileNotFoundError as e:
        print("\nADVERTENCIA: No se pudo analizar el archivo de audio.")
        print(f"Detalle: {e}")
    except Exception as e:
        print("\nADVERTENCIA: Falló el análisis del audio.")
        print(f"Detalle: {e}")

    # =====================================================================
    # === PUNTO 5: Simulación del Sistema de Comunicación con FSK ========
    # =====================================================================
    print("\n\n=======================================================")
    print("=== PUNTO 5: Simulación del Sistema de Comunicación FSK ===")
    print("=======================================================\n")

    SAMPLE_RATE = 44100
    BIT_RATE    = 40
    FC_TEXTO    = 2500      # Frecuencia portadora para mensaje FSK
    FC_PILOTO   = 800       # Frecuencia piloto (Receptor 1)
    FREQ_DEV    = 300       # Separación f0/f1

    TEXTO = "Koki es un sobo"
    BITS_LEN = len(TEXTO) * 8                     # Número de bits a transmitir
    NBIT = int(round(SAMPLE_RATE / BIT_RATE))     # Muestras por bit
    DURACION = (BITS_LEN * NBIT) / SAMPLE_RATE    # Duración exacta en segundos

    print(f"Duración exacta calculada: {DURACION:.4f} s")
    print(f"Bits totales: {BITS_LEN}, Muestras/bit: {NBIT}")

    # === TRANSMISOR ===
    TX = TransmisorFSK(sr=SAMPLE_RATE)

    t, señal_tx, mod_texto = TX.transmitir(
        texto_ascii=TEXTO,
        duracion=DURACION,
        fc_texto=FC_TEXTO,
        fc_piloto=FC_PILOTO,
        dev=FREQ_DEV,
        bit_rate=BIT_RATE
    )

    # === RECEPTOR 1 (Piloto) ===
    print("\n=== RECEPTOR 1 (Piloto / Audio) ===")
    receptor_audio(señal_tx, SAMPLE_RATE)

    # === RECEPTOR 2 (Texto ASCII) ===
    print("\n=== RECEPTOR 2 (Texto) ===")
    receptor_texto(
        señal_tx,
        modulador_original=mod_texto,
        sr=SAMPLE_RATE,
        fc_texto=FC_TEXTO,
        dev=FREQ_DEV,
        expected_bits=BITS_LEN
    )

    print("\n✅ Simulación completada.\n")
