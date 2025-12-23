# tab_spectro/audio/synth.py
import numpy as np
import sounddevice as sd
from tab_spectro.guitar.theory import midi_to_freq

#Making our own guitar sounds instead of having mp3 files 

def _karplus_strong(freq: float,
                    sr: int,
                    dur: float,
                    pick: float = 0.6, #harshness
                    decay: float = 0.997, #sustain
                    damp: float = 0.20, #bigger=darker
                    brightness: float = 0.55 #bigger=brighter
) -> np.ndarray:
    freq = max(20.0, float(freq))
    N = max(2, int(sr / freq))  # taille du buffer
    n_samples = int(sr * dur)
    noise = (np.random.rand(N).astype(np.float32) * 2.0 - 1.0)

    k = 5
    kernel = np.ones(k, dtype=np.float32) / k
    noise_lp = np.convolve(noise, kernel, mode="same").astype(np.float32)

    #pick effect
    exc = ((1.0 - pick) * noise_lp + pick * noise).astype(np.float32)


    buf = exc.copy()
    out = np.zeros(n_samples, dtype=np.float32)

    # low-pass one-pole state
    lp = 0.0
    br = float(np.clip(brightness, 0.0, 1.0))
    dm = float(np.clip(damp, 0.0, 1.0))

    for i in range(n_samples):
        x0 = buf[i % N]
        x1 = buf[(i + 1) % N]
        avg = 0.5 * (x0 + x1)

        # decay
        y = decay * avg

        # damp
        lp = (1.0 - dm) * y + dm * lp

        # brightness
        val = br * y + (1.0 - br) * lp

        buf[i % N] = val
        out[i] = val

    mx = float(np.max(np.abs(out)) + 1e-9)
    out = out / mx
    return out.astype(np.float32)

def _envelope(x: np.ndarray, sr: int, attack=0.01, release=0.35) -> np.ndarray:
    n = len(x)
    aN = max(1, int(sr * attack))
    rN = max(1, int(sr * release))
    env = np.ones(n, dtype=np.float32)
    env[:aN] *= np.linspace(0, 1, aN, dtype=np.float32)
    env[-rN:] *= np.linspace(1, 0, rN, dtype=np.float32)
    return x * env

def synth_chord(midis,
                sr: int = 44100,
                dur: float = 1.2,
                gain: float = 0.24,      
                pick: float = 0.10,      
                decay: float = 0.9989,  
                damp: float = 0.54,
                brightness: float = 0.24
) -> tuple[np.ndarray, int]:
    midis = list(dict.fromkeys([int(m) for m in (midis or []) if m is not None]))
    if not midis:
        return np.zeros(int(sr * dur), dtype=np.float32), sr

    freqs = [(m, midi_to_freq(m)) for m in sorted(midis)]
    n = int(sr * dur)
    out = np.zeros(n, dtype=np.float32)

    # strum max ~10ms
    max_delay = int(sr * 0.010) 
    delays = np.linspace(0, max_delay, num=len(freqs)).astype(int)

    for (m, f), d in zip(freqs, delays):
        local_pick = float(np.clip(pick + np.random.uniform(-0.05, 0.05), 0.0, 1.0))
        local_decay = float(np.clip(decay + np.random.uniform(-0.0006, 0.0006), 0.990, 0.9998))
        local_damp = float(np.clip(damp + np.random.uniform(-0.03, 0.03), 0.0, 0.95))
        local_bright = float(np.clip(brightness + np.random.uniform(-0.05, 0.05), 0.0, 1.0))

        s = _karplus_strong(
            f, sr, dur,
            pick=local_pick,
            decay=local_decay,
            damp=local_damp,
            brightness=local_bright
        )
        s = _envelope(s, sr, attack=0.003, release=0.25)

        if d > 0:
            s2 = np.zeros_like(s)
            s2[d:] = s[:-d]
            s = s2

        out += s

    out /= max(1.0, float(len(freqs)) * 0.85)
    out *= float(gain)

    mx = float(np.max(np.abs(out)) + 1e-9)
    if mx > 0.98:
        out *= (0.98 / mx)
    
    # --- soft low-pass (nylon vibe) ---
    # simple 1-pole filter: y[n] = a*y[n-1] + (1-a)*x[n]
    a = 0.88 
    lp = np.zeros_like(out, dtype=np.float32)
    prev = 0.0
    for i in range(len(out)):
        prev = a * prev + (1.0 - a) * float(out[i])
        lp[i] = prev

    air = out - lp
    out = lp + 0.18 * air 

    return out.astype(np.float32), sr

def play_midis(midis, sr: int = 44100, dur: float = 1.0):
    x, sr = synth_chord(midis, sr=sr, dur=dur)
    sd.stop()
    sd.play(x, sr, blocking=False)
