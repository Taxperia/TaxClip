from __future__ import annotations

from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QFileDialog, QScrollArea
)

from ..utils import resource_path, copy_to_clipboard_safely
from ..storage import ClipItemType
from ..i18n import i18n


def row_val(row, key, default=None):
    try:
        return row[key]
    except Exception:
        try:
            return row.get(key, default)  # dict ise
        except Exception:
            return default


class ItemPreviewDialog(QDialog):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self._tr("preview.title", "Preview"))
        try:
            self.setWindowIcon(QIcon(str(resource_path("assets/icons/expand.svg"))))
        except Exception:
            pass
        self.resize(720, 520)

        self.row = row
        self.item_type = ClipItemType(row["item_type"])

        v = QVBoxLayout(self)

        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            text = row_val(row, "text_content", "") or ""
            if not text:
                html = row_val(row, "html_content", "") or ""
                if html:
                    from PySide6.QtGui import QTextDocument
                    doc = QTextDocument()
                    doc.setHtml(html)
                    text = doc.toPlainText()

            edit = QTextEdit()
            edit.setReadOnly(True)
            edit.setPlainText(text)
            v.addWidget(edit, 1)

        elif self.item_type == ClipItemType.IMAGE:
            blob = row_val(row, "image_blob")
            pm = QPixmap()
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            if blob is not None:
                pm.loadFromData(QByteArray(blob))
                lbl.setPixmap(pm)
            else:
                lbl.setText(self._tr("item.unsupported", "(Unsupported)"))

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(lbl)
            v.addWidget(scroll, 1)
        else:
            lbl = QLabel(self._tr("item.unsupported", "(Unsupported)"))
            lbl.setAlignment(Qt.AlignCenter)
            v.addWidget(lbl, 1)

        # Buttons
        h = QHBoxLayout()
        h.addStretch(1)

        self.btn_copy = QPushButton(self._tr("preview.copy", "Copy"))
        self.btn_copy.clicked.connect(self._copy)
        h.addWidget(self.btn_copy)

        self.btn_save = QPushButton(self._tr("preview.save", "Save As…"))
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setVisible(self.item_type == ClipItemType.IMAGE)
        h.addWidget(self.btn_save)

        self.btn_close = QPushButton(self._tr("preview.close", "Close"))
        self.btn_close.clicked.connect(self.accept)
        h.addWidget(self.btn_close)

        self.btn_share = QPushButton(self._tr("preview.share", "Paylaş"))
        self.btn_share.clicked.connect(self._share)
        h.addWidget(self.btn_share)

        v.addLayout(h)

    def _tr(self, key: str, fallback: str) -> str:
        try:
            s = i18n.t(key)
        except Exception:
            s = ""
        return s if s and s != key else fallback

    def _copy(self):
        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            payload = row_val(self.row, "text_content") or (row_val(self.row, "html_content") or "")
        elif self.item_type == ClipItemType.IMAGE:
            payload = row_val(self.row, "image_blob")
        else:
            payload = None
        copy_to_clipboard_safely(self, self.item_type, payload)

    def _save(self):
        if self.item_type != ClipItemType.IMAGE:
            return
        file, _ = QFileDialog.getSaveFileName(self, self._tr("preview.save", "Save As…"), "", "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)")
        if not file:
            return
        blob = row_val(self.row, "image_blob")
        if blob is None:
            return
        pm = QPixmap()
        pm.loadFromData(QByteArray(blob))
        pm.save(file)