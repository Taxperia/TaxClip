from typing import Optional, Callable, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton, QHBoxLayout,
    QScrollArea, QApplication, QTabWidget, QLabel
)
from PySide6.QtCore import Qt, QSize, QRect, QPoint, QTimer, QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtGui import QIcon, QShortcut, QKeySequence, QCursor

from ..storage import Storage, ClipItemType
from .flow_layout import FlowLayout
from .item_widget import ItemWidget
from .toast import Toast
from ..utils import resource_path, copy_to_clipboard_safely
from ..settings import Settings


class HistoryWindow(QWidget):
    # Ayarlar açma isteği (App yakalayıp SettingsDialog açabilir)
    open_settings_requested = Signal()

    def __init__(self, storage: Storage, settings: Settings):
        super().__init__()
        self.storage = storage
        self.settings = settings
        self._notifier: Optional[Callable[[str, str], None]] = None
        self._open_settings_handler: Optional[Callable[[], None]] = None

        self.setWindowTitle("ClipStack - Geçmiş")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(settings.get("stay_on_top", False)))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(900, 560)

        # Top bar
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara...")
        self.search.textChanged.connect(self.apply_filter)

        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(QIcon(str(resource_path("assets/icons/gear.svg"))))
        self.btn_settings.setText("Ayarlar")
        self.btn_settings.clicked.connect(self._open_settings_clicked)

        self.btn_clear = QPushButton("Geçmişi Sil")
        self.btn_clear.setIcon(QIcon(str(resource_path("assets/icons/clear.svg"))))
        self.btn_clear.clicked.connect(self.clear_history)

        # Minimum yükseklikleri OLUŞTURDUKTAN SONRA ayarla
        self.search.setMinimumHeight(32)
        self.btn_settings.setMinimumHeight(32)
        self.btn_clear.setMinimumHeight(32)

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addStretch(1)
        top.addWidget(self.btn_settings)
        top.addWidget(self.btn_clear)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setMinimumHeight(200)

        # Tab: Tümü
        self.tab_all = QWidget()
        self.container_all = QWidget(self.tab_all)
        self.flow_all = FlowLayout(self.container_all, margin=8, hspacing=12, vspacing=12)

        self.scroll_all = QScrollArea(self.tab_all)
        self.scroll_all.setWidgetResizable(True)
        self.scroll_all.setWidget(self.container_all)
        self.scroll_all.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        lay_all = QVBoxLayout(self.tab_all)
        lay_all.setContentsMargins(0, 0, 0, 0)
        lay_all.addWidget(self.scroll_all)
        self.tabs.addTab(self.tab_all, "Tümü")

        # Tab: Favoriler
        self.tab_fav = QWidget()
        self.container_fav = QWidget(self.tab_fav)
        self.flow_fav = FlowLayout(self.container_fav, margin=8, hspacing=12, vspacing=12)

        self.scroll_fav = QScrollArea(self.tab_fav)
        self.scroll_fav.setWidgetResizable(True)
        self.scroll_fav.setWidget(self.container_fav)
        self.scroll_fav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        lay_fav = QVBoxLayout(self.tab_fav)
        lay_fav.setContentsMargins(0, 0, 0, 0)
        lay_fav.addWidget(self.scroll_fav)
        self.tabs.addTab(self.tab_fav, "Favoriler")

        # Root
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tabs, 1)

        # In-app toast
        self._toast = Toast(self)

        # Yükleme overlay'i
        self._loading = QLabel("Yükleniyor…", self)
        self._loading.setObjectName("LoadingOverlay")
        self._loading.setAlignment(Qt.AlignCenter)
        # Temel stil (global style.qss olmasa bile okunaklı)
        self._loading.setStyleSheet("background: rgba(15,23,42,0.88); color: #e2e8f0; font-weight: 600;")
        self._loading.hide()

        # İç durumlar
        self._bulk_loading = False
        self._anims: List[QPropertyAnimation] = []
        self._scroll_anim: Optional[QPropertyAnimation] = None

        # Kısayol
        QShortcut(QKeySequence("Escape"), self, activated=self.hide)

    def set_open_settings_handler(self, fn: Callable[[], None]):
        self._open_settings_handler = fn

    def _open_settings_clicked(self):
        if callable(self._open_settings_handler):
            self._open_settings_handler()
            return
        # Yedek: doğrudan modal aç
        from .settings_dialog import SettingsDialog
        from ..theme_manager import theme_manager
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            theme_manager.apply(self.settings.get("theme", "default"))
            self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings.get("stay_on_top", False)))
            self.show()
            self.apply_filter(self.search.text())

    def set_notifier(self, fn: Callable[[str, str], None]):
        self._notifier = fn

    def showEvent(self, e):
        if self._toast:
            self._toast.dismiss()
        return super().showEvent(e)

    def hideEvent(self, e):
        if self._toast:
            self._toast.dismiss()
        return super().hideEvent(e)

    def showCentered(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 900, 560
        cursor_pos = QCursor.pos()
        x = max(0, min(cursor_pos.x() - w // 2, screen.width() - w))
        y = max(0, min(cursor_pos.y() - 100, screen.height() - h))
        self.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
        self.show()
        self._toast.dismiss()
        self._position_loading_overlay()

    def resizeEvent(self, e):
        if self._toast and self._toast.isVisible():
            self._toast._reposition()
        self._position_loading_overlay()
        return super().resizeEvent(e)

    def _position_loading_overlay(self):
        if self._loading:
            self._loading.setGeometry(self.rect())

    def _clear_flows(self):
        for w in self._items_all if hasattr(self, "_items_all") else []:
            w.setParent(None)
            w.deleteLater()
        self._items_all = []
        for w in self._items_fav if hasattr(self, "_items_fav") else []:
            w.setParent(None)
            w.deleteLater()
        self._items_fav = []
        self.flow_all.invalidate()
        self.flow_fav.invalidate()

    def _refresh_layouts(self):
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

    def reload_items(self):
        self._bulk_loading = True
        self._loading.show()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        self.setUpdatesEnabled(False)
        try:
            self._clear_flows()
            rows_all = self.storage.list_items(limit=int(self.settings.get("max_items", 1000)), favorites_only=False)
            self._items_all = []
            for row in rows_all:
                w = ItemWidget(row, self.container_all)
                w.on_copy_requested.connect(self.on_copy_requested)
                w.on_delete_requested.connect(self.on_delete_requested)
                w.on_favorite_toggled.connect(self.on_favorite_toggled)
                self.flow_all.addWidget(w)
                self._items_all.append(w)

            rows_fav = self.storage.list_items(limit=int(self.settings.get("max_items", 1000)), favorites_only=True)
            self._items_fav = []
            for row in rows_fav:
                w = ItemWidget(row, self.container_fav)
                w.on_copy_requested.connect(self.on_copy_requested)
                w.on_delete_requested.connect(self.on_delete_requested)
                w.on_favorite_toggled.connect(self.on_favorite_toggled)
                self.flow_fav.addWidget(w)
                self._items_fav.append(w)

            self.apply_filter(self.search.text())
        finally:
            self.setUpdatesEnabled(True)
            self._bulk_loading = False
            QTimer.singleShot(0, self._refresh_layouts)
            self._loading.hide()
            QApplication.restoreOverrideCursor()

    def apply_filter(self, text: str):
        q = (text or "").lower().strip()

        def match_item(item: ItemWidget) -> bool:
            if not q:
                return True
            if item.item_type in (ClipItemType.TEXT, ClipItemType.HTML):
                content = (item.preview_text or "").lower()
                return q in content
            return False

        for w in getattr(self, "_items_all", []):
            w.setVisible(match_item(w))
        for w in getattr(self, "_items_fav", []):
            w.setVisible(match_item(w))

    def on_item_added(self, row):
        if not self.isVisible():
            return

        q = (self.search.text() or "").lower().strip()

        def match_row(r) -> bool:
            if not q:
                return True
            t = int(r["item_type"])
            if t in (int(ClipItemType.TEXT), int(ClipItemType.HTML)):
                content = (r["text_content"] or r["html_content"] or "").lower()
                return q in content
            return False

        w = ItemWidget(row, self.container_all)
        w.on_copy_requested.connect(self.on_copy_requested)
        w.on_delete_requested.connect(self.on_delete_requested)
        w.on_favorite_toggled.connect(self.on_favorite_toggled)
        self.flow_all.insertWidget(0, w)
        if not hasattr(self, "_items_all"):
            self._items_all = []
        self._items_all.insert(0, w)
        w.setVisible(match_row(row))

        if bool(row["favorite"]):
            wf = ItemWidget(row, self.container_fav)
            wf.on_copy_requested.connect(self.on_copy_requested)
            wf.on_delete_requested.connect(self.on_delete_requested)
            wf.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_fav.insertWidget(0, wf)
            if not hasattr(self, "_items_fav"):
                self._items_fav = []
            self._items_fav.insert(0, wf)
            wf.setVisible(match_row(row))

        self._refresh_layouts()

        sb = self.scroll_all.verticalScrollBar()
        start = sb.value()
        if start != 0:
            anim = QPropertyAnimation(sb, b"value", self)
            anim.setDuration(220 if self.settings.get("animations", True) else 0)
            anim.setStartValue(start)
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._scroll_anim = anim

        if self.settings.get("animations", True):
            QTimer.singleShot(0, lambda: self._animate_widget_fade_in(w))

    def _animate_widget_fade_in(self, widget):
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
        eff.setOpacity(0.0)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start()
        self._anims.append(anim)

        def _cleanup():
            try:
                self._anims.remove(anim)
            except Exception:
                pass
        anim.finished.connect(_cleanup)

    def on_copy_requested(self, row_id: int, data_kind: ClipItemType, payload):
        success = copy_to_clipboard_safely(self, data_kind, payload)
        if not success:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Hata", "Pano kopyalama başarısız oldu.")
            return
        if self.settings.get("show_toast", True):
            self._toast.show_message("İçerik panoya kopyalandı.")
        if self._notifier and self.settings.get("tray_notifications", True):
            self._notifier("Kopyalandı", "İçerik panoya kopyalandı.")
        if self.settings.get("hide_after_copy", False):
            self.hide()

    def on_delete_requested(self, row_id: int):
        from PySide6.QtWidgets import QMessageBox
        if self.settings.get("confirm_delete", True):
            mb = QMessageBox(self)
            mb.setWindowTitle("Silme Onayı")
            mb.setText("Bu öğeyi silmek istediğinize emin misiniz?")
            mb.setIcon(QMessageBox.Warning)
            mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            mb.setDefaultButton(QMessageBox.No)
            res = mb.exec()
            if res != QMessageBox.Yes:
                return
        self.storage.delete_item(row_id)
        self.reload_items()

    def on_favorite_toggled(self, row_id: int, fav: bool):
        self.storage.set_favorite(row_id, fav)
        if self.settings.get("show_toast", True):
            self._toast.show_message("Favorilere eklendi." if fav else "Favorilerden çıkarıldı.")
        self.reload_items()

    def clear_history(self):
        from PySide6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Onay", "Tüm geçmişi silmek istediğinizden emin misiniz?")
        if confirm == QMessageBox.Yes:
            self.storage.clear_all()
            self.reload_items()