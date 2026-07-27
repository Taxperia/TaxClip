from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QByteArray, Signal
from PySide6.QtGui import QPixmap, QTextDocument, QColor, QDesktopServices, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton, QMenu,
    QApplication, QMessageBox, QInputDialog, QColorDialog,
)
from PySide6.QtCore import QUrl

from ..storage import ClipItemType
from ..sensitive_detector import ensure_sensitive_access, requires_sensitive_access
from ..smart_content import analyze_text, describe_paths, ContentKind
from ..utils import resource_path, svg_icon
from ..i18n import i18n


class ItemWidget(QWidget):
    on_copy_requested = Signal(int, int, object)       # (row_id, item_type, payload)
    on_delete_requested = Signal(int)                  # row_id
    on_favorite_toggled = Signal(int, bool)            # (row_id, new_state)
    on_pin_toggled = Signal(int, bool)
    on_save_snippet = Signal(int)
    on_meta_changed = Signal(int)

    CARD_W = 260
    CARD_H = 160

    def __init__(self, row, parent=None, settings=None, selected: bool = False):
        super().__init__(parent)
        self.row = row
        self.row_id = row["id"]
        self.item_type = ClipItemType(row["item_type"])
        parent_window = parent.window() if parent is not None else None
        self.settings = settings or getattr(parent_window, "settings", None) or getattr(self.window(), "settings", None)
        self.preview_text: Optional[str] = None
        self._selected = selected
        self._file_paths: list[str] = []
        self._smart = None
        self._sensitive_probe_text = self._build_sensitive_probe_text()
        self._requires_sensitive_access = requires_sensitive_access(self.settings, self._sensitive_probe_text)

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("border: none;")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setFocusPolicy(Qt.StrongFocus)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(10, 10, 10, 10)
        self.v.setSpacing(4)

        # Üst başlık (akıllı tür / özel isim)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("ItemTitle")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px;")
        self.v.addWidget(self.lbl_title)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)

        custom_title = self._row("custom_title") or ""
        if self._requires_sensitive_access:
            self.lbl_title.setText("🔒 Hassas veri")
            self.preview.setText("Görüntülemek için açın")
        elif self.item_type == ClipItemType.FILE:
            self._render_file_card(custom_title)
        elif self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            self._render_text_card(custom_title)
        elif self.item_type == ClipItemType.IMAGE:
            self.lbl_title.setText(custom_title or "🖼 Görsel")
            blob = self._row("image_blob")
            pm = QPixmap()
            if blob is not None:
                pm.loadFromData(QByteArray(blob))
                thumb = pm.scaled(self.CARD_W - 20, self.CARD_H - 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview.setPixmap(thumb)
            else:
                self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
        else:
            self.lbl_title.setText("?")
            self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
        self.v.addWidget(self.preview, 1)

        # Bottom bar: meta
        self.bottom = QHBoxLayout()
        meta_parts = [str(self._row("created_at", ""))]
        source = self._row("source_app") or ""
        if source:
            meta_parts.append(source.replace(".exe", ""))
        use_count = int(self._row("use_count") or 0)
        if use_count:
            meta_parts.append(f"×{use_count}")
        if self._row("collection"):
            meta_parts.append(str(self._row("collection")))
        if self._row("is_sensitive"):
            meta_parts.append("🔒")
        self.lbl_meta = QLabel(" · ".join(p for p in meta_parts if p))
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet("font-size: 10px; color: #888;")
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
        self.btn_copy.setIcon(svg_icon("assets/icons/copy.svg"))
        self.btn_copy.setToolTip(self._tr("item.tooltip.copy", "Copy to clipboard"))
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.clicked.connect(self._copy)
        self.toolbar_layout.addWidget(self.btn_copy)

        self.btn_expand = QToolButton()
        self.btn_expand.setIcon(svg_icon("assets/icons/expand.svg"))
        self.btn_expand.setToolTip(self._tr("item.tooltip.expand", "Expand"))
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.clicked.connect(self._expand)
        self.toolbar_layout.addWidget(self.btn_expand)

        self.btn_delete = QToolButton()
        self.btn_delete.setIcon(svg_icon("assets/icons/delete.svg"))
        self.btn_delete.setToolTip(self._tr("item.tooltip.delete", "Delete"))
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.clicked.connect(self._delete)
        self.toolbar_layout.addWidget(self.btn_delete)

        self.btn_share = QToolButton()
        self.btn_share.setIcon(svg_icon("assets/icons/share.svg"))
        self.btn_share.setToolTip(self._tr("item.tooltip.share", "Paylaş"))
        self.btn_share.setAutoRaise(True)
        self.btn_share.clicked.connect(self._share)
        self.toolbar_layout.addWidget(self.btn_share)

        self.toolbar.hide()
        self._sync_overlays()
        self._apply_selection_style()

    def _render_file_card(self, custom_title: str):
        raw = self._row("text_content") or ""
        try:
            data = json.loads(raw)
            self._file_paths = list(data.get("paths") or [])
        except Exception:
            self._file_paths = [raw] if raw else []
        count = len(self._file_paths)
        self.lbl_title.setText(custom_title or (f"📎 {count} dosya" if count != 1 else f"📎 {Path(self._file_paths[0]).name}"))
        self.preview_text = "\n".join(self._file_paths)
        self.preview.setText(describe_paths(self._file_paths))

    def _render_text_card(self, custom_title: str):
        text = self._row("text_content", "") or ""
        if not text:
            html = self._row("html_content", "") or ""
            if html:
                doc = QTextDocument()
                doc.setHtml(html)
                text = doc.toPlainText()
        self.preview_text = text
        self._smart = analyze_text(text)
        title = custom_title or self._smart.title
        kind_icons = {
            ContentKind.URL: "🔗",
            ContentKind.EMAIL: "✉",
            ContentKind.PHONE: "📞",
            ContentKind.HEX_COLOR: "🎨",
            ContentKind.JSON: "{ }",
            ContentKind.CODE: "</>",
            ContentKind.MARKDOWN: "MD",
            ContentKind.FILE_PATH: "📂",
            ContentKind.LONG_TEXT: "📝",
            ContentKind.BASE64_IMAGE: "🖼",
        }
        icon = kind_icons.get(self._smart.kind, "")
        self.lbl_title.setText(f"{icon} {title}".strip())
        if self._smart.kind == ContentKind.HEX_COLOR:
            hex_c = self._smart.meta.get("hex", "#000")
            self.preview.setText(f"{hex_c}\n{self._smart.summary}")
            self.preview.setStyleSheet(
                f"background-color: {hex_c}; color: #fff; padding: 6px; border-radius: 6px;"
            )
        else:
            self.preview.setText(self._shorten(self._smart.summary or text, 280))

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_selection_style()

    def _apply_selection_style(self):
        if self._selected:
            self.setStyleSheet("border: 2px solid #3b82f6; border-radius: 12px;")
        else:
            self.setStyleSheet("border: none;")

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

    def _build_sensitive_probe_text(self) -> str:
        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            text = self._row("text_content", "") or ""
            if text:
                return text
            html = self._row("html_content", "") or ""
            if html:
                doc = QTextDocument()
                doc.setHtml(html)
                return doc.toPlainText()
            return ""
        if self.item_type == ClipItemType.IMAGE:
            return self._row("ocr_text", "") or ""
        return ""

    def _ensure_sensitive_access(self) -> bool:
        if ensure_sensitive_access(self.settings, self._sensitive_probe_text, self):
            return True
        QMessageBox.warning(
            self,
            "Erişim Engellendi",
            "Bu içerik hassas veri içeriyor. Görüntülemek veya kopyalamak için doğrulama gerekli."
        )
        return False

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
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self._show_context_menu(event.globalPos())

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction("Kopyala", self._copy)
        menu.addAction("Genişlet", self._expand)
        menu.addSeparator()

        pinned = bool(self._row("pinned", False))
        menu.addAction("Sabitlemeyi kaldır" if pinned else "Sabitle", lambda: self.on_pin_toggled.emit(self.row_id, not pinned))
        menu.addAction("Favori değiştir", lambda: self.btn_fav.toggle())

        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            menu.addAction("Snippet olarak kaydet", lambda: self.on_save_snippet.emit(self.row_id))

        menu.addAction("İsim ver…", self._rename)
        menu.addAction("Koleksiyona ekle…", self._set_collection)
        menu.addAction("Etiket ekle…", self._set_tags)
        menu.addSeparator()

        # Akıllı eylemler
        if self.item_type == ClipItemType.FILE and self._file_paths:
            menu.addAction("Dosyayı aç", self._open_file)
            menu.addAction("Klasörde göster", self._reveal_in_explorer)
            menu.addAction("Yolu kopyala", self._copy_paths_text)
        elif self._smart:
            if self._smart.kind == ContentKind.URL:
                menu.addAction("Tarayıcıda aç", lambda: QDesktopServices.openUrl(QUrl(self._smart.meta["url"])))
            elif self._smart.kind == ContentKind.EMAIL:
                menu.addAction("E-posta gönder", lambda: QDesktopServices.openUrl(QUrl(f"mailto:{self._smart.meta['email']}")))
            elif self._smart.kind == ContentKind.JSON:
                menu.addAction("Biçimlendirilmiş kopyala", lambda: QApplication.clipboard().setText(self._smart.meta.get("pretty", "")))
                menu.addAction("Küçültülmüş kopyala", lambda: QApplication.clipboard().setText(self._smart.meta.get("compact", "")))
            elif self._smart.kind == ContentKind.HEX_COLOR:
                menu.addAction("RGB kopyala", lambda: QApplication.clipboard().setText(self._smart.summary))
            elif self._smart.kind == ContentKind.FILE_PATH:
                menu.addAction("Konumu aç", lambda: self._reveal_path(self._smart.meta.get("path", "")))
            elif self._smart.kind == ContentKind.MARKDOWN:
                menu.addAction("Düz metin kopyala", lambda: QApplication.clipboard().setText(self.preview_text or ""))

        menu.addSeparator()
        menu.addAction("Sil", self._delete)
        menu.exec(global_pos)

    def _rename(self):
        current = self._row("custom_title") or ""
        name, ok = QInputDialog.getText(self, "İsim ver", "Kart adı:", text=current)
        if ok:
            storage = getattr(self.window(), "storage", None)
            if storage:
                storage.update_item_meta(self.row_id, custom_title=name.strip())
                self.on_meta_changed.emit(self.row_id)

    def _set_collection(self):
        presets = ["Kodlar", "Adresler", "Cevaplar", "Komutlar", ""]
        current = self._row("collection") or ""
        name, ok = QInputDialog.getItem(self, "Koleksiyon", "Koleksiyon seç/yaz:", presets, 0, True)
        if ok:
            storage = getattr(self.window(), "storage", None)
            if storage:
                storage.update_item_meta(self.row_id, collection=name.strip())
                self.on_meta_changed.emit(self.row_id)

    def _set_tags(self):
        current = self._row("tags") or ""
        tags, ok = QInputDialog.getText(self, "Etiketler", "Virgülle ayırın:", text=current)
        if ok:
            storage = getattr(self.window(), "storage", None)
            if storage:
                storage.update_item_meta(self.row_id, tags=tags.strip())
                self.on_meta_changed.emit(self.row_id)

    def _open_file(self):
        if not self._file_paths:
            return
        path = self._file_paths[0]
        if not Path(path).exists():
            QMessageBox.warning(self, "Dosya", "Dosya artık mevcut değil.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _reveal_in_explorer(self):
        if self._file_paths:
            self._reveal_path(self._file_paths[0])

    def _reveal_path(self, path: str):
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "Dosya", "Dosya artık mevcut değil.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)], shell=False)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent if p.is_file() else p)))

    def _copy_paths_text(self):
        QApplication.clipboard().setText("\n".join(self._file_paths))

    def _apply_fav_icon(self):
        icon_path = "assets/icons/star_on.svg" if self.btn_fav.isChecked() else "assets/icons/star_off.svg"
        self.btn_fav.setIcon(svg_icon(icon_path))

    def _fav_toggled(self, checked: bool):
        self._apply_fav_icon()
        self.on_favorite_toggled.emit(self.row_id, checked)

    def _copy(self):
        if self._requires_sensitive_access and not self._ensure_sensitive_access():
            return
        if self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            payload = self._row("text_content") or (self._row("html_content") or "")
        elif self.item_type == ClipItemType.IMAGE:
            payload = self._row("image_blob")
        elif self.item_type == ClipItemType.FILE:
            payload = self._row("text_content")
        else:
            payload = None
        self.on_copy_requested.emit(self.row_id, int(self.item_type), payload)

    def _delete(self):
        self.on_delete_requested.emit(self.row_id)

    def _expand(self):
        from .item_preview_dialog import ItemPreviewDialog
        dlg = ItemPreviewDialog(self.row, self, settings=self.settings)
        dlg.exec()

    def _shorten(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _share(self):
        if self._requires_sensitive_access and not self._ensure_sensitive_access():
            return
        from .item_preview_dialog import ItemPreviewDialog
        dlg = ItemPreviewDialog(self.row, self, settings=self.settings)
        dlg.exec()
        # Paylaşım dialog içinden yapılabilir; yoksa kopyala
        content = self._row("text_content") or self._row("html_content") or ""
        if content:
            QApplication.clipboard().setText(str(content))
