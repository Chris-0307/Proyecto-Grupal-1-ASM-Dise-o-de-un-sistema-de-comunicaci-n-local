
# receptor_buzzer_pico_v3.py
# Reproduce SOLO el piloto en banda baja (por defecto 700–1100 Hz) sin lock.
# Criterios suaves y sin bordes falsos.

import machine, utime, math

# ---------- Pines ----------
ADC_PIN = 26        # GP26 (ADC0) entrada de la mezcla
BUZZER_PIN = 16     # GP16 (PWM) salida al buzzer (pasivo o activo)

# ---------- Muestreo ----------
FS_REAL = 8350             # ~8.35 kHz
N_SAMPLES = 197            # primo → evita “fantasmas” periódicos; Δf≈FS/N≈42.4 Hz
T_SAMPLE_US = int(1_000_000 // FS_REAL)

# ---------- Banda ESCANEADA ----------
# Para 880 Hz: 700–1100 funciona muy bien. Si cambias el piloto, ajusta aquí.
SCAN_MIN_HZ = 700
SCAN_MAX_HZ = 1100

# ---------- Criterios (relajados) ----------
SNR_MARGIN  = 4.0          # best_mag > SNR_MARGIN * mediana_ruido
DOM_MARGIN  = 1.20         # best_mag / second_mag >= DOM_MARGIN
ABS_MIN_MAG = 8e9          # piso absoluto (ajusta si hace falta)
REQ_STABLE_FRAMES = 2      # 2 frames seguidos válidos para sonar (sin lock)
SMOOTH_ALPHA = 0.40        # suavizado de la frecuencia de salida

# ---------- Preprocesado ----------
DC_ALPHA = 0.0010          # cancelación de DC lenta
USE_HANN = True            # ventaneo Hann reduce fugas
VERBOSE = True

# ---------- Pre-cálculo de bins Goertzel ----------
def build_bins():
    k_min = max(1, int(round(SCAN_MIN_HZ * N_SAMPLES / FS_REAL)))
    k_max = min((N_SAMPLES // 2) - 1, int(round(SCAN_MAX_HZ * N_SAMPLES / FS_REAL)))

    ks = list(range(k_min, k_max + 1))
    # Ignorar SIEMPRE los bordes (primer y último bin) para evitar “picos de borde”
    if len(ks) >= 3:
        ks = ks[1:-1]

    coeffs = [2.0 * math.cos(2.0 * math.pi * k / N_SAMPLES) for k in ks]
    freqs  = [k * FS_REAL / N_SAMPLES for k in ks]
    return ks, coeffs, freqs

BIN_KS, BIN_COEFFS, BIN_FREQS = build_bins()
HANN = [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (N_SAMPLES - 1)) for i in range(N_SAMPLES)] if USE_HANN else None

# ---------- HW ----------
adc = machine.ADC(machine.Pin(ADC_PIN))
pwm = machine.PWM(machine.Pin(BUZZER_PIN))
pwm.duty_u16(0)

# ---------- Estado ----------
dc_ema = 0.0
noise_med_ema = 0.0
smoothed_freq = 0.0
stable_ctr = 0

def set_buzzer(freq_hz):
    if freq_hz <= 0:
        pwm.duty_u16(0); return
    f = int(max(50, min(5000, freq_hz)))
    try:
        pwm.freq(f)
        pwm.duty_u16(24000)  # volumen; bájalo si satura
    except:
        pwm.duty_u16(0)

def parabolic_interp(mags, idx):
    if idx <= 0 or idx >= len(mags) - 1:
        return 0.0
    m1, m2, m3 = mags[idx - 1], mags[idx], mags[idx + 1]
    denom = (m1 - 2.0 * m2 + m3)
    if abs(denom) < 1e-20: return 0.0
    return 0.5 * (m1 - m3) / denom

def goertzel_frame():
    global dc_ema
    q1 = [0.0] * len(BIN_KS)
    q2 = [0.0] * len(BIN_KS)

    t0 = utime.ticks_us()
    for i in range(N_SAMPLES):
        raw = float(adc.read_u16())
        dc_ema += DC_ALPHA * (raw - dc_ema)
        s = raw - dc_ema - 32768.0
        if HANN: s *= HANN[i]

        for idx in range(len(BIN_KS)):
            q0 = BIN_COEFFS[idx] * q1[idx] - q2[idx] + s
            q2[idx] = q1[idx]
            q1[idx] = q0

        t_next = utime.ticks_add(t0, (i + 1) * T_SAMPLE_US)
        while utime.ticks_diff(t_next, utime.ticks_us()) > 0:
            pass

    mags = []
    for idx in range(len(BIN_KS)):
        mag = (q1[idx]*q1[idx]) + (q2[idx]*q2[idx]) - (BIN_COEFFS[idx]*q1[idx]*q2[idx])
        mags.append(mag if mag > 0 else 0.0)

    if not mags:
        return 0.0, 0.0, 0.0, 0.0

    best_idx = max(range(len(mags)), key=lambda i: mags[i])
    best_mag = mags[best_idx]
    second_mag = 0.0 if len(mags) == 1 else max(mags[:best_idx] + mags[best_idx+1:])

    ms = sorted(mags)
    mid = len(ms) // 2
    noise_median = 0.5 * (ms[mid - 1] + ms[mid]) if len(ms) % 2 == 0 else ms[mid]

    delta = parabolic_interp(mags, best_idx)
    k_est = BIN_KS[best_idx] + delta
    best_freq = k_est * FS_REAL / N_SAMPLES
    return best_freq, best_mag, second_mag, noise_median

def main():
    global noise_med_ema, smoothed_freq, stable_ctr
    if VERBOSE:
        print("FS={} Hz, N={}, Δf≈{:.1f} Hz | Banda {}–{} Hz | bins={}".format(
            FS_REAL, N_SAMPLES, FS_REAL/N_SAMPLES, int(BIN_FREQS[0]), int(BIN_FREQS[-1]), len(BIN_KS)))
    set_buzzer(0)
    utime.sleep_ms(200)

    # Pequeño warm-up para estimar mediana de ruido
    for _ in range(6):
        _, _, _, med = goertzel_frame()
        noise_med_ema = med if noise_med_ema == 0 else (0.7*noise_med_ema + 0.3*med)

    while True:
        best_f, best_mag, second_mag, noise_med = goertzel_frame()
        noise_med_ema = 0.9*noise_med_ema + 0.1*noise_med if noise_med_ema > 0 else noise_med

        snr_ok = best_mag > (SNR_MARGIN * (noise_med_ema + 1.0))
        dom_ok = (second_mag <= 0) or (best_mag / (second_mag + 1.0) >= DOM_MARGIN)
        abs_ok = best_mag >= ABS_MIN_MAG

        if snr_ok and dom_ok and abs_ok:
            stable_ctr = min(stable_ctr + 1, REQ_STABLE_FRAMES)
            if stable_ctr >= REQ_STABLE_FRAMES:
                smoothed_freq = best_f if smoothed_freq <= 0 else (1.0 - SMOOTH_ALPHA)*smoothed_freq + SMOOTH_ALPHA*best_f
                set_buzzer(smoothed_freq)
                if VERBOSE:
                    print("f≈{:.0f} Hz | mag={:.2e} | 2nd={:.2e} | med={:.2e}".format(
                        smoothed_freq, best_mag, second_mag, noise_med_ema))
        else:
            stable_ctr = 0
            smoothed_freq = 0.0
            set_buzzer(0)
            if VERBOSE:
                print("— silencio —   best={:.0f}Hz  mag={:.2e}  2nd={:.2e}  med={:.2e}".format(
                    best_f, best_mag, second_mag, noise_med_ema))

        utime.sleep_ms(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pwm.duty_u16(0)
        print("\nDetenido.")

