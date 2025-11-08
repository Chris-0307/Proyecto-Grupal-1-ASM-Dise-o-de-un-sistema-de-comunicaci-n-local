import numpy as np
import librosa
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

class AudioFFT:
    def __init__(self, audio_path=None, sr_target=None, n_fft=None, use_hann=True, top_peaks=8):
        self.audio_path = audio_path or librosa.ex('trumpet')
        self.sr_target = sr_target
        self.n_fft = n_fft
        self.use_hann = use_hann
        self.top_peaks = top_peaks

    def analyze(self, window_title="Análisis FFT de Archivo de Audio", show_plot=True):
        y, sr = librosa.load(self.audio_path, sr=self.sr_target, mono=True)
        # Pasamos el parámetro show_plot al método interno
        return self._analyze_array(y, sr, window_title=window_title, show_plot=show_plot)

    def _analyze_array(self, y, sr, window_title="Análisis FFT", show_plot=True):
        y = y / (np.max(np.abs(y)) + 1e-12)
        L = len(y)
        n_fft = self.n_fft or 1 << (L - 1).bit_length()
        win = np.hanning(min(L, n_fft)) if self.use_hann else np.ones(min(L, n_fft))
        xw = y[:len(win)] * win
        if n_fft > len(xw):
            xw = np.pad(xw, (0, n_fft - len(xw)))
        Y = np.fft.rfft(xw, n=n_fft)
        freq = np.fft.rfftfreq(n_fft, d=1.0/sr)
        mag = np.abs(Y)
        mag_db = 20 * np.log10(mag / (np.max(mag) + 1e-12) + 1e-12)
        phase = np.angle(Y)
        peaks, _ = find_peaks(mag_db, height=-50, distance=max(3, n_fft // 2048))
        peaks = peaks[freq[peaks] > 1.0]
        order = np.argsort(mag[peaks])[::-1]
        peaks = peaks[order][:self.top_peaks]

        if show_plot:
            self._plot(freq, mag_db, phase, peaks, window_title)
        
        self._summary(sr, n_fft, freq, mag_db, phase, peaks)
        
        return {
            'freq': freq, 'mag_db': mag_db, 'phase': phase, 'peaks': peaks
        }

    def _plot(self, freq, mag_db, phase, peaks, window_title):
        plt.figure(num=window_title, figsize=(12, 6))
        
        plt.subplot(2, 1, 1)
        plt.plot(freq, mag_db, color="#1f77b4")
        if len(peaks) > 0:
            plt.scatter(freq[peaks], mag_db[peaks], color="crimson", label="Picos")
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

    def _summary(self, sr, n_fft, freq, mag_db, phase, peaks):
        print(f"Samplerate: {sr} Hz")
        print(f"FFT size: {n_fft} (df ~= {sr/n_fft:.2f} Hz)")
        for i, p in enumerate(peaks, start=1):
            print(f"{i:02d}: {freq[p]:8.2f} Hz | {mag_db[p]:6.1f} dB | fase {phase[p]:+6.2f} rad")