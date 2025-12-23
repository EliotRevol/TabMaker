from PySide6 import QtGui

def build_actions(window):
    a = {}

    a["open"] = QtGui.QAction("Open…", window)
    a["open"].setShortcut(QtGui.QKeySequence.Open)

    a["exit"] = QtGui.QAction("Quit", window)
    a["exit"].setShortcut(QtGui.QKeySequence.Quit)

    a["play"] = QtGui.QAction("Play", window)
    a["play"].setShortcut("Space")

    a["pause"] = QtGui.QAction("Pause", window)

    a["mic"] = QtGui.QAction("Toggle Mic", window)
    a["mic"].setCheckable(True)

    a["loop"] = QtGui.QAction("Loop", window)
    a["loop"].setCheckable(True)

    a["clear_cross"] = QtGui.QAction("Clear crosses", window)

    a["guitar"] = QtGui.QAction("Guitar View", window)

    return a

def build_menus_and_toolbar(window, actions, dock_controls, dock_notes):
    m_file = window.menuBar().addMenu("File")
    m_file.addAction(actions["open"])
    m_file.addSeparator()
    m_file.addAction(actions["exit"])

    m_view = window.menuBar().addMenu("View")
    m_view.addAction(actions["guitar"])
    m_view.addSeparator()
    m_view.addAction(dock_controls.toggleViewAction())
    m_view.addAction(dock_notes.toggleViewAction())

    m_play = window.menuBar().addMenu("Playback")
    m_play.addAction(actions["play"])
    m_play.addAction(actions["pause"])
    m_play.addSeparator()
    m_play.addAction(actions["loop"])

    m_tools = window.menuBar().addMenu("Tools")
    m_tools.addAction(actions["mic"])
    m_tools.addAction(actions["clear_cross"])

    tb = window.addToolBar("Main")
    tb.setMovable(False)
    tb.addAction(actions["open"])
    tb.addSeparator()
    tb.addAction(actions["play"])
    tb.addAction(actions["pause"])
    tb.addSeparator()
    tb.addAction(actions["loop"])
    tb.addAction(actions["mic"])
    tb.addSeparator()
    tb.addAction(actions["guitar"])
    tb.addAction(actions["clear_cross"])
