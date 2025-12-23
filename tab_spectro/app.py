import sys
from PySide6 import QtWidgets
import pyqtgraph as pg
from tab_spectro.ui.main_window import TabSpectroMainWindow

def main():
    pg.setConfigOptions(imageAxisOrder="row-major")
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    w = TabSpectroMainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
