import threading
import sounddevice as sd
import numpy as np

class AudioPlayer:
    def __init__(self):
        self.is_playing = False
        self.playhead = 0.0
        self._out_stream = None
        self._lock = threading.Lock()

        self.loop_enabled = False
        self.loop_a = None
        self.loop_b = None

        self._audio = None 

    def set_audio(self, y: np.ndarray, sr: int, duration: float):
        self._audio = (y, sr, duration)
        self.playhead = 0.0

    def set_loop(self, enabled: bool, a: float = None, b: float = None):
        self.loop_enabled = bool(enabled)
        self.loop_a = a
        self.loop_b = b

    def play(self):
        if self._audio is None or self.is_playing:
            return
        y, sr, duration = self._audio
        self.is_playing = True

        def callback(outdata, frames, time_info, status):
            with self._lock:
                if not self.is_playing:
                    outdata[:] = 0
                    raise sd.CallbackStop

                if self.loop_enabled and self.loop_a is not None and self.loop_b is not None:
                    if self.playhead < self.loop_a or self.playhead >= self.loop_b:
                        self.playhead = float(self.loop_a)

                idx = int(self.playhead * sr)
                if idx >= len(y):
                    outdata[:] = 0
                    self.is_playing = False
                    raise sd.CallbackStop

                if self.loop_enabled and self.loop_a is not None and self.loop_b is not None:
                    loop_start = int(self.loop_a * sr)
                    loop_end = int(self.loop_b * sr)
                    loop_end = max(loop_start + 1, min(loop_end, len(y)))

                    out = np.zeros((frames,), dtype=np.float32)
                    pos = 0
                    cur = idx
                    while pos < frames:
                        if cur >= loop_end:
                            cur = loop_start
                        take = min(frames - pos, loop_end - cur)
                        out[pos:pos+take] = y[cur:cur+take]
                        pos += take
                        cur += take
                    outdata[:, 0] = out
                    self.playhead += frames / sr
                    if self.playhead >= self.loop_b:
                        self.playhead = self.loop_a + (self.playhead - self.loop_b)
                    return

                end = idx + frames
                if end >= len(y):
                    chunk = y[idx:]
                    out = np.zeros((frames,), dtype=np.float32)
                    out[:len(chunk)] = chunk
                    outdata[:, 0] = out
                    self.playhead = duration
                    self.is_playing = False
                    raise sd.CallbackStop

                outdata[:, 0] = y[idx:end]
                self.playhead += frames / sr

        sd.stop()
        self._out_stream = sd.OutputStream(
            samplerate=sr, channels=1, dtype="float32",
            callback=callback, blocksize=1024
        )
        self._out_stream.start()

    def pause(self):
        with self._lock:
            self.is_playing = False

    def stop(self):
        with self._lock:
            self.is_playing = False
        try:
            if self._out_stream:
                self._out_stream.stop()
                self._out_stream.close()
        except Exception:
            pass
        self._out_stream = None
