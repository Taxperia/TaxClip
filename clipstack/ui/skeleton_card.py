from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame


class SkeletonCard(QWidget):
    """Kart yüklenirken gösterilen iskelet placeholder."""

    CARD_W = 260
    CARD_H = 168

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SkeletonCard")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._view_mode = "grid"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top = QHBoxLayout()
        self.b1 = self._bar(28, 28, radius=6)
        top.addWidget(self.b1)
        top.addStretch(1)
        self.b2 = self._bar(20, 20, radius=10)
        top.addWidget(self.b2)
        self.b3 = self._bar(20, 20, radius=10)
        top.addWidget(self.b3)
        lay.addLayout(top)

        self.line1 = self._bar(0, 12, stretch=True)
        lay.addWidget(self.line1)
        self.line2 = self._bar(0, 12, stretch=True)
        lay.addWidget(self.line2)
        self.line3 = self._bar(0, 12, stretch=True, width_ratio=0.55)
        lay.addWidget(self.line3)
        lay.addStretch(1)

        bottom = QHBoxLayout()
        self.b4 = self._bar(90, 10)
        bottom.addWidget(self.b4)
        bottom.addStretch(1)
        self.b5 = self._bar(22, 22, radius=6)
        bottom.addWidget(self.b5)
        lay.addLayout(bottom)

        # QGraphicsOpacityEffect, Windows/Qt raster backend'inde rounded child
        # widget'ları önceki frame ile birlikte tekrar boyayabiliyor. Bu da tek
        # skeleton kartı birkaç piksel kaymış iki kart gibi gösteriyordu.
        # Skeleton kısa süre göründüğü için statik çizim daha temiz ve ucuz.

    def _bar(self, w: int, h: int, radius: int = 4, stretch: bool = False, width_ratio: float = 1.0) -> QFrame:
        f = QFrame()
        f.setObjectName("SkeletonBar")
        f.setFixedHeight(h)
        if w:
            f.setFixedWidth(w)
        elif stretch:
            f.setMinimumWidth(int(180 * width_ratio))
        f.setStyleSheet(
            f"background: #1e293b; border-radius: {radius}px; border: none;"
        )
        return f
