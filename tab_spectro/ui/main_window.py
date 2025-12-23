import os
import queue

import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets, QtGui

from tab_spectro.audio.io import load_audio_file, AudioData
from tab_spectro.audio.spectrogram import compute_spectrogram_full, render_region_to_u8
from tab_spectro.audio.playback import AudioPlayer
from tab_spectro.audio.mic import extract_mic_peaks
from tab_spectro.guitar.theory import freq_to_nearest_note
from tab_spectro.guitar.guitar_view import GuitarViewWindow
from tab_spectro.graphics.viewbox import SpectroViewBox
from tab_spectro.ui.docks import build_controls_dock, build_notes_dock
from tab_spectro.ui.actions import build_actions, build_menus_and_toolbar
from tab_spectro.utils.settings import (
    QUALITIES, DEFAULT_HARD_FMIN, DEFAULT_HARD_FMAX, DEFAULT_GAMMA,
    MIC_FMIN, MIC_FMAX, MIC_MAX_LINES, MIC_LINE_WIDTH, MIC_BASE_GREEN,
    MIC_MAX_GREEN, MIC_ALPHA_MIN, MIC_ALPHA_MAX
)

def make_audacity_lut(n: int = 256) -> np.ndarray:
    stops = [
        (0.00, (0, 0, 0)),
        (0.25, (0, 0, 120)),
        (0.45, (0, 120, 255)),
        (0.70, (255, 120, 0)),
        (0.88, (255, 220, 0)),
        (1.00, (255, 255, 160)),
    ]
    lut = np.zeros((n, 3), dtype=np.uint8)
    xs = np.linspace(0, 1, n)
    for i, x in enumerate(xs):
        for j in range(len(stops) - 1):
            x0, c0 = stops[j]
            x1, c1 = stops[j + 1]
            if x0 <= x <= x1:
                t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
                r = int(round(c0[0] + t * (c1[0] - c0[0])))
                g = int(round(c0[1] + t * (c1[1] - c0[1])))
                b = int(round(c0[2] + t * (c1[2] - c0[2])))
                lut[i] = (r, g, b)
                break
    return lut

class TabSpectroMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tab Maker Helper")
        self.resize(1750, 980)

        self.audio: AudioData | None = None

        self.f = None
        self.t = None
        self.S_db = None
        self.db_vmin = None
        self.db_vmax = None

        self.hard_fmin = DEFAULT_HARD_FMIN
        self.hard_fmax = DEFAULT_HARD_FMAX
        self.gamma = DEFAULT_GAMMA

        # quality
        self.quality_name = "Très fin"
        self.nperseg = 16384
        self.noverlap_ratio = 0.85

        # player
        self.player = AudioPlayer()

        # loop region
        self.loop_region = None
        self._loop_dragging = False
        self._loop_anchor_t = 0.0

        # mic
        self.mic_enabled = False
        self._mic_stream = None
        self._mic_q = queue.Queue()
        self.mic_fmin = MIC_FMIN
        self.mic_fmax = MIC_FMAX
        self.mic_max_lines = MIC_MAX_LINES
        self.mic_line_width = MIC_LINE_WIDTH
        self.mic_base_green = MIC_BASE_GREEN
        self.mic_max_green = MIC_MAX_GREEN
        self.mic_alpha_min = MIC_ALPHA_MIN
        self.mic_alpha_max = MIC_ALPHA_MAX
        self._mic_lines = []

        # crosses
        self.cross_points = []

        # Guitar view
        self.guitar_window = None

        # guards
        self._in_render = False
        self._updating_scroll = False
        self._suspend_render = False

        self._build_central()
        self._build_ui()
        self._build_timers()

        self.statusBar().showMessage("Ready. Open-> File to open a music.")

    def _build_central(self):
        spectroPane = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(spectroPane)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)

        self.vb = SpectroViewBox()
        self.plot = pg.PlotWidget(viewBox=self.vb)
        self.plot.setLabel("left", "Frequency (Hz)")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setMenuEnabled(False)

        self.plot.installEventFilter(self)
        self.plot.viewport().installEventFilter(self)
        self.plot.scene().installEventFilter(self)


        grid.addWidget(self.plot, 0, 0, 1, 1)

        self.vscroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical)
        self.vscroll.setEnabled(False)
        self.vscroll.setMinimumWidth(18)
        grid.addWidget(self.vscroll, 0, 1, 1, 1)

        self.hscroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal)
        self.hscroll.setEnabled(False)
        self.hscroll.setMinimumHeight(20)
        grid.addWidget(self.hscroll, 1, 0, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setRowStretch(0, 1)

        self.setCentralWidget(spectroPane)

        self.lut = make_audacity_lut(256)

        self.img = pg.ImageItem()
        self.img.setLookupTable(self.lut)
        self.plot.addItem(self.img)

        self.play_line = pg.InfiniteLine(pos=0, angle=90, movable=True, pen=pg.mkPen(width=2))
        self.play_line.setZValue(30)
        self.plot.addItem(self.play_line)

        self.cross_outline = pg.ScatterPlotItem(
            size=11, symbol="x",
            pen=pg.mkPen(QtGui.QColor(0, 0, 0, 235), width=4),
            brush=None
        )
        self.cross_outline.setZValue(60)
        self.plot.addItem(self.cross_outline)

        self.cross_inner = pg.ScatterPlotItem(
            size=10, symbol="x",
            pen=pg.mkPen(QtGui.QColor(255, 255, 255, 235), width=2),
            brush=None
        )
        self.cross_inner.setZValue(61)
        self.plot.addItem(self.cross_inner)

        self.hscroll.valueChanged.connect(self.on_hscroll)
        self.vscroll.valueChanged.connect(self.on_vscroll)
        self.play_line.sigPositionChanged.connect(self.on_playhead_moved)
        self.plot.scene().sigMouseClicked.connect(self.on_scene_clicked)
        self.plot.scene().sigMouseMoved.connect(self.on_scene_mouse_moved)
        self.vb.sigRangeChanged.connect(self.on_view_range_changed)

    def _build_ui(self):
        # docks
        self.dock_controls, self.spin_win, self.spin_hfmin, self.spin_hfmax, self.combo_quality, self.combo_zoom = build_controls_dock(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.dock_controls)

        self.dock_notes, self.chat = build_notes_dock(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_notes)

        # actions + menus + toolbar
        self.actions = build_actions(self)
        build_menus_and_toolbar(self, self.actions, self.dock_controls, self.dock_notes)

        # connect
        self.actions["open"].triggered.connect(self.on_open_file)
        self.actions["exit"].triggered.connect(self.close)
        self.actions["play"].triggered.connect(self.toggle_play_pause)
        self.actions["pause"].triggered.connect(self.on_pause)
        self.actions["mic"].triggered.connect(self.on_toggle_mic)
        self.actions["loop"].triggered.connect(self.on_toggle_loop)
        self.actions["clear_cross"].triggered.connect(self.clear_crosses)
        self.actions["guitar"].triggered.connect(self.on_guitar_view)

        self.spin_win.valueChanged.connect(self.on_window_changed)
        self.spin_hfmin.valueChanged.connect(self.on_hard_freq_changed)
        self.spin_hfmax.valueChanged.connect(self.on_hard_freq_changed)
        self.combo_quality.currentTextChanged.connect(self.on_quality_changed)

    def _build_timers(self):
        self.ui_timer = QtCore.QTimer()
        self.ui_timer.setInterval(30)
        self.ui_timer.timeout.connect(self.on_ui_tick)
        self.ui_timer.start()

        self.mic_timer = QtCore.QTimer()
        self.mic_timer.setInterval(50)
        self.mic_timer.timeout.connect(self.on_mic_tick)
        self.mic_timer.start()
    
    def _time_from_scene(self, scene_pos: QtCore.QPointF) -> float:
        mp = self.vb.mapSceneToView(scene_pos)
        if not self.audio:
            return 0.0
        return float(max(0.0, min(float(mp.x()), self.audio.duration)))

    def _click_near_playhead(self, scene_pos: QtCore.QPointF, px_tol: int = 10) -> bool:
        x_line_scene = self.vb.mapViewToScene(QtCore.QPointF(float(self.play_line.value()), 0.0)).x()
        return abs(scene_pos.x() - x_line_scene) <= px_tol

    # -------- Wheel handling --------
    def eventFilter(self, obj, event):
        # --- wheel (zoom/scroll) ---
        if event.type() == QtCore.QEvent.Type.Wheel:
            return self._handle_wheel_event(event)

        # --- loop drag: use GraphicsScene mouse events (works on Windows reliably) ---
        if obj is self.plot.scene() and self.audio and self.actions["loop"].isChecked():
            et = event.type()

            if et == QtCore.QEvent.Type.GraphicsSceneMousePress:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    pos = event.scenePos()

                    # click outside existing loop => remove
                    if self.loop_region is not None:
                        a, b = self.loop_region.getRegion()
                        t = self._time_from_scene(pos)
                        if not (min(a, b) <= t <= max(a, b)):
                            self.remove_loop_region()
                            self.statusBar().showMessage("Loop deleted")
                            return True  # event handled

                    # start drag only if press near playhead
                    if self._click_near_playhead(pos, px_tol=12):
                        self._loop_dragging = True
                        self._loop_anchor_t = float(self.play_line.value())
                        return True

            elif et == QtCore.QEvent.Type.GraphicsSceneMouseMove:
                if self._loop_dragging:
                    pos = event.scenePos()
                    t = self._time_from_scene(pos)
                    self._ensure_loop_region(self._loop_anchor_t, t)
                    return True

            elif et == QtCore.QEvent.Type.GraphicsSceneMouseRelease:
                if event.button() == QtCore.Qt.MouseButton.LeftButton and self._loop_dragging:
                    self._loop_dragging = False
                    return True

        return super().eventFilter(obj, event)


    def _handle_wheel_event(self, ev: QtGui.QWheelEvent) -> bool:
        if not self.audio:
            return False

        pd = ev.pixelDelta()
        ad = ev.angleDelta()
        mods = ev.modifiers()

        pos = ev.position()
        scene_pos = self.plot.mapToScene(int(pos.x()), int(pos.y()))
        center = self.vb.mapSceneToView(scene_pos)

        def pick_axis(dx_abs: float, dy_abs: float) -> str:
            mode = self.combo_zoom.currentText()
            if mode.startswith("Horizontal"):
                return "x"
            if mode.startswith("Vertical"):
                return "y"
            if mode.startswith("XY"):
                return "xy"
            if dx_abs > 1.4 * dy_abs:
                return "x"
            if dy_abs > 1.4 * dx_abs:
                return "y"
            return "xy"

        if not pd.isNull():
            dx = float(pd.x())
            dy = float(pd.y())

            if abs(dx) < 0.5 and (mods & QtCore.Qt.KeyboardModifier.ShiftModifier):
                dx = dy
                dy = 0.0

            if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
                axis = pick_axis(abs(dx), abs(dy))
                step = -dy if abs(dy) >= abs(dx) else -dx
                base = 1.006
                factor = base ** float(step)

                if axis == "x":
                    self.vb.zoom_by_xy(factor, 1.0, center=center)
                elif axis == "y":
                    self.vb.zoom_by_xy(1.0, factor, center=center)
                else:
                    self.vb.zoom_by_xy(factor, factor, center=center)

                ev.accept()
                return True

            self.vb.pan_by_pixels(dx, dy)
            ev.accept()
            return True

        if not ad.isNull():
            dx = float(ad.x())
            dy = float(ad.y())

            if abs(dx) < 1e-6 and (mods & QtCore.Qt.KeyboardModifier.ShiftModifier):
                dx = dy
                dy = 0.0

            if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
                axis = pick_axis(abs(dx), abs(dy))
                step = dy if abs(dy) >= abs(dx) else dx
                base = 1.10
                factor = base if step > 0 else (1.0 / base)

                if axis == "x":
                    self.vb.zoom_by_xy(factor, 1.0, center=center)
                elif axis == "y":
                    self.vb.zoom_by_xy(1.0, factor, center=center)
                else:
                    self.vb.zoom_by_xy(factor, factor, center=center)

                ev.accept()
                return True

            self.vb.pan_by_pixels((dx/120.0)*40.0, (dy/120.0)*40.0)
            ev.accept()
            return True

        return False

    # -------- File open / load --------
    def on_open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open audio", "", "Audio (*.wav *.flac *.ogg *.mp3);;All (*.*)"
        )
        if not path:
            return
        self.load_audio(path)

    def load_audio(self, path: str):
        try:
            self.audio = load_audio_file(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load error", str(e))
            return

        self.player.stop()
        self.player.set_audio(self.audio.y, self.audio.sr, self.audio.duration)

        self.statusBar().showMessage("Computing FULL spectrogram…")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self.f, self.t, self.S_db, self.db_vmin, self.db_vmax = compute_spectrogram_full(
                self.audio.y, self.audio.sr, self.nperseg, self.noverlap_ratio
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.update_hard_limits()

        dur = self.audio.duration
        self.spin_win.blockSignals(True)
        self.spin_win.setMaximum(max(0.1, dur))
        self.spin_win.setValue(dur)
        self.spin_win.blockSignals(False)

        self._suspend_render = True
        try:
            self.vb.setRange(xRange=(0.0, dur), yRange=(self.hard_fmin, self.hard_fmax), padding=0.0, update=True)
            self.vb.clamp_view()
        finally:
            self._suspend_render = False

        self.hscroll.setEnabled(True)
        self.vscroll.setEnabled(True)
        self.render_tile_from_viewbox()
        self.statusBar().showMessage(f"Loaded: {os.path.basename(path)} — {dur:.2f}s")

    # -------- Quality / range / window --------
    def on_quality_changed(self, name: str):
        self.quality_name = name
        q = next((q for q in QUALITIES if q.name == name), None)
        if q:
            self.nperseg = q.nperseg
            self.noverlap_ratio = q.noverlap_ratio

        if self.audio:
            self.statusBar().showMessage(f"Recomputing spectrogram ({self.quality_name})…")
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            try:
                self.f, self.t, self.S_db, self.db_vmin, self.db_vmax = compute_spectrogram_full(
                    self.audio.y, self.audio.sr, self.nperseg, self.noverlap_ratio
                )
                self.render_tile_from_viewbox()
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("OK.")

    def on_hard_freq_changed(self):
        fmin = float(self.spin_hfmin.value())
        fmax = float(self.spin_hfmax.value())
        if fmax <= fmin + 1.0:
            fmax = fmin + 1.0
            self.spin_hfmax.blockSignals(True)
            self.spin_hfmax.setValue(fmax)
            self.spin_hfmax.blockSignals(False)

        self.hard_fmin, self.hard_fmax = fmin, fmax

        if self.audio:
            self.update_hard_limits()
            dur = self.audio.duration
            self._suspend_render = True
            try:
                self.vb.setRange(xRange=(0.0, dur), yRange=(self.hard_fmin, self.hard_fmax), padding=0.0, update=True)
                self.vb.clamp_view()
            finally:
                self._suspend_render = False
            self.render_tile_from_viewbox()

    def on_window_changed(self):
        if not self.audio:
            return
        dur = self.audio.duration
        win = float(self.spin_win.value())
        win = max(0.1, min(win, dur))

        (xr, _) = self.vb.viewRange()
        x0 = float(xr[0])
        x0 = max(0.0, min(x0, dur - win))
        x1 = x0 + win

        self._suspend_render = True
        try:
            self.vb.setRange(xRange=(x0, x1), padding=0.0, update=True)
            self.vb.clamp_view()
        finally:
            self._suspend_render = False

        self.render_tile_from_viewbox()

    # -------- Hard limits + scrollbars --------
    def update_hard_limits(self):
        dur = self.audio.duration
        self.vb.set_hard_limits(0.0, dur, self.hard_fmin, self.hard_fmax)
        self.vb.setLimits(xMin=0.0, xMax=dur, yMin=self.hard_fmin, yMax=self.hard_fmax, minYRange=1.0)

    def configure_scrollbars_from_view(self):
        if not self.audio:
            self.hscroll.setEnabled(False)
            self.vscroll.setEnabled(False)
            return

        dur = self.audio.duration
        (xr, yr) = self.vb.viewRange()
        x0, x1 = float(xr[0]), float(xr[1])
        y0, y1 = float(yr[0]), float(yr[1])

        win = max(0.1, x1 - x0)
        ywin = max(1.0, y1 - y0)

        max_t0 = max(0.0, dur - win)
        self.hscroll.setEnabled(True)
        self.hscroll.blockSignals(True)
        self.hscroll.setMinimum(0)
        self.hscroll.setMaximum(int(max_t0 * 1000))
        self.hscroll.setPageStep(int(win * 1000))
        self.hscroll.setValue(int(max(0.0, min(x0, max_t0)) * 1000))
        self.hscroll.blockSignals(False)

        span = max(1.0, self.hard_fmax - self.hard_fmin)
        max_y0 = max(0.0, span - ywin)
        self.vscroll.setEnabled(max_y0 > 1e-6)
        self.vscroll.blockSignals(True)
        self.vscroll.setMinimum(0)
        self.vscroll.setMaximum(int(max_y0 * 10))
        self.vscroll.setPageStep(int(ywin * 10))
        v = int((self.hard_fmax - ywin - y0) * 10)
        v = max(self.vscroll.minimum(), min(v, self.vscroll.maximum()))
        self.vscroll.setValue(v)
        self.vscroll.blockSignals(False)

        self.spin_win.blockSignals(True)
        self.spin_win.setMaximum(max(0.1, dur))
        self.spin_win.setValue(win)
        self.spin_win.blockSignals(False)

    def on_hscroll(self, v: int):
        if not self.audio or self._updating_scroll:
            return
        dur = self.audio.duration
        (xr, _) = self.vb.viewRange()
        win = max(0.1, float(xr[1] - xr[0]))
        max_t0 = max(0.0, dur - win)
        x0 = max(0.0, min(v / 1000.0, max_t0))
        x1 = x0 + win

        self._suspend_render = True
        try:
            self.vb.setRange(xRange=(x0, x1), padding=0.0, update=True)
            self.vb.clamp_view()
        finally:
            self._suspend_render = False
        self.render_tile_from_viewbox()

    def on_vscroll(self, v: int):
        if not self.audio or self._updating_scroll:
            return
        (_, yr) = self.vb.viewRange()
        ywin = max(1.0, float(yr[1] - yr[0]))

        y0 = (self.hard_fmax - ywin) - (v / 10.0)
        y0 = max(self.hard_fmin, min(y0, self.hard_fmax - ywin))
        y1 = y0 + ywin

        self._suspend_render = True
        try:
            self.vb.setRange(yRange=(y0, y1), padding=0.0, update=True)
            self.vb.clamp_view()
        finally:
            self._suspend_render = False
        self.render_tile_from_viewbox()

    # -------- render tile --------
    def on_view_range_changed(self, vb, ranges):
        if not self.audio:
            return
        if self._suspend_render:
            self._updating_scroll = True
            try:
                self.configure_scrollbars_from_view()
            finally:
                self._updating_scroll = False
            self.plot.repaint()
            return
        self.render_tile_from_viewbox()

    def render_tile_from_viewbox(self):
        if self._in_render:
            return
        if self.S_db is None or self.t is None or self.f is None or not self.audio:
            return

        self._in_render = True
        try:
            dur = self.audio.duration
            (xr, yr) = self.vb.viewRange()
            x0, x1 = float(xr[0]), float(xr[1])
            y0, y1 = float(yr[0]), float(yr[1])

            x0 = max(0.0, min(x0, dur))
            x1 = max(0.0, min(x1, dur))
            if x1 <= x0 + 1e-6:
                x1 = min(dur, x0 + 0.1)

            y0 = max(self.hard_fmin, min(y0, self.hard_fmax))
            y1 = max(self.hard_fmin, min(y1, self.hard_fmax))
            if y1 <= y0 + 1e-6:
                y1 = min(self.hard_fmax, y0 + 1.0)

            ti0 = int(np.searchsorted(self.t, x0, side="left"))
            ti1 = int(np.searchsorted(self.t, x1, side="right"))
            ti0 = max(0, min(ti0, len(self.t) - 2))
            ti1 = max(ti0 + 2, min(ti1, len(self.t)))

            fi0 = int(np.searchsorted(self.f, y0, side="left"))
            fi1 = int(np.searchsorted(self.f, y1, side="right"))
            fi0 = max(0, min(fi0, len(self.f) - 2))
            fi1 = max(fi0 + 2, min(fi1, len(self.f)))

            region_db = self.S_db[fi0:fi1, ti0:ti1]
            img_u8 = render_region_to_u8(region_db, self.db_vmin, self.db_vmax, gamma=self.gamma)
            img_u8 = np.flipud(img_u8)
            self.img.setImage(img_u8, autoLevels=False)

            t_slice = self.t[ti0:ti1]
            f_slice = self.f[fi0:fi1]
            dt = float((t_slice[-1] - t_slice[0]) / max(1, len(t_slice) - 1))
            df = float((f_slice[-1] - f_slice[0]) / max(1, len(f_slice) - 1))

            tr = QtGui.QTransform()
            tr.translate(x0, y1)
            tr.scale(dt, -df)
            self.img.setTransform(tr)

            self._updating_scroll = True
            try:
                self.configure_scrollbars_from_view()
            finally:
                self._updating_scroll = False

        finally:
            self._in_render = False

    # -------- clicks / crosses --------
    def on_scene_clicked(self, event):
        if not self.audio:
            return
        pos = event.scenePos()
        if not self.plot.sceneBoundingRect().contains(pos):
            return
        mp = self.vb.mapSceneToView(pos)
        t_clicked = float(mp.x())
        f_clicked = float(mp.y())

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.actions["loop"].isChecked():
                if self.loop_region is not None:
                    a, b = self.loop_region.getRegion()
                    t = self._time_from_scene(pos)
                    if not (min(a, b) <= t <= max(a, b)):
                        self.remove_loop_region()
                        self.statusBar().showMessage("Loop deleted")
                        return

                if self._click_near_playhead(pos):
                    self._loop_dragging = True
                    self._loop_anchor_t = float(self.play_line.value())
                    return

            self.set_playhead(t_clicked)
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.add_cross(t_clicked, f_clicked)

    def on_scene_mouse_moved(self, pos):
        if not (self.audio and self.actions["loop"].isChecked() and self._loop_dragging):
            return
        t = self._time_from_scene(pos)
        self._ensure_loop_region(self._loop_anchor_t, t)
    
    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        super().mouseReleaseEvent(e)
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._loop_dragging = False

    def add_cross(self, t: float, f: float):
        dur = self.audio.duration
        t = max(0.0, min(t, dur))
        f = max(self.hard_fmin, min(f, self.hard_fmax))
        self.cross_points.append((t, f))
        self._refresh_cross_items()
        self._log_crosses()
        self._update_guitar_view()

    def clear_crosses(self):
        self.cross_points = []
        self._refresh_cross_items()
        self.chat.appendPlainText("Crosses erased.\n")
        self._update_guitar_view()

    def _refresh_cross_items(self):
        if not self.cross_points:
            self.cross_outline.setData([], [])
            self.cross_inner.setData([], [])
            return
        xs = [p[0] for p in self.cross_points]
        ys = [p[1] for p in self.cross_points]
        self.cross_outline.setData(xs, ys)
        self.cross_inner.setData(xs, ys)

    def _log_crosses(self):
        lines = []
        for i, (t, f) in enumerate(self.cross_points, start=1):
            note, target, _ = freq_to_nearest_note(f)
            lines.append(f"{i}) t={t:.3f}s | f={f:.2f} Hz -> {note} (≈{target:.2f} Hz)")
        self.chat.appendPlainText("\n".join(lines) + "\n")

    def _selected_midis_from_crosses(self):
        out = []
        for _, f in self.cross_points:
            _, _, mi = freq_to_nearest_note(f)
            out.append(mi)
        return list(dict.fromkeys(out))

    # -------- guitar view --------
    def on_guitar_view(self):
        if self.guitar_window is None:
            self.guitar_window = GuitarViewWindow()
            self.guitar_window.resize(1200, 420)
        self.guitar_window.show()
        self.guitar_window.raise_()
        self.guitar_window.activateWindow()
        self._update_guitar_view()

    def _update_guitar_view(self):
        if self.guitar_window is None:
            return
        self.guitar_window.set_selected_midis(self._selected_midis_from_crosses())

    # -------- loop --------
    def _ensure_loop_region(self, a: float, b: float):
        a, b = float(min(a, b)), float(max(a, b))
        if b - a < 0.03:
            return

        if self.loop_region is None:
            self.loop_region = pg.LinearRegionItem(values=(a, b), orientation=pg.LinearRegionItem.Vertical, movable=True)
            self.loop_region.setZValue(55)
            self.plot.addItem(self.loop_region)
            self.loop_region.sigRegionChanged.connect(self.on_loop_region_changed)
        else:
            self.loop_region.setRegion((a, b))

        # sync player
        self.player.set_loop(True, a, b)

    def on_loop_region_changed(self):
        if self.loop_region is None:
            return
        a, b = self.loop_region.getRegion()
        a, b = float(min(a, b)), float(max(a, b))
        self.player.set_loop(True, a, b)

    def remove_loop_region(self):
        if self.loop_region is not None:
            try:
                self.plot.removeItem(self.loop_region)
            except Exception:
                pass
        self.loop_region = None
        self.player.set_loop(False, None, None)

    def on_toggle_loop(self, checked: bool):
        if not checked:
            self.remove_loop_region()
            self.statusBar().showMessage("Loop OFF")
        else:
            self.player.set_loop(True, self.player.loop_a, self.player.loop_b)
            self.statusBar().showMessage("Loop ON — press cursor and drag")


    # -------- playback --------
    def toggle_play_pause(self):
        if self.player.is_playing:
            self.on_pause()
        else:
            self.on_play()

    def on_play(self):
        if not self.audio:
            return
        try:
            self.player.play()
            self.statusBar().showMessage("Playing… (Space)")
        except Exception as e:
            self.statusBar().showMessage(f"Playback error: {e}")

    def on_pause(self):
        self.player.pause()
        self.statusBar().showMessage("Paused.")

    # -------- playhead --------
    def set_playhead(self, t: float):
        if not self.audio:
            return
        self.player.playhead = max(0.0, min(float(t), self.audio.duration))
        self.play_line.setValue(self.player.playhead)

    def on_playhead_moved(self):
        if not self.audio:
            return
        self.player.playhead = max(0.0, min(float(self.play_line.value()), self.audio.duration))

    # -------- mic --------
    def on_toggle_mic(self, checked: bool):
        if checked:
            self.start_mic()
        else:
            self.stop_mic()

    def start_mic(self):
        if self.mic_enabled:
            return
        self.mic_enabled = True
        self.actions["mic"].setChecked(True)

        def mic_callback(indata, frames, time_info, status):
            x = indata[:, 0].copy()
            try:
                self._mic_q.put_nowait(x)
            except queue.Full:
                pass

        try:
            self._mic_stream = sd.InputStream(
                channels=1, dtype="float32", samplerate=44100,
                blocksize=4096, callback=mic_callback
            )
            self._mic_stream.start()
            self.statusBar().showMessage("Mic ON")
        except Exception as e:
            self.mic_enabled = False
            self.actions["mic"].setChecked(False)
            self.statusBar().showMessage(f"Mic error: {e}")

    def stop_mic(self):
        self.mic_enabled = False
        self.actions["mic"].setChecked(False)
        self._clear_mic_lines()
        try:
            if self._mic_stream:
                self._mic_stream.stop()
                self._mic_stream.close()
        except Exception:
            pass
        self._mic_stream = None
        self.statusBar().showMessage("Mic OFF")

    def _clear_mic_lines(self):
        for line in self._mic_lines:
            try:
                self.plot.removeItem(line)
            except Exception:
                pass
        self._mic_lines = []

    def _draw_mic_lines(self, freqs, amps):
        self._clear_mic_lines()
        if not freqs or not self.audio:
            return

        a = np.array(amps, dtype=np.float32)
        amax = float(np.max(a)) if len(a) else 1.0
        if amax <= 1e-12:
            amax = 1.0
        an = (a / amax).clip(0.0, 1.0)

        for f0, strength in zip(freqs, an.tolist()):
            if f0 < self.hard_fmin or f0 > self.hard_fmax:
                continue
            g = int(round(self.mic_base_green + strength * (self.mic_max_green - self.mic_base_green)))
            alpha = int(round(self.mic_alpha_min + strength * (self.mic_alpha_max - self.mic_alpha_min)))
            pen = pg.mkPen(QtGui.QColor(0, g, 0, alpha), width=self.mic_line_width)
            line = pg.InfiniteLine(pos=float(f0), angle=0, movable=False, pen=pen)
            line.setZValue(40)
            self.plot.addItem(line)
            self._mic_lines.append(line)

    def on_mic_tick(self):
        if not self.mic_enabled:
            return
        latest = None
        while True:
            try:
                latest = self._mic_q.get_nowait()
            except queue.Empty:
                break
        if latest is None:
            return

        freqs, amps = extract_mic_peaks(latest, fs=44100, fmin=self.mic_fmin, fmax=self.mic_fmax, max_lines=self.mic_max_lines)
        self._draw_mic_lines(freqs, amps)

    # -------- ui tick --------
    def on_ui_tick(self):
        if not self.audio:
            return
        self.play_line.blockSignals(True)
        self.play_line.setValue(self.player.playhead)
        self.play_line.blockSignals(False)

    def closeEvent(self, event):
        try:
            self.stop_mic()
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        event.accept()
