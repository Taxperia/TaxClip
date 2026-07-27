"""
Kompakt pano paneli — Win+V benzeri küçük, klavye odaklı görünüm.
"""
from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QAbstractItemView,
)

from ..storage import ClipItemType, Storage
from ..utils import copy_to_clipboard_safely


class CompactPanel(QWidget):
    open_full_requested = Signal()
    paste_requested = Signal(int)  # item id — doğrudan yapıştır

    def __init__(self, storage: Storage, settings=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.settings = settings
        self.setWindowTitle("TaxClip — Hızlı Pano")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.resize(360, 420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Son öğeler")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        header.addWidget(title, 1)
        self.btn_full = QPushButton("Gelişmiş görünüm")
        self.btn_full.clicked.connect(self.open_full_requested.emit)
        header.addWidget(self.btn_full)
        lay.addLayout(header)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemActivated.connect(self._on_activate)
        lay.addWidget(self.list, 1)

        hint = QLabel("↑↓ seç · Enter kopyala · Ctrl+Enter yapıştır · Esc kapat · Alt+1-9")
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        QShortcut(QKeySequence("Escape"), self, activated=self.hide)
        QShortcut(QKeySequence("Return"), self, activated=self._copy_current)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._paste_current)
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Alt+{i}"), self, activated=lambda n=i: self._activate_index(n - 1))

        self.reload()

    def reload(self):
        self.list.clear()
        items = self.storage.list_items(limit=10)
        for row in items:
            label = self._label_for(row)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, row)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _label_for(self, row: dict) -> str:
        t = ClipItemType(row.get("item_type", 1))
        title = row.get("custom_title") or ""
        if title:
            return title
        if t == ClipItemType.IMAGE:
            return "🖼 Görsel"
        if t == ClipItemType.FILE:
            text = row.get("text_content") or ""
            return f"📎 Dosya — {text[:40]}"
        text = (row.get("text_content") or row.get("html_content") or "").replace("\n", " ")
        return (text[:60] + "…") if len(text) > 60 else (text or "(boş)")

    def _current_row(self) -> Optional[dict]:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_activate(self, _item):
        self._copy_current()

    def _copy_current(self):
        row = self._current_row()
        if not row:
            return
        self._copy_row(row)

    def _paste_current(self):
        row = self._current_row()
        if not row:
            return
        self._copy_row(row)
        self.paste_requested.emit(int(row["id"]))
        self.hide()

    def _activate_index(self, idx: int):
        if 0 <= idx < self.list.count():
            self.list.setCurrentRow(idx)
            self._paste_current()

    def _copy_row(self, row: dict):
        kind = ClipItemType(row.get("item_type", 1))
        if kind == ClipItemType.IMAGE:
            payload = row.get("image_blob")
        elif kind == ClipItemType.HTML:
            payload = row.get("html_content")
        else:
            payload = row.get("text_content")
        copy_to_clipboard_safely(self, kind, payload)
        try:
            self.storage.record_item_use(int(row["id"]))
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Delete:
            row = self._current_row()
            if row:
                self.storage.delete_item(int(row["id"]))
                self.reload()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        self.reload()
        self.activateWindow()
        self.list.setFocus()
        super().showEvent(event)

    def position_above_taskbar(self, anchor=None):
        """
        Paneli görev çubuğunun üstünde, ekranın kullanılabilir alanında tut.
        Tray'den açılınca genelde sağ-alt köşeye (Win+V tarzı) yerleştirir.
        """
        from PySide6.QtGui import QCursor, QGuiApplication
        from PySide6.QtCore import QPoint

        screen = QGuiApplication.screenAt(anchor or QCursor.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        # availableGeometry görev çubuğunu hariç tutar
        geo = screen.availableGeometry()
        margin = 12
        w = self.width() or 360
        h = self.height() or 420

        # Varsayılan: sağ-alt (tray yakını) — Win+V benzeri
        x = geo.right() - w - margin
        y = geo.bottom() - h - margin

        # İmleç verilmişse ona yaklaştır, yine de ekranın içine sıkıştır
        if anchor is not None:
            x = anchor.x() - w // 2
            y = anchor.y() - h - margin

        x = max(geo.left() + margin, min(x, geo.right() - w - margin))
        y = max(geo.top() + margin, min(y, geo.bottom() - h - margin))

        self.move(QPoint(x, y))
