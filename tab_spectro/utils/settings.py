from dataclasses import dataclass

@dataclass
class SpectroQuality:
    name: str
    nperseg: int
    noverlap_ratio: float

QUALITIES = [
    SpectroQuality("Rapide", 4096, 0.75),
    SpectroQuality("Fin", 8192, 0.80),
    SpectroQuality("Très fin", 16384, 0.85),
    SpectroQuality("Ultra", 32768, 0.90),
]

DEFAULT_HARD_FMIN = 70.0
DEFAULT_HARD_FMAX = 600.0

DEFAULT_GAMMA = 1.6

MIC_FMIN = 70.0
MIC_FMAX = 2500.0
MIC_MAX_LINES = 24
MIC_LINE_WIDTH = 7
MIC_BASE_GREEN = 90
MIC_MAX_GREEN = 210
MIC_ALPHA_MIN = 110
MIC_ALPHA_MAX = 230
