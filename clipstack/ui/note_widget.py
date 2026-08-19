from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton,
    QDialog, QTextEdit, QPushButton, QInputDialog,
)

from .card_common import (
    CARD_W, CARD_H, LIST_H, format_card_date, make_type_badge, make_tool_button, highlight_code,
    apply_card_view_mode,
)
from ..utils import svg_icon
from ..i18n import i18n


class NoteWidget(QWidget):
    on_copy_requested = Signal(int, object, object)
    on_delete_requested = Signal(int)
    on_edit_requested = Signal(int, str)

    CARD_W = CARD_W
    CARD_H = CARD_H
    LIST_H = LIST_H

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.note_id = int(self._row("id", -1))
        self.content: str = str(self._row("content", ""))
        self.created_at: str = str(self._row("created_at", ""))
        self._view_mode = "grid"

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoFillBackground(False)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(12, 12, 12, 10)
        self.v.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(make_type_badge("assets/icons/nav_note.svg", "N"))

        self.lbl_title = QLabel("Not")
        self.lbl_title.setObjectName("ItemTitle")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent; border: none;")
        top.addWidget(self.lbl_title, 1)

        self.btn_more = make_tool_button("MoreButton", "assets/icons/more_vert.svg", "Diğer", "⋮")
        self.btn_more.clicked.connect(self._expand)
        top.addWidget(self.btn_more)
        self.v.addLayout(top)

        self.preview = QLabel()
        self.preview.setObjectName("ItemPreview")
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.RichText if self._looks_like_code(self.content) else Qt.PlainText)
        self.preview.setStyleSheet("background: transparent; border: none;")
        if self._looks_like_code(self.content):
            self.preview.setText(highlight_code(self.content))
        else:
            self.preview.setText(self._shorten(self.content, 280))
        self.v.addWidget(self.preview, 1)

        bottom = QHBoxLayout()
        meta = format_card_date(self.created_at)
        if self.content:
            meta = f"{meta} · {len(self.content)} kr" if meta else f"{len(self.content)} kr"
        self.lbl_meta = QLabel(meta)
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet("font-size: 10px; color: #94a3b8; background: transparent; border: none;")
        bottom.addWidget(self.lbl_meta, 1)

        self.btn_copy = make_tool_button("CopyButton", "assets/icons/copy.svg", "Kopyala")
        self.btn_copy.clicked.connect(self._copy)
        bottom.addWidget(self.btn_copy)
        self.v.addLayout(bottom)
        try:
            mode = getattr(getattr(self.window(), "chip_bar", None), "view_mode", "grid")
            self.set_view_mode(mode)
        except Exception:
            pass

    def set_view_mode(self, mode: str):
        apply_card_view_mode(self, mode, getattr(self, "preview", None))
        self.updateGeometry()

    def _looks_like_code(self, text: str) -> bool:
        if not text:
            return False
        hints = ("{", "}", "=>", "function", "def ", "import ", "class ", "const ", "let ")
        return sum(1 for h in hints if h in text) >= 2

    def _row(self, key, default=None):
        try:
            return self.row[key]
        except Exception:
            try:
                return self.row.get(key, default)
            except Exception:
                return default

    def _shorten(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _copy(self):
        self.on_copy_requested.emit(self.note_id, None, self.content)

    def _expand(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Not")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setPlainText(self.content)
        lay.addWidget(edit, 1)
        row = QHBoxLayout()
        btn_save = QPushButton("Kaydet")
        btn_del = QPushButton("Sil")
        btn_close = QPushButton("Kapat")
        row.addStretch(1)
        row.addWidget(btn_del)
        row.addWidget(btn_save)
        row.addWidget(btn_close)
        lay.addLayout(row)

        def save():
            self.content = edit.toPlainText()
            self.on_edit_requested.emit(self.note_id, self.content)
            if self._looks_like_code(self.content):
                self.preview.setTextFormat(Qt.RichText)
                self.preview.setText(highlight_code(self.content))
            else:
                self.preview.setTextFormat(Qt.PlainText)
                self.preview.setText(self._shorten(self.content, 280))
            dlg.accept()

        btn_save.clicked.connect(save)
        btn_del.clicked.connect(lambda: (self.on_delete_requested.emit(self.note_id), dlg.reject()))
        btn_close.clicked.connect(dlg.reject)
        dlg.exec()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, QToolButton):
                self._expand()
        super().mousePressEvent(event)
