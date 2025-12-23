from PySide6 import QtCore, QtWidgets
from tab_spectro.utils.settings import DEFAULT_HARD_FMIN, DEFAULT_HARD_FMAX, QUALITIES

def build_controls_dock(window):
    dock = QtWidgets.QDockWidget("Controls", window)
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)

    ctrl = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(ctrl)
    form.setContentsMargins(8, 8, 8, 8)
    form.setSpacing(8)

    spin_win = QtWidgets.QDoubleSpinBox()
    spin_win.setRange(0.1, 999999.0)
    spin_win.setSingleStep(0.5)
    spin_win.setValue(8.0)
    form.addRow("Window (s)", spin_win)

    spin_hfmin = QtWidgets.QDoubleSpinBox()
    spin_hfmin.setRange(0.0, 20000.0)
    spin_hfmin.setSingleStep(10.0)
    spin_hfmin.setValue(DEFAULT_HARD_FMIN)
    form.addRow("Fmin (Hz)", spin_hfmin)

    spin_hfmax = QtWidgets.QDoubleSpinBox()
    spin_hfmax.setRange(10.0, 20000.0)
    spin_hfmax.setSingleStep(10.0)
    spin_hfmax.setValue(DEFAULT_HARD_FMAX)
    form.addRow("Fmax (Hz)", spin_hfmax)

    combo_quality = QtWidgets.QComboBox()
    combo_quality.addItems([q.name for q in QUALITIES])
    combo_quality.setCurrentText("Très fin")
    form.addRow("Quality", combo_quality)

    combo_zoom = QtWidgets.QComboBox()
    combo_zoom.addItems(["Auto", "Horizontal (X)", "Vertical (Y)", "XY (les deux)"])
    combo_zoom.setCurrentText("Auto")
    form.addRow("Zoom axis", combo_zoom)

    dock.setWidget(ctrl)

    return dock, spin_win, spin_hfmin, spin_hfmax, combo_quality, combo_zoom

def build_notes_dock(window):
    dock = QtWidgets.QDockWidget("Notes", window)
    dock.setAllowedAreas(
        QtCore.Qt.DockWidgetArea.BottomDockWidgetArea |
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea |
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    )

    chat = QtWidgets.QPlainTextEdit()
    chat.setReadOnly(True)
    chat.setPlaceholderText("Right click to add a cross, the frequencies will appear hear.")
    dock.setWidget(chat)
    return dock, chat
