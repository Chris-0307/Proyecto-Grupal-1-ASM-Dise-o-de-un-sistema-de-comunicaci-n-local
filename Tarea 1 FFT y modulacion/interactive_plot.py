import matplotlib.pyplot as plt
from matplotlib.widgets import Button

class InteractivePlotter:
    def __init__(self, time_data, fft_data, punto2_data, punto2_title):
        self.time_data = time_data
        self.fft_data = fft_data
        # Añadimos los datos del punto 2 al diccionario de FFTs
        self.fft_data['punto2'] = punto2_data
        self.punto2_title = punto2_title
        
        self.t = self.time_data['t']
        self.fig = plt.figure(figsize=(12, 8))
        self.fig.canvas.manager.set_window_title('Visualizador Interactivo de Tarea')

        # Dibujar la vista inicial
        self.draw_time_domain(None)

    def show(self):
        plt.show()
        
    def _setup_buttons(self):
        """Crea los botones y los conecta a las funciones. Se llama en cada redibujado."""
        # Definimos posiciones para 5 botones
        ax_btn_p2 = plt.axes([0.05, 0.05, 0.16, 0.075])
        ax_btn_time = plt.axes([0.25, 0.05, 0.16, 0.075])
        ax_btn_fft_msg = plt.axes([0.45, 0.05, 0.16, 0.075])
        ax_btn_fft_mod = plt.axes([0.65, 0.05, 0.16, 0.075])
        ax_btn_fft_demod = plt.axes([0.85, 0.05, 0.16, 0.075])

        btn_p2 = Button(ax_btn_p2, 'Punto 2: Audio')
        btn_time = Button(ax_btn_time, 'Tiempo FSK')
        btn_fft_msg = Button(ax_btn_fft_msg, 'FFT Mensaje')
        btn_fft_mod = Button(ax_btn_fft_mod, 'FFT Modulada')
        btn_fft_demod = Button(ax_btn_fft_demod, 'FFT Demodulada')
        
        # Guardamos los botones como atributos para que no sean eliminados por el garbage collector
        self.buttons = [btn_p2, btn_time, btn_fft_msg, btn_fft_mod, btn_fft_demod]
        
        btn_p2.on_clicked(self.draw_fft_punto2)
        btn_time.on_clicked(self.draw_time_domain)
        btn_fft_msg.on_clicked(self.draw_fft_message)
        btn_fft_mod.on_clicked(self.draw_fft_modulated)
        btn_fft_demod.on_clicked(self.draw_fft_demodulated)

    def draw_time_domain(self, event):
        self.fig.clf()
        self._setup_buttons()

        import numpy as np  # por si no estaba

        plt.suptitle('Punto 5: Proceso de Modulación/Demodulación FSK en el Tiempo', fontsize=16)
        self.fig.subplots_adjust(top=0.92, bottom=0.2, hspace=0.6)

        ax1, ax2, ax3, ax4 = self.fig.subplots(4, 1, sharex=True)

        ax1.plot(self.t, self.time_data['mensaje'], label="Mensaje (Bits 0/1)")
        ax1.set_title("Señal de Mensaje (NRZ)")
        ax1.legend(loc="upper right"); ax1.grid(True, alpha=0.5)

        ax2.plot(self.t, self.time_data['portadora'], label="Portadora (ref)", color="orange")
        ax2.set_title("Portadora"); ax2.legend(loc="upper right"); ax2.grid(True, alpha=0.5)

        ax3.plot(self.t, self.time_data['modulada'], label="FSK", color="green", lw=1.0)
        ax3.set_title("Señal Modulada (FSK)")
        ax3.legend(loc="upper right"); ax3.grid(True, alpha=0.5)

        y = self.time_data.get('demodulada', None)
        if y is None or len(y) != len(self.t):
            print("ADVERTENCIA: demodulada no está lista o longitudes no coinciden.")
            return

        ax4.plot(self.t, y, label="Demodulada (recuperada)", color="red", lw=2.0)
        ax4.set_title("Señal Demodulada (Recuperada)")
        ax4.set_xlabel("Tiempo (s)")
        ax4.legend(loc="upper right"); ax4.grid(True, alpha=0.5)

        # mostrar ~5 bits y asegurar visibilidad en Y
        ax4.set_xlim(0, 5 / self.time_data['fm'])
        ax4.set_ylim(-0.1, 1.1)  # <- hace que 0/1 siempre se vean

        self.fig.canvas.draw_idle()


    def _draw_fft_plot(self, key, title):
        self.fig.clf() # Limpia la figura entera
        self._setup_buttons() # Redibuja los botones

        plt.suptitle(title, fontsize=16)
        self.fig.subplots_adjust(top=0.92, bottom=0.2, hspace=0.4)

        data = self.fft_data[key]
        freq, mag_db, phase, peaks = data['freq'], data['mag_db'], data['phase'], data['peaks']
        
        ax_mag, ax_phase = self.fig.subplots(2, 1)

        ax_mag.plot(freq, mag_db, color="#1f77b4")
        if len(peaks) > 0:
            ax_mag.scatter(freq[peaks], mag_db[peaks], color="crimson", label="Picos")
        ax_mag.set_title("Espectro de Magnitud (dBFS)")
        ax_mag.set_xlabel("Frecuencia (Hz)")
        ax_mag.set_ylabel("Magnitud (dB)")
        ax_mag.grid(True, alpha=0.3)
        ax_mag.legend(loc="best")

        ax_phase.plot(freq, phase, color="#2ca02c")
        ax_phase.set_title("Fase (rad)")
        ax_phase.set_xlabel("Frecuencia (Hz)")
        ax_phase.set_ylabel("Fase (rad)")
        ax_phase.grid(True, alpha=0.3)
        
        self.fig.canvas.draw_idle()

    def draw_fft_punto2(self, event):
        self._draw_fft_plot('punto2', self.punto2_title)

    def draw_fft_message(self, event):
        self._draw_fft_plot('mensaje', 'Punto 5: FFT - Señal de Mensaje (Cuadrada)')

    def draw_fft_modulated(self, event):
        self._draw_fft_plot('modulada', 'Punto 5: FFT - Señal Modulada (FSK)')

    def draw_fft_demodulated(self, event):
        self._draw_fft_plot('demodulada', 'Punto 5: FFT - Señal Demodulada')