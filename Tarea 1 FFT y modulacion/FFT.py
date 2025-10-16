# -*- coding: utf-8 -*-
# Requisitos: pip install librosa soundfile matplotlib numpy scipy

import numpy as np
import librosa
import librosa.display
import soundfile as sf
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

def analyze_audio_fft(audio_path: str | None = None, sr_target: int | None = None,
                      n_fft: int | None = None, use_hann: bool = True,
                      top_peaks: int = 8):
    """
    Carga audio, calcula FFT (rFFT) y grafica/retorna magnitud y fase.

    Parámetros:
    - audio_path: ruta a .wav/.mp3. Si None, usa un audio de ejemplo libre de librosa.
    - sr_target: remuestreo opcional (p.ej., 22050, 44100). Si None, conserva el original.
    - n_fft: tamaño de la FFT. Si None, usa la potencia de 2 siguiente al largo de la señal.
    - use_hann: aplica ventana de Hann para reducir leakage.
    - top_peaks: cuántos picos (frecuencias dominantes) listar.

    Retorna:
      dict con:
        'freq_hz' (vector), 'mag' (lineal), 'mag_db' (dBFS),
        'phase_rad' (radianes), 'sr' (Hz), 'peaks' (índices de picos)
    """
    # === 1) Cargar audio ===
    if audio_path is None:
        # Ejemplo libre integrado en librosa
        audio_path = librosa.ex('trumpet')  # archivo de dominio público para demos
    y, sr = librosa.load(audio_path, sr=sr_target, mono=True)  # mezcla a mono

    # Normaliza para que 0 dBFS sea el pico de la señal (opcional, ayuda a comparar dB)
    peak = np.max(np.abs(y)) + 1e-12
    y = y / peak

    # === 2) Preparar señal para FFT ===
    L = len(y)
    if n_fft is None:
        # próxima potencia de 2: mejor desempeño y resolución controlada
        n_fft = 1 << (L - 1).bit_length()
    x = y
    if use_hann:
        win = np.hanning(min(L, n_fft))
    else:
        win = np.ones(min(L, n_fft))

    # si n_fft > L, hacemos zero-padding; si n_fft < L, truncamos educadamente
    x = x[:len(win)]
    xw = x * win
    if n_fft > len(xw):
        xw = np.pad(xw, (0, n_fft - len(xw)))

    # === 3) rFFT (solo mitad positiva) ===
    Y = np.fft.rfft(xw, n=n_fft)
    freq = np.fft.rfftfreq(n_fft, d=1.0/sr)

    # Magnitud y fase
    mag = np.abs(Y)
    mag_db = 20 * np.log10(mag / (np.max(mag) + 1e-12) + 1e-12)  # dBFS relativo al pico del espectro
    phase = np.angle(Y)  # envuelta en (-π, π]; podrías hacer np.unwrap si prefieres

    # === 4) Encontrar picos dominantes (ignorando DC) ===
    # Umbral sencillo: -50 dB y distancia mínima entre picos para no listar armónicos muy cercanos
    peaks, _ = find_peaks(mag_db, height=-50, distance=max(3, n_fft // 2048))
    peaks = peaks[freq[peaks] > 1.0]  # ignorar 0–1 Hz (DC/deriva)
    # Ordenar por magnitud (desc)
    order = np.argsort(mag[peaks])[::-1]
    peaks = peaks[order][:top_peaks]

    # === 5) Gráficas ===
    plt.figure(figsize=(12, 6))
    plt.subplot(2, 1, 1)
    plt.plot(freq, mag_db, color="#1f77b4")
    if len(peaks) > 0:
        plt.scatter(freq[peaks], mag_db[peaks], color="crimson", zorder=5, label="Picos")
        for p in peaks:
            plt.annotate(f"{freq[p]:.1f} Hz", (freq[p], mag_db[p]),
                         textcoords="offset points", xytext=(5, 5), fontsize=8)
    plt.title("Espectro de Magnitud (dBFS)")
    plt.xlabel("Frecuencia (Hz)")
    plt.ylabel("Magnitud (dB)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="best")

    plt.subplot(2, 1, 2)
    plt.plot(freq, phase, color="#2ca02c")
    plt.title("Fase (rad)")
    plt.xlabel("Frecuencia (Hz)")
    plt.ylabel("Fase (rad)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    # === 6) Resumen por consola ===
    print(f"Samplerate: {sr} Hz")
    print(f"FFT size: {n_fft} (Δf ≈ {sr/n_fft:.2f} Hz)")
    if len(peaks) > 0:
        print("\nFrecuencias dominantes:")
        for i, p in enumerate(peaks, start=1):
            print(f"  {i:02d}: {freq[p]:8.2f} Hz | {mag_db[p]:6.1f} dB | fase {phase[p]:+6.2f} rad")
    else:
        print("No se detectaron picos significativos (> -50 dB).")

    return {
        "freq_hz": freq,
        "mag": mag,
        "mag_db": mag_db,
        "phase_rad": phase,
        "sr": sr,
        "peaks": peaks
    }

if __name__ == "__main__":
    # 1) Usar el ejemplo libre de librosa:
    analyze_audio_fft("Audios/TimeLeaper.mp3", sr_target=44100, n_fft=65536)

    # 2) O usar tu propio archivo:
    # analyze_audio_fft("mi_audio.wav", sr_target=44100, n_fft=65536)
