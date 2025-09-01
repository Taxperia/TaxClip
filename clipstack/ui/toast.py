from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QTimer, QRect

class Toast(QWidget):
    def __init__(self, parent=None):
        # Child widget olarak; pencere içinde sağ üstte konumlanır.
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._label = QLabel("", self)
        self._label.setObjectName("ToastLabel")
        self._label.setAlignment(Qt.AlignCenter)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.resize(280, 44)
        self.hide()

    def show_message(self, text: str, ms: int = 1500):
        # Önce varsa eski zamanlayıcıyı durdur
        if self._timer.isActive():
            self._timer.stop()
        self._label.setText(text)
        self._label.setGeometry(self.rect().adjusted(10, 8, -10, -8))
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def dismiss(self):
        if self._timer.isActive():
            self._timer.stop()
        self.hide()

    def _reposition(self):
        # Ebeveyn pencere içinde sağ üst köşe
        if not self.parent():
            return
        margin = 16
        pw = self.parent().width()
        x = pw - self.width() - margin
        y = margin
        self.setGeometry(QRect(x, y, self.width(), self.height()))