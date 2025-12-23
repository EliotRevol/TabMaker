import numpy as np
from scipy.signal import stft, get_window
from tab_spectro.utils.settings import DEFAULT_GAMMA

def compute_spectrogram_full(y: np.ndarray, sr: int, nperseg: int, noverlap_ratio: float):
    nperseg = int(nperseg)
    noverlap = int(nperseg * float(noverlap_ratio))
    noverlap = max(0, min(noverlap, nperseg - 1))

    window = get_window("hann", nperseg, fftbins=True)
    f, t, Zxx = stft(
        y, fs=sr, window=window,
        nperseg=nperseg, noverlap=noverlap,
        boundary=None, padded=False
    )

    S = np.abs(Zxx) + 1e-10
    S_db = 20.0 * np.log10(S)

    vmax = float(np.percentile(S_db, 99.8))
    vmin = vmax - 90.0

    f = f.astype(np.float32)
    t = t.astype(np.float32)
    S_db = np.clip(S_db, vmin, vmax).astype(np.float32)

    return f, t, S_db, vmin, vmax

def render_region_to_u8(S_db_region: np.ndarray, vmin: float, vmax: float, gamma: float = DEFAULT_GAMMA):
    scaled = (S_db_region - float(vmin)) / (float(vmax) - float(vmin) + 1e-12)
    scaled = np.clip(scaled, 0.0, 1.0)
    scaled = scaled ** float(gamma)
    img_u8 = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
    return img_u8
