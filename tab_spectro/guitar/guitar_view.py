from PySide6 import QtCore, QtWidgets, QtGui
from tab_spectro.guitar.theory import midi_to_name
from tab_spectro.audio.synth import play_midis
import math
from tab_spectro.guitar.theory import midi_to_freq, midi_to_name


class GuitarGridWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 260)

        # Standard tuning MIDI, top->bottom: E4 B3 G3 D3 A2 E2
        self.tuning_midi = [64, 59, 55, 50, 45, 40]
        self.max_fret = 15

        self.selected_midis = []
        self.midi_to_color = {}

        self._show_note_text = True
        self._dark_theme = True

        self.setMouseTracking(True)
        self._hover_timer = QtCore.QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)  # 0.5s
        self._hover_timer.timeout.connect(self._show_hover_tooltip)

        self._hover_cell = None  
        self._hover_global_pos = None


    def _cell_at_pos(self, pos: QtCore.QPointF):
        rect = self.rect()
        margin = 18
        title_h = 32
        inner = QtCore.QRectF(
            rect.left() + margin,
            rect.top() + margin + title_h,
            rect.width() - 2 * margin,
            rect.height() - 2 * margin - title_h
        )
        if not inner.contains(pos):
            return None

        strings = 6
        frets = self.max_fret + 1

        cell_w = inner.width() / frets
        cell_h = inner.height() / strings

        fret = int((pos.x() - inner.left()) / cell_w)
        string_idx = int((pos.y() - inner.top()) / cell_h)

        if fret < 0 or fret >= frets or string_idx < 0 or string_idx >= strings:
            return None
        return (string_idx, fret)

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent):
        cell = self._cell_at_pos(ev.position())
        gp = ev.globalPosition().toPoint()

        if cell != self._hover_cell:
            self._hover_cell = cell
            self._hover_global_pos = gp
            QtWidgets.QToolTip.hideText()
            self._hover_timer.stop()

            if cell is not None:
                self._hover_timer.start()
        else:
            self._hover_global_pos = gp

        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev: QtCore.QEvent):
        self._hover_timer.stop()
        self._hover_cell = None
        self._hover_global_pos = None
        QtWidgets.QToolTip.hideText()
        super().leaveEvent(ev)

    def _show_hover_tooltip(self):
        if self._hover_cell is None or self._hover_global_pos is None:
            return
        s, f = self._hover_cell
        midi = self._midi_at(s, f)
        name = midi_to_name(midi)
        hz = midi_to_freq(midi)

        QtWidgets.QToolTip.showText(
            self._hover_global_pos,
            f"{name} — {hz:.1f} Hz",
            self
        )


    def set_selected_midis(self, midis):
        self.selected_midis = list(dict.fromkeys(midis or []))
        self.update()

    def set_show_note_text(self, on: bool):
        self._show_note_text = bool(on)
        self.update()

    def set_dark_theme(self, on: bool):
        self._dark_theme = bool(on)
        self.update()

    def _midi_at(self, string_idx: int, fret: int) -> int:
        return self.tuning_midi[string_idx] + fret

    def _color_for_midi(self, m: int) -> QtGui.QColor:
        if m in self.midi_to_color:
            return self.midi_to_color[m]
        palette = [
            QtGui.QColor(0, 200, 0, 190),
            QtGui.QColor(255, 0, 0, 190),
            QtGui.QColor(0, 140, 255, 190),
            QtGui.QColor(255, 140, 0, 190),
            QtGui.QColor(180, 0, 255, 190),
            QtGui.QColor(0, 220, 220, 190),
        ]
        c = palette[len(self.midi_to_color) % len(palette)]
        self.midi_to_color[m] = c
        return c

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        if self._dark_theme:
            bg = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            bg.setColorAt(0.0, QtGui.QColor(20, 16, 12))
            bg.setColorAt(1.0, QtGui.QColor(40, 28, 20))
        else:
            bg = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            bg.setColorAt(0.0, QtGui.QColor(245, 240, 232))
            bg.setColorAt(1.0, QtGui.QColor(230, 220, 205))
        p.fillRect(rect, bg)

        margin = 18
        title_h = 32
        inner = QtCore.QRectF(
            rect.left() + margin,
            rect.top() + margin + title_h,
            rect.width() - 2 * margin,
            rect.height() - 2 * margin - title_h
        )

        title_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Weight.DemiBold)
        p.setFont(title_font)
        p.setPen(QtGui.QColor(245, 245, 245) if self._dark_theme else QtGui.QColor(25, 25, 25))
        p.drawText(QtCore.QRectF(rect.left()+margin, rect.top()+margin, rect.width()-2*margin, title_h),
                   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                   "Guitar View — Fretboard (Standard tuning)")

        strings = 6
        frets = self.max_fret + 1

        cell_w = inner.width() / frets
        cell_h = inner.height() / strings

        # Frets
        nut_pen = QtGui.QPen(QtGui.QColor(230, 230, 230, 210) if self._dark_theme else QtGui.QColor(30, 30, 30, 220))
        nut_pen.setWidth(6)
        fret_pen = QtGui.QPen(QtGui.QColor(220, 220, 220, 140) if self._dark_theme else QtGui.QColor(30, 30, 30, 120))
        fret_pen.setWidth(2)

        for f in range(frets + 1):
            x = inner.left() + f * cell_w
            p.setPen(nut_pen if f == 1 else fret_pen)
            p.drawLine(QtCore.QPointF(x, inner.top()), QtCore.QPointF(x, inner.bottom()))

        # Strings
        string_pen = QtGui.QPen(QtGui.QColor(240, 240, 240, 170) if self._dark_theme else QtGui.QColor(20, 20, 20, 140))
        string_pen.setWidth(3)
        for s in range(strings):
            y = inner.top() + (s + 0.5) * cell_h
            p.setPen(string_pen)
            p.drawLine(QtCore.QPointF(inner.left(), y), QtCore.QPointF(inner.right(), y))

        # Fret numbers
        p.setFont(QtGui.QFont("Segoe UI", 9))
        p.setPen(QtGui.QColor(235, 235, 235, 200) if self._dark_theme else QtGui.QColor(30, 30, 30, 200))
        for f in range(1, frets):
            x = inner.left() + (f + 0.5) * cell_w
            p.drawText(QtCore.QRectF(x - cell_w/2, inner.bottom() + 4, cell_w, 18),
                       QtCore.Qt.AlignmentFlag.AlignCenter, str(f))

        p.setFont(QtGui.QFont("Segoe UI", 8))
        selected_set = set(self.selected_midis)
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        for s in range(strings):
            for f in range(frets):
                x0 = inner.left() + f * cell_w
                y0 = inner.top() + s * cell_h
                cell = QtCore.QRectF(x0, y0, cell_w, cell_h)

                m = self._midi_at(s, f)
                name = midi_to_name(m)

                p.setPen(QtGui.QColor(255, 255, 255, 25) if self._dark_theme else QtGui.QColor(0, 0, 0, 18))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRect(cell)

                if self._show_note_text:
                    p.setPen(QtGui.QColor(245, 245, 245, 180) if self._dark_theme else QtGui.QColor(25, 25, 25, 170))
                    p.drawText(cell, QtCore.Qt.AlignmentFlag.AlignCenter, name)

                if m in selected_set:
                    center = cell.center()
                    r = min(cell_w, cell_h) * 0.28

                    ring = QtGui.QPen(QtGui.QColor(0, 0, 0, 190))
                    ring.setWidth(3)
                    p.setPen(ring)
                    p.setBrush(QtGui.QBrush(self._color_for_midi(m)))
                    p.drawEllipse(center, r, r)
                    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        p.end()

class GuitarViewWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guitar View")
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)

        self._pinned = False

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        topbar = QtWidgets.QHBoxLayout()
        layout.addLayout(topbar)

        self.btn_pin = QtWidgets.QToolButton()
        self.btn_pin.setText("📌")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setToolTip("Always on top")
        self.btn_pin.toggled.connect(self.set_pinned)
        topbar.addWidget(self.btn_pin)

        self.btn_play = QtWidgets.QToolButton()
        self.btn_play.setText("▶ Play")
        self.btn_play.setToolTip("Play selected notes")
        self.btn_play.clicked.connect(self.play_selected_notes)
        topbar.addWidget(self.btn_play)

        self.chk_text = QtWidgets.QCheckBox("Show notes values")
        self.chk_text.setChecked(True)
        topbar.addWidget(self.chk_text)

        self.chk_dark = QtWidgets.QCheckBox("Dark theme")
        self.chk_dark.setChecked(True)
        topbar.addWidget(self.chk_dark)

        topbar.addStretch(1)

        self.grid = GuitarGridWidget()
        layout.addWidget(self.grid)

        self.chk_text.toggled.connect(self.grid.set_show_note_text)
        self.chk_dark.toggled.connect(self.grid.set_dark_theme)

    def set_pinned(self, pinned: bool):
        self._pinned = bool(pinned)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, self._pinned)
        self.show()

    def set_selected_midis(self, midis):
        self.grid.set_selected_midis(midis)

    def play_selected_notes(self):
        midis = list(getattr(self.grid, "selected_midis", []) or [])
        if not midis:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "No selected notes")
            return
        dur = 0.65 if len(midis) >= 4 else 0.9
        try:
            play_midis(midis, sr=44100, dur=dur)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Audio", f"Can't play notes:\n{e}")
