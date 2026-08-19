"""Çizim kartı — ItemCard düzeni."""
from __future__ import annotations

import base64

from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton

from .card_common import CARD_W, CARD_H, LIST_H, format_card_date, make_type_badge, make_tool_button, apply_card_view_mode


class DrawingCardWidget(QWidget):
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    LIST_H = LIST_H

    def __init__(self, drawing: dict, parent=None):
        super().__init__(parent)
        self.drawing = drawing
        self.drawing_id = drawing["id"]
        self._view_mode = "grid"

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(make_type_badge("assets/icons/nav_drawing.svg", "✎"))

        title = drawing.get("title") or "Çizim"
        self.lbl_title = QLabel(str(title)[:36])
        self.lbl_title.setObjectName("ItemTitle")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent; border: none;")
        top.addWidget(self.lbl_title, 1)

        self.btn_more = make_tool_button("MoreButton", "assets/icons/more_vert.svg", "Diğer", "⋮")
        self.btn_more.clicked.connect(lambda: self.edit_requested.emit(self.drawing_id))
        top.addWidget(self.btn_more)
        layout.addLayout(top)

        self.preview = QLabel()
        self.preview.setObjectName("ItemPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.preview, 1)

        bottom = QHBoxLayout()
        self.lbl_meta = QLabel(format_card_date(str(drawing.get("created_at", "") or "")))
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet("font-size: 10px; color: #94a3b8; background: transparent; border: none;")
        bottom.addWidget(self.lbl_meta, 1)

        self.btn_copy = make_tool_button("CopyButton", "assets/icons/expand.svg", "Aç")
        self.btn_copy.clicked.connect(lambda: self.edit_requested.emit(self.drawing_id))
        bottom.addWidget(self.btn_copy)
        layout.addLayout(bottom)

        self._load_thumbnail()
        try:
            mode = getattr(getattr(self.window(), "chip_bar", None), "view_mode", "grid")
            self.set_view_mode(mode)
        except Exception:
            pass

    def set_view_mode(self, mode: str):
        apply_card_view_mode(self, mode, getattr(self, "preview", None))
        if mode == "list" and self.preview.pixmap() and not self.preview.pixmap().isNull():
            thumb = self.preview.pixmap().scaled(48, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(thumb)
        self.updateGeometry()

    def _load_thumbnail(self):
        try:
            img_key = "image_data" if "image_data" in self.drawing else "image"
            img_b64 = self.drawing.get(img_key)
            if not img_b64:
                self.preview.setText("Çizim yok")
                return
            if isinstance(img_b64, str):
                padding = len(img_b64) % 4
                if padding:
                    img_b64 += "=" * (4 - padding)
                img_bytes = base64.b64decode(img_b64)
            else:
                img_bytes = bytes(img_b64)
            pm = QPixmap()
            pm.loadFromData(QByteArray(img_bytes))
            if pm.isNull():
                self.preview.setText("Önizleme yok")
                return
            thumb = pm.scaled(230, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(thumb)
        except Exception:
            self.preview.setText("Önizleme hatası")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, QToolButton):
                self.edit_requested.emit(self.drawing_id)
        super().mousePressEvent(event)
