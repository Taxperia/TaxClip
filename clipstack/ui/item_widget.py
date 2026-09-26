from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QByteArray, Signal, QTimer
from PySide6.QtGui import QPixmap, QTextDocument, QColor, QDesktopServices, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton, QMenu,
    QApplication, QMessageBox, QInputDialog, QColorDialog, QFrame,
)
from PySide6.QtCore import QUrl

from ..storage import ClipItemType
from ..sensitive_detector import ensure_sensitive_access, requires_sensitive_access
from ..smart_content import analyze_text, describe_paths, ContentKind, detect_language
from .card_common import highlight_code as _highlight_code, apply_card_view_mode, CARD_W, CARD_H, LIST_H
from ..utils import resource_path, svg_icon
from ..i18n import i18n


# _highlight_code card_common'dan geliyor


class ItemWidget(QWidget):
    on_copy_requested = Signal(int, int, object)       # (row_id, item_type, payload)
    on_delete_requested = Signal(int)                  # row_id
    on_favorite_toggled = Signal(int, bool)            # (row_id, new_state)
    on_pin_toggled = Signal(int, bool)
    on_save_snippet = Signal(int)
    on_meta_changed = Signal(int)

    CARD_W = CARD_W
    CARD_H = CARD_H
    LIST_H = LIST_H

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
        self._char_count = 0
        self._view_mode = "grid"
        self._sensitive_probe_text = self._build_sensitive_probe_text()
        self._requires_sensitive_access = requires_sensitive_access(self.settings, self._sensitive_probe_text)

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        # Global QWidget arka planının iç içe kutu oluşturmasını engelle
        self.setAutoFillBackground(False)

        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(12, 12, 12, 10)
        self.v.setSpacing(8)

        # Üst satır: tip rozeti | stretch | favori | menü
        top = QHBoxLayout()
        top.setSpacing(6)

        self.type_badge = QFrame()
        self.type_badge.setObjectName("ItemTypeBadge")
        self.type_badge.setFixedSize(28, 28)
        self.type_badge.setAttribute(Qt.WA_StyledBackground, True)
        self.type_badge.setAutoFillBackground(False)
        badge_lay = QHBoxLayout(self.type_badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        self.type_icon = QLabel()
        self.type_icon.setAlignment(Qt.AlignCenter)
        self.type_icon.setFixedSize(28, 28)
        self.type_icon.setStyleSheet("background: transparent; border: none;")
        badge_lay.addWidget(self.type_icon)
        top.addWidget(self.type_badge)

        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("ItemTitle")
        self.lbl_title.setStyleSheet(
            "font-weight: 600; font-size: 11px; background: transparent; border: none;"
        )
        top.addWidget(self.lbl_title, 1)

        self.btn_fav = QToolButton()
        self.btn_fav.setObjectName("FavButton")
        self.btn_fav.setToolTip(self._tr("item.tooltip.favorite", "Add/Remove favorites"))
        self.btn_fav.setCheckable(True)
        self.btn_fav.setChecked(bool(self._row("favorite", False)))
        self.btn_fav.setStyleSheet("background: transparent; border: none;")
        self._apply_fav_icon()
        self.btn_fav.toggled.connect(self._fav_toggled)
        self.btn_fav.setAutoRaise(True)
        top.addWidget(self.btn_fav)

        self.btn_more = QToolButton()
        self.btn_more.setObjectName("MoreButton")
        self.btn_more.setToolTip("Diğer")
        self.btn_more.setAutoRaise(True)
        self.btn_more.setStyleSheet("background: transparent; border: none;")
        try:
            self.btn_more.setIcon(svg_icon("assets/icons/more_vert.svg"))
        except Exception:
            self.btn_more.setText("⋮")
        self.btn_more.clicked.connect(lambda: self._show_context_menu(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft())))
        top.addWidget(self.btn_more)

        self.v.addLayout(top)

        # Önizleme
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setObjectName("ItemPreview")
        # Renkli kod için color set etme — QSS span renklerini ezer
        self.preview.setStyleSheet("background: transparent; border: none;")
        self.preview.setAutoFillBackground(False)

        custom_title = self._row("custom_title") or ""
        if self._requires_sensitive_access:
            self.lbl_title.setText("Hassas veri")
            self.preview.setTextFormat(Qt.PlainText)
            self.preview.setText("Görüntülemek için açın")
            self._set_type_icon("lock")
            self._char_count = 0
        elif self.item_type == ClipItemType.FILE:
            self._render_file_card(custom_title)
        elif self.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
            self._render_text_card(custom_title)
        elif self.item_type == ClipItemType.IMAGE:
            self.lbl_title.setText(custom_title or "Görsel")
            self._set_type_icon("image")
            blob = self._row("image_blob")
            pm = QPixmap()
            if blob is not None:
                pm.loadFromData(QByteArray(blob))
                thumb = pm.scaled(self.CARD_W - 24, self.CARD_H - 78, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview.setPixmap(thumb)
            else:
                self.preview.setTextFormat(Qt.PlainText)
                self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
            self._char_count = 0
        else:
            self.lbl_title.setText("?")
            self._set_type_icon("text")
            self.preview.setTextFormat(Qt.PlainText)
            self.preview.setText(self._tr("item.unsupported", "(Unsupported)"))
        self.v.addWidget(self.preview, 1)

        # Alt bar: tarih + karakter | kopyala
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        date_str = self._format_date(str(self._row("created_at", "") or ""))
        meta_bits = [date_str]
        if self._char_count > 0:
            meta_bits.append(f"{self._char_count} kr")
        source = self._row("source_app") or ""
        if source:
            meta_bits.append(source.replace(".exe", "")[:12])
        if self._row("is_sensitive"):
            meta_bits.append("🔒")

        self.lbl_meta = QLabel(" · ".join(p for p in meta_bits if p))
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet(
            "font-size: 10px; color: #94a3b8; background: transparent; border: none;"
        )
        bottom.addWidget(self.lbl_meta, 1)

        self.btn_copy = QToolButton()
        self.btn_copy.setObjectName("CopyButton")
        self.btn_copy.setIcon(svg_icon("assets/icons/copy.svg"))
        self.btn_copy.setToolTip(self._tr("item.tooltip.copy", "Copy to clipboard"))
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.setStyleSheet("background: transparent; border: none;")
        self.btn_copy.clicked.connect(self._copy)
        bottom.addWidget(self.btn_copy)

        self.v.addLayout(bottom)
        self._apply_selection_style()
        # Mevcut pencere görünüm modunu uygula
        try:
            win = self.window()
            mode = getattr(getattr(win, "chip_bar", None), "view_mode", "grid")
            self.set_view_mode(mode)
        except Exception:
            pass

    def set_view_mode(self, mode: str):
        apply_card_view_mode(self, mode, getattr(self, "preview", None))
        self.updateGeometry()

    def showEvent(self, event):
        # Item cards are embedded controls, never native windows. Repair the
        # window type too: setParent(parent) alone preserves Qt.Window.
        parent = self.parentWidget()
        if parent is None:
            self.hide()
            event.ignore()
            return
        if self.isWindow():
            self.hide()
            self.setParent(parent, Qt.WindowType.Widget)
            QTimer.singleShot(0, self.show)
            event.ignore()
            return
        super().showEvent(event)

    def _format_date(self, raw: str) -> str:
        if not raw:
            return ""
        # "2026-07-28 14:30:00" -> "28.07.2026"
        try:
            date_part = raw.split(" ")[0]
            y, m, d = date_part.split("-")
            return f"{d}.{m}.{y}"
        except Exception:
            return raw[:16]

    def _set_type_icon(self, kind: str):
        icon_map = {
            "text": "assets/icons/type_text.svg",
            "code": "assets/icons/type_code.svg",
            "image": "assets/icons/nav_image.svg",
            "file": "assets/icons/nav_file.svg",
            "lock": "assets/icons/lock.svg",
        }
        path = icon_map.get(kind, "assets/icons/type_text.svg")
        try:
            self.type_icon.setPixmap(svg_icon(path).pixmap(QSize(16, 16)))
        except Exception:
            glyphs = {"text": "T", "code": "</>", "image": "🖼", "file": "📎", "lock": "🔒"}
            self.type_icon.setText(glyphs.get(kind, "T"))
            self.type_icon.setAlignment(Qt.AlignCenter)

    def _render_file_card(self, custom_title: str):
        raw = self._row("text_content") or ""
        try:
            data = json.loads(raw)
            self._file_paths = list(data.get("paths") or [])
        except Exception:
            self._file_paths = [raw] if raw else []
        count = len(self._file_paths)
        self.lbl_title.setText(custom_title or (f"{count} dosya" if count != 1 else Path(self._file_paths[0]).name))
        self._set_type_icon("file")
        self.preview_text = "\n".join(self._file_paths)
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setText(describe_paths(self._file_paths))
        self._char_count = len(self.preview_text or "")

    def _render_text_card(self, custom_title: str):
        text = self._row("text_content", "") or ""
        if not text:
            html = self._row("html_content", "") or ""
            if html:
                doc = QTextDocument()
                doc.setHtml(html)
                text = doc.toPlainText()
        self.preview_text = text
        self._char_count = len(text)
        self._smart = analyze_text(text)
        title = custom_title or self._smart.title
        self.lbl_title.setText(title)

        if self._smart.kind == ContentKind.CODE or self._smart.kind == ContentKind.JSON:
            self._set_type_icon("code")
            self.preview.setTextFormat(Qt.RichText)
            code = self._smart.meta.get("pretty") or self._smart.meta.get("code") or text
            self.preview.setText(_highlight_code(code))
            self.preview.setStyleSheet("background: transparent; border: none;")
        elif self._smart.kind == ContentKind.HEX_COLOR:
            self._set_type_icon("text")
            hex_c = self._smart.meta.get("hex", "#000")
            self.preview.setTextFormat(Qt.RichText)
            self.preview.setText(
                f"<div style='background:{hex_c};color:#fff;padding:8px;border-radius:6px;border:none;'>"
                f"<b>{hex_c}</b><br/>{self._smart.summary}</div>"
            )
        else:
            self._set_type_icon("text")
            # Kod benzeri satırlar varsa renklendir
            if self._looks_like_code(text):
                self._set_type_icon("code")
                self.preview.setTextFormat(Qt.RichText)
                self.preview.setText(_highlight_code(text))
                self.preview.setStyleSheet("background: transparent; border: none;")
            else:
                self.preview.setTextFormat(Qt.PlainText)
                self.preview.setStyleSheet("background: transparent; border: none;")
                self.preview.setText(self._shorten(self._smart.summary or text, 280))

    def _looks_like_code(self, text: str) -> bool:
        if not text:
            return False
        hints = ("{", "}", "=>", "function", "def ", "import ", "class ", "const ", "let ", "#!/")
        score = sum(1 for h in hints if h in text)
        return score >= 2 or text.count("\n") >= 3 and ("{" in text or ";" in text)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_selection_style()

    def _apply_selection_style(self):
        if self._selected:
            self.setStyleSheet(
                "#ItemCard { border: none; border-radius: 14px; "
                "background: #1e3a5f; }"
                "#ItemCard QLabel, #ItemCard QToolButton, #ItemCard QFrame {"
                " background: transparent; border: none; }"
            )
        else:
            self.setStyleSheet("")

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
        if getattr(self, "_view_mode", "grid") == "list":
            parent = self.parentWidget()
            w = parent.width() - 24 if parent and parent.width() > 100 else 640
            return QSize(max(320, w), self.LIST_H)
        return QSize(self.CARD_W, self.CARD_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Kart tıklanınca tam ekran / önizleme
            child = self.childAt(event.pos())
            # Butonlara basıldıysa kopyalama/menü kendi handler'ını kullanır
            if isinstance(child, QToolButton) or (child and child.parent() and isinstance(child.parent(), QToolButton)):
                super().mousePressEvent(event)
                return
            self._expand()
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
        if self._requires_sensitive_access and not self._ensure_sensitive_access():
            return
        from .item_preview_dialog import ItemPreviewDialog
        owner = self.window()
        dlg = ItemPreviewDialog(
            self.row,
            owner if owner is not self else None,
            settings=self.settings,
        )
        dlg.exec_animated()

    def _shorten(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _share(self):
        if self._requires_sensitive_access and not self._ensure_sensitive_access():
            return
        from .item_preview_dialog import ItemPreviewDialog
        owner = self.window()
        dlg = ItemPreviewDialog(
            self.row,
            owner if owner is not self else None,
            settings=self.settings,
        )
        dlg.exec_animated()
        content = self._row("text_content") or self._row("html_content") or ""
        if content:
            QApplication.clipboard().setText(str(content))
