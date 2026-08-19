"""Snippet kartı — ItemCard düzeni + renkli kod."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton

from .card_common import (
    CARD_W, CARD_H, LIST_H, format_card_date, make_type_badge, make_tool_button, highlight_code,
    apply_card_view_mode,
)


class SnippetCardWidget(QWidget):
    on_copy_requested = Signal(str)
    on_delete_requested = Signal(int)
    on_favorite_toggled = Signal(int)
    on_edit_requested = Signal(int)

    CARD_W = CARD_W
    CARD_H = CARD_H
    LIST_H = LIST_H

    def __init__(self, snippet: dict, storage, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self.snippet_id = snippet["id"]
        self.storage = storage
        self.is_multi_file = bool(snippet.get("is_multi_file", 0))
        self._view_mode = "grid"

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(make_type_badge("assets/icons/type_code.svg", "</>"))

        title = snippet.get("title") or "Snippet"
        self.lbl_title = QLabel(title[:36] + ("…" if len(title) > 36 else ""))
        self.lbl_title.setObjectName("ItemTitle")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent; border: none;")
        top.addWidget(self.lbl_title, 1)

        self.btn_fav = make_tool_button("FavButton", tip="Favori")
        self.btn_fav.setCheckable(True)
        self.btn_fav.setChecked(bool(snippet.get("favorite")))
        self._apply_fav()
        self.btn_fav.toggled.connect(self._fav)
        top.addWidget(self.btn_fav)

        self.btn_more = make_tool_button("MoreButton", "assets/icons/more_vert.svg", "Diğer", "⋮")
        self.btn_more.clicked.connect(lambda: self.on_edit_requested.emit(self.snippet_id))
        top.addWidget(self.btn_more)
        layout.addLayout(top)

        self.preview = QLabel()
        self.preview.setObjectName("ItemPreview")
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setStyleSheet("background: transparent; border: none;")
        if self.is_multi_file:
            self.preview.setTextFormat(Qt.PlainText)
            self.preview.setText("Çok dosyalı snippet")
        else:
            code = snippet.get("code", "") or ""
            self.preview.setText(highlight_code(code, 320))
        layout.addWidget(self.preview, 1)

        bottom = QHBoxLayout()
        lang = (snippet.get("language") or "").upper()
        meta = format_card_date(str(snippet.get("created_at", "") or ""))
        if lang:
            meta = f"{meta} · {lang}" if meta else lang
        code_len = len(snippet.get("code") or "")
        if code_len:
            meta = f"{meta} · {code_len} kr" if meta else f"{code_len} kr"
        self.lbl_meta = QLabel(meta)
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet("font-size: 10px; color: #94a3b8; background: transparent; border: none;")
        bottom.addWidget(self.lbl_meta, 1)

        self.btn_copy = make_tool_button("CopyButton", "assets/icons/copy.svg", "Kopyala")
        self.btn_copy.clicked.connect(self._copy)
        bottom.addWidget(self.btn_copy)
        layout.addLayout(bottom)
        try:
            mode = getattr(getattr(self.window(), "chip_bar", None), "view_mode", "grid")
            self.set_view_mode(mode)
        except Exception:
            pass

    def set_view_mode(self, mode: str):
        apply_card_view_mode(self, mode, getattr(self, "preview", None))
        self.updateGeometry()

    def _apply_fav(self):
        path = "assets/icons/star_on.svg" if self.btn_fav.isChecked() else "assets/icons/star_off.svg"
        try:
            from ..utils import svg_icon
            self.btn_fav.setIcon(svg_icon(path))
        except Exception:
            pass

    def _fav(self, _checked=False):
        self._apply_fav()
        self.on_favorite_toggled.emit(self.snippet_id)

    def _copy(self):
        if self.is_multi_file:
            self.on_copy_requested.emit(self.snippet.get("title") or "")
        else:
            self.on_copy_requested.emit(self.snippet.get("code") or "")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, QToolButton):
                self.on_edit_requested.emit(self.snippet_id)
        super().mousePressEvent(event)
