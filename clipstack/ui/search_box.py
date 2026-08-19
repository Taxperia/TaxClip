"""Üst arama kutusu — solda ikon, sağda Ctrl+K rozeti."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QLabel, QFrame,
)
from ..utils import svg_icon


class SearchBox(QFrame):
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(36)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 8, 4)
        lay.setSpacing(8)

        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        try:
            self.icon.setPixmap(svg_icon("assets/icons/search.svg").pixmap(QSize(16, 16)))
        except Exception:
            self.icon.setText("🔍")
        self.icon.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(self.icon)

        self.edit = QLineEdit()
        self.edit.setObjectName("SearchBoxEdit")
        self.edit.setPlaceholderText("Ara... (Fuzzy search destekli)")
        self.edit.setFrame(False)
        self.edit.setStyleSheet(
            "QLineEdit#SearchBoxEdit {"
            "  background: transparent; border: none; padding: 2px 0;"
            "  color: #e6edf3;"
            "}"
        )
        self.edit.textChanged.connect(self.textChanged.emit)
        lay.addWidget(self.edit, 1)

        self.shortcut = QLabel("Ctrl K")
        self.shortcut.setObjectName("SearchShortcutBadge")
        self.shortcut.setAlignment(Qt.AlignCenter)
        self.shortcut.setFixedHeight(22)
        lay.addWidget(self.shortcut)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str):
        self.edit.setText(text)

    def clear(self):
        self.edit.clear()

    def setFocus(self, reason=Qt.OtherFocusReason):
        self.edit.setFocus(reason)

    def selectAll(self):
        self.edit.selectAll()

    def setPlaceholderText(self, text: str):
        self.edit.setPlaceholderText(text)

    def hasFocus(self) -> bool:
        return self.edit.hasFocus()

    def blockSignals(self, block: bool) -> bool:
        return self.edit.blockSignals(block)
