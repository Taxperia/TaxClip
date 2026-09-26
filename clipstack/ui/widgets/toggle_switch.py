from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    def __init__(
        self,
        parent=None,
        checked=False,
        on_color="#3B82F6",
        off_color="#334155",
        knob_color="#FFFFFF",
    ):
        super().__init__(parent)
        self._checked = checked
        self._progress = 1.0 if checked else 0.0
        self._on_color = QColor(on_color)
        self._off_color = QColor(off_color)
        self._knob_color = QColor(knob_color)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setColors(self, on_color, off_color, knob_color="#FFFFFF"):
        self._on_color = QColor(on_color)
        self._off_color = QColor(off_color)
        self._knob_color = QColor(knob_color)
        self.update()

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
        on_col = QColor(self._on_color)
        off_col = QColor(self._off_color)
        bg = QColor(on_col if self._checked else off_col)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        rect = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob_r = rect.height() - 4
        x = 3 + (rect.width() - knob_r - 6) * self._progress
        knob_rect = QRectF(x, 3, knob_r, knob_r)
        p.setBrush(QBrush(self._knob_color))
        p.setPen(QPen(QColor(0, 0, 0, 40)))
        p.drawEllipse(knob_rect)

    def getProgress(self):
        return self._progress

    def setProgress(self, v: float):
        self._progress = v
        self.update()

    progress = Property(float, getProgress, setProgress)

    def onToggled(self, fn):
        self._cb = fn

    def toggled(self, state: bool):
        if hasattr(self, "_cb") and callable(self._cb):
            self._cb(state)
