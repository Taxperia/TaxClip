from typing import Optional
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton,
                               QDialog, QTextEdit, QScrollArea)
from PySide6.QtGui import QPixmap, QIcon, QTextDocument
from PySide6.QtCore import Qt, Signal, QByteArray, QSize
from ..storage import ClipItemType
from ..utils import resource_path

class ItemWidget(QWidget):
    on_copy_requested = Signal(int, int, object)       # (row_id, item_type, payload)
    on_delete_requested = Signal(int)                  # row_id
    on_favorite_toggled = Signal(int, bool)            # (row_id, new_state)

    CARD_W = 260
    CARD_H = 160

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.row_id = row["id"]
        self.item_type = ClipItemType(row["item_type"])
        self.preview_text: Optional[str] = None

        self.setObjectName("ItemCard")
        self.setFixedSize(self.CARD_W, self.CARD_H)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(10, 10, 10, 10)
        self.v.setSpacing(6)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)  # RichText render etmeyi kapat

        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            text = row["text_content"] or ""
            if not text and row["html_content"]:
                doc = QTextDocument()
                doc.setHtml(row["html_content"] or "")
                text = doc.toPlainText()
            self.preview_text = text
            self.preview.setText(self._shorten(text, 300))
        elif self.item_type == ClipItemType.IMAGE:
            blob = row["image_blob"]
            pm = QPixmap()
            pm.loadFromData(QByteArray(blob))
            thumb = pm.scaled(self.CARD_W - 20, self.CARD_H - 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(thumb)
        else:
            self.preview.setText("(Desteklenmeyen)")
        self.v.addWidget(self.preview, 1)

        # Bottom bar: created_at + favorite
        self.bottom = QHBoxLayout()
        self.lbl_meta = QLabel(str(row["created_at"]))
        self.lbl_meta.setObjectName("MetaLabel")
        self.bottom.addWidget(self.lbl_meta, 1)

        self.btn_fav = QToolButton()
        self.btn_fav.setObjectName("FavButton")
        self.btn_fav.setToolTip("Favorilere ekle/çıkar")
        self.btn_fav.setCheckable(True)
        self.btn_fav.setChecked(bool(row["favorite"]))
        self._apply_fav_icon()
        self.btn_fav.toggled.connect(self._fav_toggled)
        self.btn_fav.setAutoRaise(True)
        self.bottom.addWidget(self.btn_fav)

        self.v.addLayout(self.bottom)

        # Hover highlight overlay
        self.hover_overlay = QWidget(self)
        self.hover_overlay.setObjectName("HoverHighlight")
        self.hover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hover_overlay.hide()

        # Hover toolbar
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("HoverToolbar")
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(6, 4, 6, 4)
        self.toolbar_layout.setSpacing(6)

        self.btn_copy = QToolButton()
        self.btn_copy.setIcon(QIcon(str(resource_path("assets/icons/copy.svg"))))
        self.btn_copy.setToolTip("Panoya kopyala")
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.clicked.connect(self._copy)
        self.toolbar_layout.addWidget(self.btn_copy)

        self.btn_expand = QToolButton()
        self.btn_expand.setIcon(QIcon(str(resource_path("assets/icons/expand.svg"))))
        self.btn_expand.setToolTip("Büyüt")
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.clicked.connect(self._expand)
        self.toolbar_layout.addWidget(self.btn_expand)

        self.btn_delete = QToolButton()
        self.btn_delete.setIcon(QIcon(str(resource_path("assets/icons/delete.svg"))))
        self.btn_delete.setToolTip("Sil")
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.clicked.connect(self._delete)
        self.toolbar_layout.addWidget(self.btn_delete)

        self.toolbar.hide()

        self._sync_overlays()

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

    def _apply_fav_icon(self):
        icon_path = "assets/icons/star_on.svg" if self.btn_fav.isChecked() else "assets/icons/star_off.svg"
        self.btn_fav.setIcon(QIcon(str(resource_path(icon_path))))

    def _fav_toggled(self, checked: bool):
        self._apply_fav_icon()
        self.on_favorite_toggled.emit(self.row_id, checked)

    def _copy(self):
        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            payload = self.row["text_content"] or (self.row["html_content"] or "")
        elif self.item_type == ClipItemType.IMAGE:
            payload = self.row["image_blob"]
        else:
            payload = None
        self.on_copy_requested.emit(self.row_id, int(self.item_type), payload)

    def _delete(self):
        self.on_delete_requested.emit(self.row_id)

    def _expand(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("İçerik")
        dlg.resize(700, 500)
        lay = QVBoxLayout(dlg)

        if self.item_type == ClipItemType.IMAGE:
            lbl = QLabel()
            pm = QPixmap()
            pm.loadFromData(QByteArray(self.row["image_blob"]))
            lbl.setPixmap(pm.scaledToWidth(680, Qt.SmoothTransformation))
            scroll = QScrollArea()
            scroll.setWidget(lbl)
            lay.addWidget(scroll)
        else:
            te = QTextEdit()
            te.setReadOnly(True)
            # HTML bile olsa panelde düz metin göster
            text = self.row["text_content"]
            if not text and self.row["html_content"]:
                doc = QTextDocument()
                doc.setHtml(self.row["html_content"])
                text = doc.toPlainText()
            te.setPlainText(text or "")
            lay.addWidget(te)

        dlg.exec()

    def _shorten(self, text: str, max_chars: int) -> str:
        s = (text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if len(s) <= max_chars:
            return s
        return s[:max_chars - 1] + "…"