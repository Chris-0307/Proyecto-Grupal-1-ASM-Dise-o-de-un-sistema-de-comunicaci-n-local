import numpy as np
import matplotlib.pyplot as plt
from numpy.fft import rfft, rfftfreq
from scipy.signal import butter, sosfiltfilt

def butter_bandpass_sos(lowcut, highcut, fs, order=6):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    return butter(order, [low, high], btype='band', output='sos')

def bandpass(signal, fs, f_center, dev, scale=1.5, order=6):
    low = max(1.0, f_center - scale*dev)
    high = f_center + scale*dev
    sos = butter_bandpass_sos(low, high, fs, order=order)
    return sosfiltfilt(sos, signal)

def detectar_bandas(signal, sr, n=65536):
    Y = rfft(signal, n=n)
    freq = rfftfreq(n, 1/sr)
    mag = np.abs(Y)
    idx = np.argsort(mag)[-5:]
    return freq[idx]

def receptor_audio(signal, sr):
    bandas = detectar_bandas(signal, sr)
    f_obj = min(bandas)
    print(f"[Receptor 1] Banda detectada (piloto): ~ {f_obj:.1f} Hz")

    plt.figure()
    plt.title("Receptor 1 - Señal Piloto Visualizada")
    plt.plot(signal[:2000])
    plt.xlabel("Muestras")
    plt.show()

def receptor_texto(signal, modulador_original, sr, fc_texto, dev, expected_bits):
    # 1) Filtrado de banda alrededor de la FSK del texto
    y = bandpass(signal, sr, f_center=fc_texto, dev=dev, scale=1.5, order=6)

    # 2) Demodular con el mismo objeto (usa su Nbit y ventanas)
    modulador_original.modulada = y
    modulador_original._demodular()

    # 3) Extraer exactamente los bits esperados (sin tile)
    bits_per_bit = modulador_original.Nbit
    bits_stream = modulador_original.demodulada[::bits_per_bit]
    bits_stream = bits_stream[:expected_bits].astype(int)

    # 4) Reconstruir ASCII
    chars = []
    for i in range(0, len(bits_stream) - (len(bits_stream) % 8), 8):
        byte = bits_stream[i:i+8]
        val = 0
        for b in byte:
            val = (val << 1) | b
        chars.append(chr(val))
    mensaje = ''.join(chars)
    print(f"[Receptor 2] Mensaje decodificado: {mensaje}")
