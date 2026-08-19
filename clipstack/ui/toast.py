from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QTimer, QRect


class Toast(QWidget):
    def __init__(self, parent=None):
        # Child widget — ana pencere içinde alt ortada gösterilir (üst UI ile karışmasın).
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._label = QLabel("", self)
        self._label.setObjectName("ToastLabel")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.resize(300, 44)
        self.hide()

    def show_message(self, text: str, ms: int = 1500):
        if self._timer.isActive():
            self._timer.stop()
        self._label.setText(text)
        self._label.adjustSize()
        needed_h = max(44, self._label.sizeHint().height() + 16)
        self.resize(max(280, min(420, self._label.sizeHint().width() + 40)), needed_h)
        self._label.setGeometry(self.rect().adjusted(12, 8, -12, -8))
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def dismiss(self):
        if self._timer.isActive():
            self._timer.stop()
        self.hide()

    def _reposition(self):
        # Alt ortada — başlık çubuğu / sağ üst kontrollerle çakışmaz
        if not self.parent():
            return
        margin = 20
        pw = self.parent().width()
        ph = self.parent().height()
        x = max(margin, (pw - self.width()) // 2)
        y = max(margin, ph - self.height() - margin - 48)  # pagination üstünde kalsın
        self.setGeometry(QRect(x, y, self.width(), self.height()))
