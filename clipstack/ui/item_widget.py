from typing import Optional
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QTextDocument
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton, QMenu, QAction, QApplication, QFileDialog, QMessageBox
from clipstack.utils import export_single_item_to_json

from ..storage import ClipItemType
from ..utils import resource_path
from ..i18n import i18n


class ItemWidget(QWidget):
    from PySide6.QtCore import Signal
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
        self.setAttribute(Qt.WA_StyledBackground, True)  # QSS çizimini garanti et
        self.setStyleSheet("border: none;")              # Her OS'te border kapalı
        self.setFixedSize(self.CARD_W, self.CARD_H)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(10, 10, 10, 10)
        self.v.setSpacing(6)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)

        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            text = self._row("text_content", "") or ""
            if not text:
                html = self._row("html_content", "") or ""
                if html:
                    doc = QTextDocument()
                    doc.setHtml(html)
                    text = doc.toPlainText()
            self.preview_text = text
            self.preview.setText(self._shorten(text, 300))
        elif self.item_type == ClipItemType.IMAGE:
            blob = self._row("image_blob")
            pm = QPixmap()
            if blob is not None:
                pm.loadFromData(QByteArray(blob))
                thumb = pm.scaled(self.CARD_W - 20, self.CARD_H - 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview.setPixmap(thumb)
            else:
                self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
        else:
            self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
        self.v.addWidget(self.preview, 1)

        # Bottom bar: created_at + favorite
        self.bottom = QHBoxLayout()
        self.lbl_meta = QLabel(str(row["created_at"]))
        self.lbl_meta.setObjectName("MetaLabel")
        self.bottom.addWidget(self.lbl_meta, 1)

        self.btn_fav = QToolButton()
        self.btn_fav.setObjectName("FavButton")
        self.btn_fav.setToolTip(self._tr("item.tooltip.favorite", "Add/Remove favorites"))
        self.btn_fav.setCheckable(True)
        self.btn_fav.setChecked(bool(self._row("favorite", False)))
        self._apply_fav_icon()
        self.btn_fav.toggled.connect(self._fav_toggled)
        self.btn_fav.setAutoRaise(True)
        self.bottom.addWidget(self.btn_fav)

        self.v.addLayout(self.bottom)

        # Hover highlight overlay
        self.hover_overlay = QWidget(self)
        self.hover_overlay.setObjectName("HoverHighlight")
        self.hover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hover_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.hover_overlay.setStyleSheet("background-color: rgba(0,0,0,0.10); border-radius: 12px;")
        self.hover_overlay.hide()

        # Hover toolbar
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("HoverToolbar")
        self.toolbar.setAttribute(Qt.WA_StyledBackground, True)
        self.toolbar.setStyleSheet("background-color: rgba(0,0,0,0.22); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(6, 4, 6, 4)
        self.toolbar_layout.setSpacing(6)

        self.btn_copy = QToolButton()
        self.btn_copy.setIcon(QIcon(str(resource_path("assets/icons/copy.svg"))))
        self.btn_copy.setToolTip(self._tr("item.tooltip.copy", "Copy to clipboard"))
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.clicked.connect(self._copy)
        self.toolbar_layout.addWidget(self.btn_copy)

        self.btn_expand = QToolButton()
        self.btn_expand.setIcon(QIcon(str(resource_path("assets/icons/expand.svg"))))
        self.btn_expand.setToolTip(self._tr("item.tooltip.expand", "Expand"))
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.clicked.connect(self._expand)
        self.toolbar_layout.addWidget(self.btn_expand)

        self.btn_delete = QToolButton()
        self.btn_delete.setIcon(QIcon(str(resource_path("assets/icons/delete.svg"))))
        self.btn_delete.setToolTip(self._tr("item.tooltip.delete", "Delete"))
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.clicked.connect(self._delete)
        self.toolbar_layout.addWidget(self.btn_delete)

        self.btn_share = QToolButton()
        self.btn_share.setIcon(QIcon(str(resource_path("assets/icons/share.svg"))))
        self.btn_share.setToolTip("Paylaş")
        self.btn_share.setAutoRaise(True)
        self.btn_share.clicked.connect(self._share)
        self.toolbar_layout.addWidget(self.btn_share)

        self.toolbar.hide()

        self._sync_overlays()

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    def _row(self, key: str, default=None):
        """sqlite3.Row veya dict'ten güvenli erişim."""
        try:
            return self.row[key]
        except Exception:
            try:
                return self.row.get(key, default)  # dict ise
            except Exception:
                return default

    def sizeHint(self) -> QSize:
        return QSize(self.CARD_W, self.CARD_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def resizeEvent(self, e):
        self._sync_overlays()
        return super().resizeEvent(e)

    def _sync_overlays(self):
        # Tüm alanı kapla (çerçeve efekti istemiyoruz)
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

    def _apply_fav_icon(self):
        icon_path = "assets/icons/star_on.svg" if self.btn_fav.isChecked() else "assets/icons/star_off.svg"
        self.btn_fav.setIcon(QIcon(str(resource_path(icon_path))))

    def _fav_toggled(self, checked: bool):
        self._apply_fav_icon()
        self.on_favorite_toggled.emit(self.row_id, checked)

    def _copy(self):
        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            payload = self._row("text_content") or (self._row("html_content") or "")
        elif self.item_type == ClipItemType.IMAGE:
            payload = self._row("image_blob")
        else:
            payload = None
        self.on_copy_requested.emit(self.row_id, int(self.item_type), payload)

    def _delete(self):
        self.on_delete_requested.emit(self.row_id)

    def _expand(self):
        # Ayrıntı görünümü başka bir dosyada (ItemPreviewDialog) – çağrı burada yapılır
        from .item_preview_dialog import ItemPreviewDialog
        dlg = ItemPreviewDialog(self.row, self)
        dlg.exec()

    def _shorten(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"
    
    def _share(self):
        # Kendi row’unu JSON’a çevir
        json_data = export_single_item_to_json(self.row)
        # Kullanıcıya seçenek sun: Panoya kopyala veya dosyaya kaydet
        app = QApplication.instance()
        clipboard = app.clipboard()
        clipboard.setText(json_data)
        QMessageBox.information(self, "Paylaş", "Not JSON formatında panoya kopyalandı!\n\nBunu başka cihazda 'İçe Aktar' ile ekleyebilirsiniz.")
