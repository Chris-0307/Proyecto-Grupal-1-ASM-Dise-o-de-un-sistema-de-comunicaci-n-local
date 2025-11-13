# modulacion.py — FSK binaria con opción de portadora cuadrada por bit
import numpy as np
from audio_fft import AudioFFT

def texto_a_bits(texto: str):
    bits = []
    for c in texto.encode("ascii"):
        for i in range(8):
            bits.append((c >> (7-i)) & 1)
    return np.array(bits, dtype=int)

class ModuladorFSK:
    """
    BFSK (0 -> f0 = fc - dev, 1 -> f1 = fc + dev) con mensaje NRZ 0/1.
    Permite elegir la forma de onda transmitida:
      - tx_waveform="cos": coseno clásico a f_inst (por defecto)
      - tx_waveform="square": onda cuadrada ±1 a f0/f1 por cada bit

    Demodulación no coherente por correlación I/Q ventana-a-ventana (Nbit).
    """
    def __init__(self, freq_mensaje, freq_portadora, duracion, sr,
                 fft_analyzer: AudioFFT, freq_dev=500.0, bits=None,
                 tx_waveform: str = "cos"):
        # freq_mensaje se interpreta como bit_rate (bps)
        self.bit_rate = float(freq_mensaje)
        self.fc = float(freq_portadora)
        self.T = float(duracion)
        self.sr = int(sr)
        self.freq_dev = float(freq_dev)
        self.f0 = self.fc - self.freq_dev
        self.f1 = self.fc + self.freq_dev

        self.fft_analyzer = fft_analyzer
        self.bits_in = bits  # opcional: lista/array de 0/1

        self.t = np.linspace(0, self.T, int(self.sr * self.T), endpoint=False)
        self.N = len(self.t)

        self.Nbit = max(1, int(round(self.sr / self.bit_rate)))  # muestras por bit
        self.n_bits = max(1, int(np.ceil(self.N / self.Nbit)))   # nº de bits que caben

        # señales
        self.mensaje = None      # 0/1 NRZ (longitud N)
        self.portadora = None    # coseno de referencia (para graficar)
        self.modulada = None     # señal FSK transmitida (cos o cuadrada)
        self.demodulada = None   # 0/1 recuperado (escalones)
        self.demod_soft = None   # métrica suave opcional

        # nueva opción de forma de onda TX
        assert tx_waveform in ("cos", "square")
        self.tx_waveform = tx_waveform

    # ----------------- helpers -----------------
    def _build_bits_aligned(self):
        """Genera vector de bits (0/1) alineado con la ventana de decisión."""
        if self.bits_in is None:
            # Patrón 0,1,0,1,... por simplicidad de demo
            bits = (np.arange(self.n_bits) & 1).astype(int)
        else:
            b = np.array(self.bits_in, dtype=int) & 1
            if len(b) < self.n_bits:
                reps = int(np.ceil(self.n_bits / len(b)))
                bits = np.tile(b, reps)[:self.n_bits]
            else:
                bits = b[:self.n_bits]
        return bits

    # ----------------- pipeline -----------------
    def _generar_senales(self):
        bits = self._build_bits_aligned()

        # NRZ 0/1 perfectamente alineada a Nbit (para graficar y FFT del mensaje)
        msg = np.repeat(bits, self.Nbit)
        if len(msg) < self.N:
            msg = np.pad(msg, (0, self.N - len(msg)), mode="edge")
        else:
            msg = msg[:self.N]
        self.mensaje = msg.astype(float)
        self.bits_tx = bits.astype(float)

        # Portadora de referencia (solo para trazar)
        self.portadora = np.cos(2 * np.pi * self.fc * self.t)

    def _modular(self):
        """
        Si tx_waveform='cos': coseno a f_inst con fase continua.
        Si tx_waveform='square': por cada bit se genera un segmento cuadrado ±1
        a f0 (bit=0) o f1 (bit=1), y se concatenan los Nbit samples.
        """
        if self.tx_waveform == "cos":
            # FSK clásica variando frecuencia instantánea con fase continua
            f_bit = np.where(self.bits_tx > 0.5, self.f1, self.f0)
            f_inst = np.repeat(f_bit, self.Nbit)
            if len(f_inst) < self.N:
                f_inst = np.pad(f_inst, (0, self.N - len(f_inst)), mode="edge")
            else:
                f_inst = f_inst[:self.N]

            phase = 2 * np.pi * np.cumsum(f_inst) / self.sr
            self.modulada = np.cos(phase)

        else:  # tx_waveform == "square"
            # Construcción pieza a pieza por bit (fase se reinicia por bit)
            x = np.empty(self.n_bits * self.Nbit, dtype=float)
            for i in range(self.n_bits):
                f = self.f1 if self.bits_tx[i] > 0.5 else self.f0
                n = np.arange(self.Nbit) / self.sr
                # cuadrada ±1; evito 0 exacto con eps para consistencia
                seg = np.sign(np.sin(2 * np.pi * f * n))
                seg[seg == 0] = 1.0
                x[i*self.Nbit:(i+1)*self.Nbit] = seg
            # Ajuste a longitud N
            if len(x) < self.N:
                x = np.pad(x, (0, self.N - len(x)), mode="edge")
            else:
                x = x[:self.N]
            self.modulada = x

    def _demodular(self):
        x = self.modulada
        Nbit = self.Nbit
        n_bits = self.n_bits

        # Referencias exactas por tamaño de bit (evita desalineación)
        n = np.arange(Nbit) / self.sr
        c0, s0 = np.cos(2*np.pi*self.f0*n), np.sin(2*np.pi*self.f0*n)
        c1, s1 = np.cos(2*np.pi*self.f1*n), np.sin(2*np.pi*self.f1*n)

        E0 = np.empty(n_bits)
        E1 = np.empty(n_bits)
        decisions = np.empty(n_bits, dtype=int)

        for i in range(n_bits):
            seg = x[i*Nbit:(i+1)*Nbit]
            if len(seg) < Nbit:
                seg = np.pad(seg, (0, Nbit - len(seg)), mode="edge")

            # Correlación I/Q normalizada
            scale = (2.0 / Nbit)
            I0 = scale * np.dot(seg, c0); Q0 = scale * np.dot(seg, s0)
            I1 = scale * np.dot(seg, c1); Q1 = scale * np.dot(seg, s1)
            E0[i] = I0*I0 + Q0*Q0
            E1[i] = I1*I1 + Q1*Q1
            decisions[i] = 1 if E1[i] > E0[i] else 0

        # Señal recuperada como escalones 0/1
        demod_bits = np.repeat(decisions, Nbit)
        if len(demod_bits) < self.N:
            demod_bits = np.pad(demod_bits, (0, self.N - len(demod_bits)), mode="edge")
        else:
            demod_bits = demod_bits[:self.N]
        self.demodulada = demod_bits.astype(float)

        # Métrica "suave" (debug)
        self.demod_soft = (E1 - E0) / (np.abs(E1) + np.abs(E0) + 1e-12)

        # Debug corto
        print("FSK DEBUG -> Nbit:", Nbit,
              "f0/f1:", self.f0, self.f1,
              "TX:", self.tx_waveform)
        print("Decisiones (primeros 12 bits):", decisions[:12])

    def run_simulation_and_get_data(self):
        self._generar_senales()
        self._modular()
        self._demodular()

        time_data = {
            't': self.t,
            'fm': self.bit_rate,         # aquí es bit_rate
            'mensaje': self.mensaje,     # 0/1 NRZ alineada
            'portadora': self.portadora,
            'modulada': self.modulada,   # ahora puede ser cuadrada o coseno
            'demodulada': self.demodulada
        }

        # FFTs (sin gráficos)
        print("\n\n=== Calculando FFT del Mensaje (0/1) ===")
        fft_data_msg = self.fft_analyzer._analyze_array(self.mensaje, self.sr, show_plot=False)

        print("\n\n=== Calculando FFT de la Señal FSK ===")
        fft_data_mod = self.fft_analyzer._analyze_array(self.modulada, self.sr, show_plot=False)

        print("\n\n=== Calculando FFT de la Señal Demodulada ===")
        fft_data_demod = self.fft_analyzer._analyze_array(self.demodulada, self.sr, show_plot=False)

        fft_data = {
            'mensaje': fft_data_msg,
            'modulada': fft_data_mod,
            'demodulada': fft_data_demod
        }
        return time_data, fft_data
    
class TransmisorFSK:
    def __init__(self, sr):
        self.sr = sr

    def transmitir(self, texto_ascii, duracion, fc_texto, fc_piloto, dev, bit_rate):
        bits = texto_a_bits(texto_ascii)

        # 1) Generar señal FSK para el mensaje de texto
        mod_texto = ModuladorFSK(
            freq_mensaje=bit_rate,
            freq_portadora=fc_texto,
            duracion=duracion,
            sr=self.sr,
            fft_analyzer=None,
            freq_dev=dev,
            bits=bits,
            tx_waveform="cos"
        )
        mod_texto._generar_senales()
        mod_texto._modular()

        # 2) Señal piloto
        t = mod_texto.t
        piloto = np.sin(2*np.pi * fc_piloto * t)

        # 3) Sumar ambas señales → transmisión simultánea
        señal_tx = mod_texto.modulada + piloto

        return t, señal_tx, mod_texto

