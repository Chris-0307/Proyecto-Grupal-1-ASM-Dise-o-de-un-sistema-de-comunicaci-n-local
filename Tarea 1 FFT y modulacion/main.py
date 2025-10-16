from audio_fft import AudioFFT
from modulacion import ModuladorFSK
from interactive_plot import InteractivePlotter

if __name__ == "__main__":
    # --- Recolección de datos del Punto 2 ---
    print("================================================")
    print("=== PUNTO 2: Cargando datos del archivo de audio ===")
    print("================================================")
    
    fft_analyzer = AudioFFT(audio_path="Audios/TimeLeaper.mp3", sr_target=44100, n_fft=65536)
    punto2_data = None
    punto2_title = "Punto 2: Análisis FFT del archivo 'TimeLeaper.mp3'"
    try:
        # Obtenemos los datos SIN mostrar el gráfico ahora
        punto2_data = fft_analyzer.analyze(window_title=punto2_title, show_plot=False)
    except Exception as e:
        print(f"\nADVERTENCIA: No se pudo analizar el archivo de audio. ¿Existe la carpeta 'Audios' y el archivo 'TimeLeaper.mp3'?")
        print(f"Error: {e}")

    # --- Recolección de datos del Punto 5 ---
    print("\n\n=======================================================")
    print("=== PUNTO 5: Calculando simulación de Modulación FSK ===")
    print("=======================================================")

    SAMPLE_RATE    = 44100
    DURACION       = 2
    FREQ_MENSAJE   = 50      # bit_rate = 50 bps
    FREQ_PORTADORA = 2000
    FREQ_DEV       = 500     # separa f0/f1: f0=1500 Hz, f1=2500 Hz

    modulador = ModuladorFSK(
        freq_mensaje=FREQ_MENSAJE,
        freq_portadora=FREQ_PORTADORA,
        duracion=DURACION,
        sr=SAMPLE_RATE,
        fft_analyzer=fft_analyzer,
        freq_dev=FREQ_DEV
    )

    time_domain_data, fft_domain_data = modulador.run_simulation_and_get_data()
    
    # --- Lanzar la Interfaz Gráfica Unificada ---
    if punto2_data is None:
        print("\nADVERTENCIA: No se mostrará el botón del Punto 2 porque los datos no pudieron ser cargados.")
    
    print("\nLanzando ventana interactiva...")
    plotter = InteractivePlotter(time_domain_data, fft_domain_data, punto2_data, punto2_title)
    plotter.show()