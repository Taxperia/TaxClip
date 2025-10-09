from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QToolButton,
    QDialog,
    QTextEdit,
    QPushButton,
    QInputDialog,
)

from ..utils import resource_path
from ..i18n import i18n


class NoteWidget(QWidget):
    on_copy_requested = Signal(int, object, object)  # (note_id, item_type_unused, payload=str)
    on_delete_requested = Signal(int)                # (note_id,)
    on_edit_requested = Signal(int, str)            # (note_id, new_content)

    CARD_W = 260
    CARD_H = 160

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.note_id = int(self._row("id", -1))
        self.content: str = str(self._row("content", ""))
        self.created_at: str = str(self._row("created_at", ""))

        # ItemWidget ile aynı kart stili
        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("border: none;")
        self.setFixedSize(self.CARD_W, self.CARD_H)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(10, 10, 10, 10)
        self.v.setSpacing(6)

        # Önizleme metni
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setText(self._shorten(self.content, 300))
        self.v.addWidget(self.preview, 1)

        # Alt bar: tarih
        self.bottom = QHBoxLayout()
        self.bottom.setContentsMargins(0, 0, 0, 0)
        self.bottom.setSpacing(6)
        self.lbl_meta = QLabel(self.created_at)
        self.lbl_meta.setObjectName("MetaLabel")
        self.bottom.addWidget(self.lbl_meta, 1)
        self.v.addLayout(self.bottom)

        # Hover highlight
        self.hover_overlay = QWidget(self)
        self.hover_overlay.setObjectName("HoverHighlight")
        self.hover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hover_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.hover_overlay.setStyleSheet("background-color: rgba(0,0,0,0.10); border-radius: 12px;")
        self.hover_overlay.hide()

        # Hover toolbar: copy, expand, edit, delete
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("HoverToolbar")
        self.toolbar.setAttribute(Qt.WA_StyledBackground, True)
        self.toolbar.setStyleSheet("background-color: rgba(0,0,0,0.22); border-top-left-radius: 12px; border-top-right-radius: 12px; color: white;")
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(6, 4, 6, 4)
        self.toolbar_layout.setSpacing(6)

        self.btn_copy = QToolButton()
        try:
            self.btn_copy.setIcon(QIcon(str(resource_path("assets/icons/copy.svg"))))
        except Exception:
            pass
        self.btn_copy.setToolTip(self._tr("item.tooltip.copy", "Copy to clipboard"))
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.clicked.connect(self._copy)
        self.toolbar_layout.addWidget(self.btn_copy)

        self.btn_expand = QToolButton()
        try:
            self.btn_expand.setIcon(QIcon(str(resource_path("assets/icons/expand.svg"))))
        except Exception:
            pass
        self.btn_expand.setToolTip(self._tr("item.tooltip.expand", "Expand"))
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.clicked.connect(self._expand)
        self.toolbar_layout.addWidget(self.btn_expand)

        self.btn_edit = QToolButton()
        try:
            # Beyaz ikon
            self.btn_edit.setIcon(QIcon(str(resource_path("assets/icons/edit.svg"))))
        except Exception:
            pass
        self.btn_edit.setToolTip(self._tr("notes.edit", "Edit"))
        self.btn_edit.setAutoRaise(True)
        self.btn_edit.clicked.connect(self._edit)
        self.toolbar_layout.addWidget(self.btn_edit)

        self.btn_delete = QToolButton()
        try:
            self.btn_delete.setIcon(QIcon(str(resource_path("assets/icons/delete.svg"))))
        except Exception:
            pass
        self.btn_delete.setToolTip(self._tr("item.tooltip.delete", "Delete"))
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.clicked.connect(self._delete)
        self.toolbar_layout.addWidget(self.btn_delete)

        self.toolbar.hide()
        self._sync_overlays()

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    def _row(self, key: str, default=None):
        try:
            return self.row[key]
        except Exception:
            try:
                return self.row.get(key, default)
            except Exception:
                return default

    def _shorten(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def sizeHint(self) -> QSize:
        return QSize(self.CARD_W, self.CARD_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def resizeEvent(self, e):
        self._sync_overlays()
        return super().resizeEvent(e)

    def _sync_overlays(self):
        self.hover_overlay.setGeometry(0, 0, self.width(), self.height())
        self.toolbar.setGeometry(0, 0, self.width(), 32)
        self.hover_overlay.lower()
        self.toolbar.raise_()

    def enterEvent(self, event):
        self.hover_overlay.show()
        self.toolbar.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.toolbar.hide()
        self.hover_overlay.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._copy()
        super().mousePressEvent(event)

    # Aksiyonlar
    def _copy(self):
        self.on_copy_requested.emit(self.note_id, None, self.content)

    def _delete(self):
        self.on_delete_requested.emit(self.note_id)

    def _expand(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("notes.dialog.title", "Note"))
        v = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(self.content)
        v.addWidget(te, 1)
        btn_close = QPushButton(self._tr("common.close", "Close"))
        btn_close.clicked.connect(dlg.accept)
        v.addWidget(btn_close, alignment=Qt.AlignRight)
        dlg.resize(560, 420)
        dlg.exec()

    def _edit(self):
        # Çok satırlı düzenleme – mevcut içerikle aç
        new_text, ok = QInputDialog.getMultiLineText(
            self,
            self._tr("notes.edit.title", "Edit Note"),
            self._tr("notes.edit.prompt", "Content:"),
            self.content,
        )
        if not ok:
            return
        new_text = (new_text or "").strip()
        if new_text == self.content:
            return
        self.on_edit_requested.emit(self.note_id, new_text)

    # UI içeriğini dışarıdan güncellemek için
    def set_content(self, new_text: str):
        self.content = new_text or ""
        self.preview.setText(self._shorten(self.content, 300))