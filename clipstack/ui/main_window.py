from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n import i18n
from ..settings import Settings
from ..storage import ClipItemType, Storage
from ..utils import copy_to_clipboard_safely, resource_path
from .flow_layout import FlowLayout
from .item_widget import ItemWidget
from .toast import Toast


# İlk kaç öğe anında yüklensin?
PRIME_COUNT = 9
# Kalanları tek tek eklerken timer aralığı (ms). 0 = event loop’a yield ederek en hızlı akış.
TICK_DELAY_MS = 0


def row_val(row, key, default=None):
    try:
        return row[key]
    except Exception:
        try:
            return row.get(key, default)
        except Exception:
            return default


def row_to_dict(row) -> dict:
    try:
        return {k: row[k] for k in row.keys()}
    except Exception:
        try:
            return dict(row)
        except Exception:
            return {}


class HistoryWindow(QWidget):
    open_settings_requested = Signal()

    def __init__(self, storage: Storage, settings: Settings):
        super().__init__()
        self.storage = storage
        self.settings = settings

        self._open_settings_handler: Optional[Callable[[], None]] = None
        self._notifier: Optional[Callable[[str, str], None]] = None

        self.resize(900, 560)

        # Üst bar
        self.search = QLineEdit()
        self.search.setMinimumHeight(32)
        self.search.textChanged.connect(self.apply_filter)

        self.btn_settings = QPushButton()
        self.btn_settings.setMinimumHeight(32)
        self.btn_settings.clicked.connect(self._on_open_settings_clicked)
        try:
            self.btn_settings.setIcon(QIcon(str(resource_path("assets/icons/gear.svg"))))
        except Exception:
            pass

        self.btn_clear = QPushButton()
        self.btn_clear.setMinimumHeight(32)
        self.btn_clear.clicked.connect(self.clear_history)
        try:
            self.btn_clear.setIcon(QIcon(str(resource_path("assets/icons/clear.svg"))))
        except Exception:
            pass

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addStretch(1)
        top.addWidget(self.btn_settings)
        top.addWidget(self.btn_clear)

        # Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setMinimumHeight(200)

        # Tümü
        self.tab_all = QWidget()
        self.container_all = QWidget(self.tab_all)
        self.flow_all = FlowLayout(self.container_all, margin=8, hspacing=12, vspacing=12)
        self.container_all.setLayout(self.flow_all)

        self.scroll_all = QScrollArea(self.tab_all)
        self.scroll_all.setWidgetResizable(True)
        self.scroll_all.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_all.setWidget(self.container_all)

        lay_all = QVBoxLayout(self.tab_all)
        lay_all.setContentsMargins(0, 0, 0, 0)
        lay_all.addWidget(self.scroll_all)
        self.tabs.addTab(self.tab_all, "")

        # Favoriler
        self.tab_fav = QWidget()
        self.container_fav = QWidget(self.tab_fav)
        self.flow_fav = FlowLayout(self.container_fav, margin=8, hspacing=12, vspacing=12)
        self.container_fav.setLayout(self.flow_fav)

        self.scroll_fav = QScrollArea(self.tab_fav)
        self.scroll_fav.setWidgetResizable(True)
        self.scroll_fav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_fav.setWidget(self.container_fav)

        lay_fav = QVBoxLayout(self.tab_fav)
        lay_fav.setContentsMargins(0, 0, 0, 0)
        lay_fav.addWidget(self.scroll_fav)
        self.tabs.addTab(self.tab_fav, "")

        # Kök
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tabs, 1)

        # Toast
        self._toast = Toast(self)

        # İç durumlar
        self._items_all: List[ItemWidget] = []
        self._items_fav: List[ItemWidget] = []
        self._loaded_once = False

        # Artımlı yükleme kuyrukları ve timer
        self._pending_all: List = []
        self._pending_fav: List = []
        self._tick_timer: Optional[QTimer] = None
        self._toggle_pick_fav = False

        i18n.languageChanged.connect(self.refresh_texts)
        self.refresh_texts()

        # ESC ile gizle
        QShortcut(QKeySequence("Escape"), self, activated=self.hide)

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    def set_open_settings_handler(self, fn: Callable[[], None]):
        self._open_settings_handler = fn

    def set_notifier(self, fn: Callable[[str, str], None]):
        self._notifier = fn

    def refresh_texts(self):
        self.setWindowTitle(self._tr("history.title", "ClipStack - History"))
        self.search.setPlaceholderText(self._tr("history.search_placeholder", "Search..."))
        self.btn_settings.setText(self._tr("history.settings", "Settings"))
        self.btn_clear.setText(self._tr("history.clear_history", "Clear History"))
        self.tabs.setTabText(0, self._tr("history.tab_all", "All"))
        self.tabs.setTabText(1, self._tr("history.tab_favorites", "Favorites"))

    def showCentered(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        cursor_pos = QCursor.pos()
        x = max(0, min(cursor_pos.x() - w // 2, screen.width() - w))
        y = max(0, min(cursor_pos.y() - 100, screen.height() - h))
        self.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
        self.show()

    def showEvent(self, e):
        if self._toast:
            self._toast.dismiss()
        if not self._loaded_once:
            self._loaded_once = True
            self.reload_items()  # İlk gösterimde bekletmeden
        return super().showEvent(e)

    def hideEvent(self, e):
        if self._toast:
            self._toast.dismiss()
        return super().hideEvent(e)

    def _on_open_settings_clicked(self):
        if callable(self._open_settings_handler):
            self._open_settings_handler()
        else:
            self.open_settings_requested.emit()

    def _refresh_layouts(self):
        # Geometrileri hemen uygulatmak için layout’ları etkinleştir
        try:
            self.flow_all.activate()
        except Exception:
            pass
        try:
            self.flow_fav.activate()
        except Exception:
            pass

        self.flow_all.invalidate()
        self.flow_fav.invalidate()
        self.container_all.updateGeometry()
        self.container_fav.updateGeometry()
        self.container_all.adjustSize()
        self.container_fav.adjustSize()
        self.scroll_all.widget().updateGeometry()
        self.scroll_fav.widget().updateGeometry()
        self.scroll_all.viewport().update()
        self.scroll_fav.viewport().update()

    # ------------------ YÜKLEME: İlk 9 hemen, kalanlar tek tek ------------------

    def _stop_tick(self):
        if self._tick_timer:
            try:
                self._tick_timer.stop()
            except Exception:
                pass
        self._tick_timer = None

    def reload_items(self):
        # Devam eden artımlı yükleme varsa durdur
        self._stop_tick()

        # UI’yı temizle
        self._clear_flows()

        # DB’den listeleri al
        rows_all = self.storage.list_items(
            limit=int(self.settings.get("max_items", 1000)),
            favorites_only=False,
        )
        rows_fav = self.storage.list_items(
            limit=int(self.settings.get("max_items", 1000)),
            favorites_only=True,
        )

        # İlk 9'u anında yükle (All ve Favorites)
        self.setUpdatesEnabled(False)
        try:
            prime_all = list(rows_all[:PRIME_COUNT])
            rest_all = list(rows_all[PRIME_COUNT:])
            prime_fav = list(rows_fav[:PRIME_COUNT])
            rest_fav = list(rows_fav[PRIME_COUNT:])

            for row in prime_all:
                self._add_row_widget(kind="all", row=row, immediate_layout=True)

            for row in prime_fav:
                self._add_row_widget(kind="fav", row=row, immediate_layout=True)

            self._pending_all = rest_all
            self._pending_fav = rest_fav
        finally:
            self.setUpdatesEnabled(True)

        # İlk reflow ve filtre
        self.apply_filter(self.search.text())

        # Kalanları tek tek yüklemek üzere timer başlat
        if self._pending_all or self._pending_fav:
            self._tick_timer = QTimer(self)
            self._tick_timer.setTimerType(Qt.PreciseTimer)
            self._tick_timer.setSingleShot(False)
            self._tick_timer.timeout.connect(self._tick_load_one)
            self._tick_timer.start(max(0, int(TICK_DELAY_MS)))

    def _tick_load_one(self):
        if not (self._pending_all or self._pending_fav):
            self._stop_tick()
            self._refresh_layouts()
            return

        # Sıradaki: All ve Fav arasında sırayla yükle (biri boşsa diğerinden devam)
        pick_fav = (self._toggle_pick_fav and self._pending_fav) or (not self._pending_all and self._pending_fav)
        self._toggle_pick_fav = not self._toggle_pick_fav

        try:
            if pick_fav:
                row = self._pending_fav.pop(0)
                self._add_row_widget(kind="fav", row=row, immediate_layout=True)
            else:
                row = self._pending_all.pop(0)
                self._add_row_widget(kind="all", row=row, immediate_layout=True)
        except Exception as ex:
            # Hatalı tek bir kayıt tüm yüklemeyi durdurmasın
            print("Row load error:", ex)

        # Her eklemeden sonra düzeni hemen uygula
        self._refresh_layouts()

        if not (self._pending_all or self._pending_fav):
            self._stop_tick()
            self._refresh_layouts()

    def _add_row_widget(self, kind: str, row, immediate_layout: bool = False):
        # Kartı önce görünmez oluştur (üst üste boyama olmasın)
        if kind == "all":
            w = ItemWidget(row, self.container_all)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_all.addWidget(w)
            self._items_all.append(w)
            flow = self.flow_all
            container = self.container_all
        else:
            w = ItemWidget(row, self.container_fav)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_fav.addWidget(w)
            self._items_fav.append(w)
            flow = self.flow_fav
            container = self.container_fav

        # İstenirse layout’u hemen etkinleştir (geometri şimdi hesaplanır)
        if immediate_layout:
            try:
                flow.activate()
            except Exception:
                pass

        # Filtre uygula ve şimdi görünür yap
        q = (self.search.text() or "").lower().strip()
        is_vis = self._match_row_text(w, q)
        w.setVisible(is_vis)

        # Konteyneri hafif dürt
        container.updateGeometry()

    def _clear_flows(self):
        for w in self._items_all:
            try:
                self.flow_all.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._items_all.clear()

        for w in self._items_fav:
            try:
                self.flow_fav.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._items_fav.clear()

        self.flow_all.invalidate()
        self.flow_fav.invalidate()

    def _match_row_text(self, row_or_widget, query: str) -> bool:
        if not query:
            return True
        if isinstance(row_or_widget, ItemWidget):
            item_type = row_or_widget.item_type
            if item_type in (ClipItemType.TEXT, ClipItemType.HTML):
                content = (row_or_widget.preview_text or "").lower()
                return query in content
            return False
        else:
            t = int(row_val(row_or_widget, "item_type", 0))
            if t in (int(ClipItemType.TEXT), int(ClipItemType.HTML)):
                content = (
                    row_val(row_or_widget, "text_content", "")
                    or row_val(row_or_widget, "html_content", "")
                    or ""
                ).lower()
                return query in content
            return False

    def apply_filter(self, text: str):
        q = (text or "").lower().strip()
        for w in self._items_all:
            w.setVisible(self._match_row_text(w, q))
        for w in self._items_fav:
            w.setVisible(self._match_row_text(w, q))
        self._refresh_layouts()

    # ------------------ Anlık olaylar ------------------

    def on_item_added(self, row):
        if not self.isVisible():
            return

        w = ItemWidget(row, self.container_all)
        w.setVisible(False)
        w.on_copy_requested.connect(self.on_copy_requested)
        w.on_delete_requested.connect(self.on_delete_requested)
        w.on_favorite_toggled.connect(self.on_favorite_toggled)
        try:
            self.flow_all.insertWidget(0, w)
        except Exception:
            self.flow_all.addWidget(w)
        self._items_all.insert(0, w)

        # Geometriyi hemen uygula ve görünürlük ata
        try:
            self.flow_all.activate()
        except Exception:
            pass
        w.setVisible(self._match_row_text(w, (self.search.text() or "").lower().strip()))

        if bool(row_val(row, "favorite", False)):
            self._add_to_favorites_ui(row)

        self._refresh_layouts()

    def on_copy_requested(self, row_id: int, data_kind: ClipItemType, payload):
        success = copy_to_clipboard_safely(self, data_kind, payload)
        if not success:
            QMessageBox.warning(
                self,
                self._tr("dialog.error", "Error"),
                self._tr("dialog.copy_failed", "Failed to copy to clipboard."),
            )
            return
        if self.settings.get("show_toast", True) and self._toast:
            self._toast.show_message(self._tr("toast.copied", "Content copied to clipboard."))
        if self._notifier and self.settings.get("tray_notifications", True):
            self._notifier(self._tr("toast.copied_title", "Copied"), self._tr("toast.copied", "Content copied to clipboard."))
        if self.settings.get("hide_after_copy", False):
            self.hide()

    def on_delete_requested(self, row_id: int):
        if self.settings.get("confirm_delete", True):
            mb = QMessageBox(self)
            mb.setWindowTitle(self._tr("confirm.delete.title", "Delete Confirmation"))
            mb.setText(self._tr("confirm.delete.text", "Are you sure you want to delete this item?"))
            mb.setIcon(QMessageBox.Warning)
            mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            mb.setDefaultButton(QMessageBox.No)
            if mb.exec() != QMessageBox.Yes:
                return

        self._remove_item_from_ui(row_id)

        try:
            self.storage.delete_item(row_id)
        except Exception:
            self.reload_items()

    def on_favorite_toggled(self, row_id: int, fav: bool):
        try:
            self.storage.set_favorite(row_id, fav)
        except Exception:
            pass

        # All sekmesindeki butonu senkronla (Row’u değiştirmeden)
        self._sync_star_in_all(row_id, fav)

        # Favoriler UI
        if fav:
            w_all = self._find_in_list(self._items_all, row_id)
            if w_all:
                self._add_to_favorites_ui(w_all.row)
        else:
            self._remove_from_favorites_ui(row_id)

        if self.settings.get("show_toast", True) and self._toast:
            self._toast.show_message(
                self._tr("item.favorited" if fav else "item.unfavorited",
                         "Added to favorites." if fav else "Removed from favorites.")
            )

        self.apply_filter(self.search.text())

    def clear_history(self):
        mb = QMessageBox(self)
        mb.setWindowTitle(self._tr("confirm.clear.title", "Confirm"))
        mb.setText(self._tr("confirm.clear.text", "Are you sure you want to clear all history?"))
        mb.setIcon(QMessageBox.Warning)
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        if mb.exec() != QMessageBox.Yes:
            return

        self.storage.clear_all()
        self.reload_items()

    # ---- helpers for favorites ----

    def _find_in_list(self, lst: List[ItemWidget], row_id: int) -> Optional[ItemWidget]:
        return next((w for w in lst if getattr(w, "row_id", None) == row_id), None)

    def _sync_star_in_all(self, row_id: int, fav: bool):
        w_all = self._find_in_list(self._items_all, row_id)
        if not w_all:
            return
        if w_all.btn_fav.isChecked() != fav:
            old = w_all.btn_fav.blockSignals(True)
            try:
                w_all.btn_fav.setChecked(fav)
                w_all._apply_fav_icon()
            finally:
                w_all.btn_fav.blockSignals(old)

    def _add_to_favorites_ui(self, row):
        if any(getattr(w, "row_id", None) == row_val(row, "id") for w in self._items_fav):
            return
        row2 = row_to_dict(row)
        row2["favorite"] = True
        wf = ItemWidget(row2, self.container_fav)
        wf.setVisible(False)
        wf.on_copy_requested.connect(self.on_copy_requested)
        wf.on_delete_requested.connect(self.on_delete_requested)
        wf.on_favorite_toggled.connect(self.on_favorite_toggled)
        try:
            self.flow_fav.insertWidget(0, wf)
        except Exception:
            self.flow_fav.addWidget(wf)

        try:
            self.flow_fav.activate()
        except Exception:
            pass

        self._items_fav.insert(0, wf)
        wf.setVisible(self._match_row_text(wf, (self.search.text() or "").lower().strip()))
        self._refresh_layouts()

    def _remove_from_favorites_ui(self, row_id: int):
        idx = next((i for i, w in enumerate(self._items_fav) if getattr(w, "row_id", None) == row_id), -1)
        if idx >= 0:
            w = self._items_fav.pop(idx)
            try:
                self.flow_fav.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
            self._refresh_layouts()

    def _remove_item_from_ui(self, row_id: int):
        idx = next((i for i, w in enumerate(self._items_all) if getattr(w, "row_id", None) == row_id), -1)
        if idx >= 0:
            w = self._items_all.pop(idx)
            try:
                self.flow_all.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._remove_from_favorites_ui(row_id)
        self._refresh_layouts()