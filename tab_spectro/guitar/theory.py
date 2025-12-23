import math

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def freq_to_midi(f: float) -> float:
    return 69.0 + 12.0 * math.log2(max(f, 1e-9) / 440.0)

def midi_to_freq(m: float) -> float:
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

def midi_to_name(m: int) -> str:
    name = NOTE_NAMES_SHARP[m % 12]
    octave = (m // 12) - 1
    return f"{name}{octave}"

def freq_to_nearest_note(f: float):
    mi = int(round(freq_to_midi(f)))
    return midi_to_name(mi), float(midi_to_freq(mi)), mi
