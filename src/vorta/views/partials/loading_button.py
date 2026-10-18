from PyQt6 import QtCore, QtWidgets


class LoadingButton(QtWidgets.QPushButton):
    """
    A push button with a busy state.

    The busy state is shown elsewhere (the window's activity indicator), so the
    button only tracks it. `setGif` is kept for API compatibility.
    """

    busy_changed = QtCore.pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._busy = False

    @QtCore.pyqtSlot()
    def start(self):
        if not self._busy:
            self._busy = True
            self.busy_changed.emit(True)

    @QtCore.pyqtSlot()
    def stop(self):
        if self._busy:
            self._busy = False
            self.busy_changed.emit(False)

    def is_busy(self) -> bool:
        return self._busy

    def setGif(self, filename):
        pass
