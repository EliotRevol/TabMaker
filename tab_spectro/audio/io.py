import os
import numpy as np
import soundfile as sf
from dataclasses import dataclass

@dataclass
class AudioData:
    y: np.ndarray
    sr: int
    duration: float

def load_audio_file(path: str) -> AudioData:
    ext = os.path.splitext(path)[1].lower()

    if ext in [".wav", ".flac", ".ogg", ".aiff", ".aif"]:
        y, sr = sf.read(path, always_2d=False)
        if y.ndim == 2:
            y = y.mean(axis=1)
        y = y.astype(np.float32)
        return AudioData(y=y, sr=int(sr), duration=float(len(y) / sr))

    if ext == ".mp3":
        try:
            from pydub import AudioSegment
        except Exception as e:
            raise RuntimeError("MP3: you need to install 'pydub' (pip install pydub) and have ffmpeg in your PATH.") from e

        try:
            seg = AudioSegment.from_file(path, format="mp3")
        except Exception as e:
            raise RuntimeError("MP3: ffmpeg missing in PATH.") from e

        seg = seg.set_channels(1)
        sr = seg.frame_rate
        samples = np.array(seg.get_array_of_samples()).astype(np.float32)

        if seg.sample_width == 2:
            samples /= 32768.0
        elif seg.sample_width == 4:
            samples /= 2147483648.0
        else:
            samples /= float(2 ** (8 * seg.sample_width - 1))

        return AudioData(y=samples, sr=int(sr), duration=float(len(samples) / sr))

    raise RuntimeError(f"Unsupported format: {ext}")
