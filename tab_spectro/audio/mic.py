import numpy as np
from scipy.signal import find_peaks

def extract_mic_peaks(x: np.ndarray, fs: int, fmin: float, fmax: float, max_lines: int):
    x = x.astype(np.float32)
    x = x - np.mean(x)
    rms = float(np.sqrt(np.mean(x * x) + 1e-12))
    if rms < 0.004:
        return [], []

    N = len(x)
    w = np.hanning(N).astype(np.float32)
    X = np.fft.rfft(x * w)
    mag = np.abs(X)
    freqs = np.array(np.fft.rfftfreq(N, d=1.0 / fs), dtype=np.float32)

    mask = (freqs >= float(fmin)) & (freqs <= float(fmax))
    freqs_b = freqs[mask]
    mag_b = mag[mask]
    if len(mag_b) < 10:
        return [], []

    mmax = float(np.max(mag_b))
    if mmax <= 1e-9:
        return [], []

    floor = float(np.median(mag_b))
    prominence = max(mmax * 0.02, floor * 3.0)

    peaks, _ = find_peaks(mag_b, prominence=prominence, distance=2)
    if len(peaks) == 0:
        return [], []

    pf = freqs_b[peaks]
    pa = mag_b[peaks]
    order = np.argsort(-pa)
    pf = pf[order][: int(max_lines)]
    pa = pa[order][: int(max_lines)]
    return pf.astype(float).tolist(), pa.astype(float).tolist()
