from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget

class ToggleSwitch(QWidget):
    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self._checked = checked
        self._progress = 1.0 if checked else 0.0
        self.setFixedSize(44, 24)
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        if self._checked == v:
            return
        self._checked = v
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(1.0 if v else 0.0)
        self._anim.start()
        self.update()
        self.toggled(self._checked)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Track
        on_col = QColor("#60a5fa")
        off_col = QColor("#475569")
        bg = on_col if self._checked else off_col
        bg.setAlpha(200)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        rect = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(rect, rect.height()/2, rect.height()/2)
        # Knob
        knob_r = rect.height() - 6
        x = 3 + (rect.width() - knob_r - 6) * self._progress
        knob_rect = QRectF(x, 3, knob_r, knob_r)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(QPen(QColor(0, 0, 0, 30)))
        p.drawEllipse(knob_rect)

    def getProgress(self):
        return self._progress

    def setProgress(self, v: float):
        self._progress = v
        self.update()

    progress = Property(float, getProgress, setProgress)

    # basit sinyal pattern'i (Qt Signal yerine callback)
    def onToggled(self, fn):
        self._cb = fn

    def toggled(self, state: bool):
        if hasattr(self, "_cb") and callable(self._cb):
            self._cb(state)