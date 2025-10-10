from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal, QDateTime
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
    QLabel,
    QProgressBar,
    QInputDialog,
    QFileDialog,
    QMessageBox
)

from ..i18n import i18n
from ..settings import Settings
from ..storage import ClipItemType, Storage
from ..utils import copy_to_clipboard_safely, resource_path
from .flow_layout import FlowLayout
from .item_widget import ItemWidget
from .note_widget import NoteWidget
from .toast import Toast
from .reminder_widget import ReminderWidget
from .reminder_dialog import ReminderDialog


PRIME_COUNT = 9
PAGE_SIZE = 30
LOADER_DELAY_MS = 300


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


class LoaderWidget(QWidget):
    def __init__(self, text: str = "Yükleniyor…", parent: Optional[QWidget] = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)  # busy
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.lbl = QLabel(text)
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.lbl)


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

        # Not Ekle (yalnız Notlar sekmesinde görünür)
        self.btn_add_note = QPushButton()
        self.btn_add_note.setMinimumHeight(32)
        self.btn_add_note.clicked.connect(self._add_note_dialog)
        self.btn_add_note.setVisible(False)
        try:
            p = resource_path("assets/icons/note_add.svg")
            if p and p.exists():
                self.btn_add_note.setIcon(QIcon(str(p)))
        except Exception:
            pass
        
        self.btn_clear_reminders = QPushButton()
        self.btn_clear_reminders.setMinimumHeight(32)
        self.btn_clear_reminders.clicked.connect(self._clear_all_reminders)
        self.btn_clear_reminders.setVisible(False)
        try:
            p = resource_path("assets/icons/delete.svg")
            if p and p.exists():
                self.btn_clear_reminders.setIcon(QIcon(str(p)))
        except Exception:
            pass
        
        self.btn_add_reminder = QPushButton()
        self.btn_add_reminder.setMinimumHeight(32)
        self.btn_add_reminder.clicked.connect(self._add_reminder_dialog)
        self.btn_add_reminder.setVisible(False)
        try:
            p = resource_path("assets/icons/alarm_add.svg")
            if p and p.exists():
                self.btn_add_reminder.setIcon(QIcon(str(p)))
        except Exception:
            pass

        # Tüm notları temizle (yalnız Notlar sekmesinde görünür)
        self.btn_clear_notes = QPushButton()
        self.btn_clear_notes.setMinimumHeight(32)
        self.btn_clear_notes.clicked.connect(self._clear_all_notes)
        self.btn_clear_notes.setVisible(False)
        try:
            p = resource_path("assets/icons/delete.svg")
            if p and p.exists():
                self.btn_clear_notes.setIcon(QIcon(str(p)))
        except Exception:
            pass

        # Ayarlar
        self.btn_settings = QPushButton()
        self.btn_settings.setMinimumHeight(32)
        self.btn_settings.clicked.connect(self._on_open_settings_clicked)
        try:
            self.btn_settings.setIcon(QIcon(str(resource_path("assets/icons/gear.svg"))))
        except Exception:
            pass

        # Geçmişi temizle (tüm öğeler)
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
        top.addWidget(self.btn_add_note)
        top.addWidget(self.btn_add_reminder)
        top.addWidget(self.btn_clear_reminders)
        top.addWidget(self.btn_clear_notes)
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

        # Notlar
        self.tab_notes = QWidget()
        self.container_notes = QWidget(self.tab_notes)
        self.flow_notes = FlowLayout(self.container_notes, margin=8, hspacing=12, vspacing=12)
        self.container_notes.setLayout(self.flow_notes)

        self.scroll_notes = QScrollArea(self.tab_notes)
        self.scroll_notes.setWidgetResizable(True)
        self.scroll_notes.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_notes.setWidget(self.container_notes)

        lay_notes = QVBoxLayout(self.tab_notes)
        lay_notes.setContentsMargins(0, 0, 0, 0)
        lay_notes.addWidget(self.scroll_notes, 1)
        self.tabs.addTab(self.tab_notes, "")

         # Hatırlatmalar sekmesi
        self.tab_reminders = QWidget()
        self.container_reminders = QWidget(self.tab_reminders)
        self.flow_reminders = FlowLayout(self.container_reminders, margin=8, hspacing=12, vspacing=12)
        self.container_reminders.setLayout(self.flow_reminders)

        self.scroll_reminders = QScrollArea(self.tab_reminders)
        self.scroll_reminders.setWidgetResizable(True)
        self.scroll_reminders.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_reminders.setWidget(self.container_reminders)

        lay_reminders = QVBoxLayout(self.tab_reminders)
        lay_reminders.setContentsMargins(0, 0, 0, 0)
        lay_reminders.addWidget(self.scroll_reminders, 1)
        self.tabs.addTab(self.tab_reminders, "")

        # Sekme değişimi (tablar eklendikten sonra bağla)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Kök
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tabs, 1)

        # Toast
        self._toast = Toast(self)

        # Durum
        self._items_all: List[ItemWidget] = []
        self._items_fav: List[ItemWidget] = []
        self._note_cards: List[NoteWidget] = []
        self._reminder_cards: List[ReminderWidget] = []

        # Sayfalama durumları
        self._offset_all = 0
        self._offset_fav = 0
        self._offset_notes = 0
        self._offset_reminders = 0
        self._loading_all = False
        self._loading_fav = False
        self._loading_notes = False
        self._loading_reminders = False
        self._no_more_all = False
        self._no_more_fav = False
        self._no_more_notes = False
        self._no_more_reminders = False

        # Loader widget’ları ve gecikme timer’ları
        self._loader_all: Optional[LoaderWidget] = None
        self._loader_fav: Optional[LoaderWidget] = None
        self._loader_notes: Optional[LoaderWidget] = None
        self._loader_reminders: Optional[LoaderWidget] = None
        self._loader_timer_all: Optional[QTimer] = None
        self._loader_timer_fav: Optional[QTimer] = None
        self._loader_timer_notes: Optional[QTimer] = None
        self._loader_timer_reminders: Optional[QTimer] = None

        i18n.languageChanged.connect(self.refresh_texts)
        self.refresh_texts()

        # ESC ile gizle
        QShortcut(QKeySequence("Escape"), self, activated=self.hide)

        # Scroll izleme
        self.scroll_all.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("all"))
        self.scroll_fav.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("fav"))
        self.scroll_notes.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("notes"))
        self.scroll_reminders.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("reminders"))


        # Başlangıçta buton görünürlüğünü ayarla
        self._on_tab_changed(self.tabs.currentIndex())

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
        self.btn_add_note.setText(self._tr("notes.add_button_label", "Add Note"))
        self.btn_clear_notes.setText(self._tr("notes.clear_all", "Clear All Notes"))
        self.btn_settings.setText(self._tr("history.settings", "Settings"))
        self.btn_clear.setText(self._tr("history.clear_history", "Clear History"))
        self.tabs.setTabText(0, self._tr("history.tab_all", "All"))
        self.tabs.setTabText(1, self._tr("history.tab_favorites", "Favorites"))
        self.tabs.setTabText(2, self._tr("history.tab_notes", "Notes"))
        self.tabs.setTabText(3, self._tr("history.tab_reminders", "Hatırlatmalar"))
        self.btn_add_reminder.setText(self._tr("reminders.add_button_label", "Hatırlatma Ekle"))
        self.btn_clear_reminders.setText(self._tr("reminders.clear_all", "Tümünü Sil"))

    def _on_tab_changed(self, idx: int):
        notes_idx = self.tabs.indexOf(getattr(self, "tab_notes", None))
        reminders_idx = self.tabs.indexOf(getattr(self, "tab_reminders", None))
        
        only_notes = (idx == notes_idx)
        only_reminders = (idx == reminders_idx)
        
        # Buton görünürlükleri
        self.btn_add_note.setVisible(only_notes)
        self.btn_clear_notes.setVisible(only_notes)
        self.btn_add_reminder.setVisible(only_reminders)
        self.btn_clear_reminders.setVisible(only_reminders)
        self.btn_clear.setVisible(not only_notes and not only_reminders)
        
        QTimer.singleShot(0, self._refresh_layouts)
        QTimer.singleShot(50, self._refresh_layouts)

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
        # İlk sayfaları yükle
        self.reload_items()
        QTimer.singleShot(0, self._refresh_layouts)
        QTimer.singleShot(50, self._refresh_layouts)
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

    # Reflow'u anında zorlayan yardımcı
    def _reflow_now(self, which: str):
        if which == "all":
            flow = self.flow_all
            container = self.container_all
            scroll = self.scroll_all
        elif which == "fav":
            flow = self.flow_fav
            container = self.container_fav
            scroll = self.scroll_fav
        elif which == "notes":
            flow = self.flow_notes
            container = self.container_notes
            scroll = self.scroll_notes
        else:  # reminders
            flow = self.flow_reminders
            container = self.container_reminders
            scroll = self.scroll_reminders

        try:
            flow.activate()
        except Exception:
            pass
        try:
            flow.setGeometry(container.rect())
        except Exception:
            pass

        container.updateGeometry()
        container.adjustSize()
        if scroll and scroll.viewport():
            scroll.viewport().update()

    def _refresh_layouts(self):
        for which in ("all", "fav", "notes", "reminders"):
            self._reflow_now(which)

    # ---------- Lazy load ----------

    def reload_items(self):
        # durum sıfırla
        self._clear_flows()
        self._offset_all = self._offset_fav = self._offset_notes = 0
        self._no_more_all = self._no_more_fav = self._no_more_notes = False

        # İlk 9
        self._load_page("all", first=True)
        self._load_page("fav", first=True)
        self._load_page("notes", first=True)
        self._load_page("reminders", first=True)


    def _maybe_load_more(self, which: str):
        # Arama aktifken lazy load devre dışı (basitlik)
        if (self.search.text() or "").strip():
            return
        scroll = self.scroll_all if which == "all" else (self.scroll_fav if which == "fav" else self.scroll_notes)
        sb = scroll.verticalScrollBar()
        if sb.maximum() - sb.value() <= 120:  # dipte
            self._load_page(which, first=False)

    def _show_loader_later(self, which: str):
        def _create_and_show():
            loader = LoaderWidget(self._tr("loader.loading", "Loading…"))
            if which == "all":
                self._loader_all = loader
                self.flow_all.addWidget(loader)
                self._reflow_now("all")
            elif which == "fav":
                self._loader_fav = loader
                self.flow_fav.addWidget(loader)
                self._reflow_now("fav")
            else:
                self._loader_notes = loader
                self.flow_notes.addWidget(loader)
                self._reflow_now("notes")
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(_create_and_show)
        t.start(LOADER_DELAY_MS)
        if which == "all":
            self._loader_timer_all = t
        elif which == "fav":
            self._loader_timer_fav = t
        else:
            self._loader_timer_notes = t

    def _hide_loader(self, which: str):
        if which == "all":
            if self._loader_timer_all:
                self._loader_timer_all.stop()
            w = self._loader_all
            self._loader_timer_all = None
            self._loader_all = None
        elif which == "fav":
            if self._loader_timer_fav:
                self._loader_timer_fav.stop()
            w = self._loader_fav
            self._loader_timer_fav = None
            self._loader_fav = None
        else:
            if self._loader_timer_notes:
                self._loader_timer_notes.stop()
            w = self._loader_notes
            self._loader_timer_notes = None
            self._loader_notes = None
        if w:
            try:
                (self.flow_all if which == "all" else self.flow_fav if which == "fav" else self.flow_notes).removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
            self._reflow_now(which)

    def _load_page(self, which: str, first: bool):  # <- 4 BOŞLUK GİRİNTİ (sınıf içinde)
        # Halihazırda yükleniyor ya da bitti mi?
        if which == "all":  # <- 8 BOŞLUK GİRİNTİ (metod içinde)
            if self._loading_all or self._no_more_all:  # <- 12 BOŞLUK
                return  # <- 16 BOŞLUK
            self._loading_all = True  # <- 12 BOŞLUK
        elif which == "fav":
            if self._loading_fav or self._no_more_fav:
                return
            self._loading_fav = True
        elif which == "notes":
            if self._loading_notes or self._no_more_notes:
                return
            self._loading_notes = True
        else:  # reminders
            if self._loading_reminders or self._no_more_reminders:
                return
            self._loading_reminders = True

        # Loader'ı gecikmeli göster
        self._show_loader_later(which)

        # Sorgu
        try:
            if which in ("all", "fav"):
                limit = PRIME_COUNT if first else PAGE_SIZE
                offset = self._offset_all if which == "all" else self._offset_fav
                rows = self.storage.list_items(limit=limit, favorites_only=(which == "fav"), offset=offset)
                if not rows:
                    if which == "all":
                        self._no_more_all = True
                    else:
                        self._no_more_fav = True
                else:
                    for row in rows:
                        self._add_row_widget("all" if which == "all" else "fav", row, immediate_layout=True)
                    if which == "all":
                        self._offset_all += len(rows)
                    else:
                        self._offset_fav += len(rows)
            elif which == "notes":
                limit = PRIME_COUNT if first else PAGE_SIZE
                rows = self.storage.list_notes(limit=limit, offset=self._offset_notes)
                if not rows:
                    self._no_more_notes = True
                else:
                    for r in rows:
                        self._add_note_card(r)
                    self._offset_notes += len(rows)
            else:  # reminders
                limit = PRIME_COUNT if first else PAGE_SIZE
                rows = self.storage.list_reminders(limit=limit, offset=self._offset_reminders)
                if not rows:
                    self._no_more_reminders = True
                else:
                    for r in rows:
                        self._add_reminder_card(r)
                    self._offset_reminders += len(rows)
        finally:
            self._hide_loader(which)
            if which == "all":
                self._loading_all = False
            elif which == "fav":
                self._loading_fav = False
            elif which == "notes":
                self._loading_notes = False
            else:  # reminders
                self._loading_reminders = False

        # İlk sayfa sonrası filtre uygula
        if first:
            self.apply_filter(self.search.text())
            QTimer.singleShot(0, self._refresh_layouts)

    def _add_note_card(self, row):
        # Kartı oluştur
        w = NoteWidget(row, self.container_notes)

        # Sinyaller
        def do_copy(_note_id_unused, _type_unused, payload):
            copy_to_clipboard_safely(self, ClipItemType.TEXT, payload)
            if self.settings.get("show_toast", True) and self._toast:
                self._toast.show_message(self._tr("notes.copied", "Note copied to clipboard."))

        def do_delete(note_id_to_delete: int):
            mb = QMessageBox(self)
            mb.setWindowTitle(self._tr("confirm.delete.title", "Delete Confirmation"))
            mb.setText(self._tr("confirm.delete.text", "Are you sure you want to delete this item?"))
            mb.setIcon(QMessageBox.Warning)
            mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            mb.setDefaultButton(QMessageBox.No)
            if mb.exec() != QMessageBox.Yes:
                return
            try:
                self.storage.delete_note(note_id_to_delete)
            finally:
                try:
                    self.flow_notes.removeWidget(w)
                except Exception:
                    pass
                if hasattr(self, "_note_cards") and w in self._note_cards:
                    self._note_cards.remove(w)
                w.setParent(None)
                w.deleteLater()
                self._reflow_now("notes")

        def do_edit(note_id: int, new_text: str):
            try:
                if hasattr(self.storage, "update_note"):
                    self.storage.update_note(note_id, new_text)
                w.set_content(new_text)
                if self._toast and self.settings.get("show_toast", True):
                    self._toast.show_message(self._tr("notes.edited", "Note updated."))
            finally:
                QTimer.singleShot(0, lambda: self._reflow_now("notes"))

        w.on_copy_requested.connect(do_copy)
        w.on_delete_requested.connect(do_delete)
        if hasattr(w, "on_edit_requested"):
            w.on_edit_requested.connect(do_edit)

        # En üste ekle (gizlemeden), sonra göster
        try:
            self.flow_notes.insertWidget(0, w)
            if not hasattr(self, "_note_cards"):
                self._note_cards = []
            self._note_cards.insert(0, w)
        except Exception:
            self.flow_notes.addWidget(w)
            self._note_cards.append(w)

        # Görünürlük (geçerli arama sorgusuna göre)
        q = (self.search.text() or "").lower().strip()
        try:
            # NoteWidget için basit kontrol: tüm QLabel metinlerini birleştir
            lbls = w.findChildren(QLabel)
            full_text = " ".join([(l.text() or "") for l in lbls]).lower() if lbls else ""
            w.setVisible((q in full_text) if q else True)
        except Exception:
            w.setVisible(True)

        # Hemen göster ve düzeni uygula
        w.show()
        try:
            self.flow_notes.activate()
        except Exception:
            pass
        self._reflow_now("notes")

    def _add_note_dialog(self):
        # Çok satırlı giriş
        text, ok = QInputDialog.getMultiLineText(
            self,
            self._tr("notes.add.title", "New Note"),
            self._tr("notes.add.prompt", "Content:"),
            "",
        )
        if not ok:
            return

        content = (text or "").strip()
        if not content:
            return

        # 1) DB'ye ekle
        created_at = QDateTime.currentDateTime().toString(Qt.ISODate)
        row = None
        try:
            # Storage.add_note bir sqlite3.Row döndürmeli
            row = self.storage.add_note(content, created_at)
        except Exception:
            row = None

        # 2) Güvenli geri dönüş (add_note None dönerse en son notu getir)
        if row is None:
            try:
                rows = self.storage.list_notes(limit=1, offset=0)
                row = rows[0] if rows else {"id": -1, "content": content, "created_at": created_at}
            except Exception:
                row = {"id": -1, "content": content, "created_at": created_at}

        # 3) UI: En üste ekle ve anında görünür yap
        self._add_note_card(row)

        # 4) Filtre uygula (aranan ifade varsa görünürlük buna göre ayarlanır)
        self.apply_filter(self.search.text())

        # 5) Notlar sekmesindeysek en üste kaydır
        if getattr(self, "tab_notes", None) and self.tabs.currentWidget() is self.tab_notes:
            sb = self.scroll_notes.verticalScrollBar()
            sb.setValue(sb.minimum())

        # 6) Küçük reflow’lar
        QTimer.singleShot(0, lambda: self._reflow_now("notes"))
        QTimer.singleShot(50, lambda: self._reflow_now("notes"))

        # 7) Toast
        if self._toast and self.settings.get("show_toast", True):
            self._toast.show_message(self._tr("notes.added", "Note added."))

    # ---------- Metin ve favori kartları ----------

    def _add_row_widget(self, kind: str, row, immediate_layout: bool = False):
        if kind == "all":
            w = ItemWidget(row, self.container_all)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_all.addWidget(w)
            self._items_all.append(w)
            which = "all"
        else:
            w = ItemWidget(row, self.container_fav)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_fav.addWidget(w)
            self._items_fav.append(w)
            which = "fav"

        if immediate_layout:
            self._reflow_now(which)

        q = (self.search.text() or "").lower().strip()
        w.setVisible(self._match_row_text(w, q))
        QTimer.singleShot(0, lambda: self._reflow_now(which))

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

        for w in list(self._note_cards):
            try:
                self.flow_notes.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._note_cards.clear()

        for w in list(self._reminder_cards):
            try:
                self.flow_reminders.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._reminder_cards.clear()
        self.flow_reminders.invalidate()

        self.flow_all.invalidate()
        self.flow_fav.invalidate()
        self.flow_notes.invalidate()

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
        # Notlar için basit arama
        for card in self._note_cards:
            lbls = card.findChildren(QLabel)
            text_join = " ".join([l.text() or "" for l in lbls]) if lbls else ""
            card.setVisible(q in text_join.lower() if q else True)
        for card in self._reminder_cards:
            lbls = card.findChildren(QLabel)
            text_join = " ".join([l.text() or "" for l in lbls]) if lbls else ""
            card.setVisible(q in text_join.lower() if q else True)
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

        self._reflow_now("all")
        w.setVisible(self._match_row_text(row, (self.search.text() or "").lower().strip()))
        if bool(row_val(row, "favorite", False)):
            self._add_to_favorites_ui(row)
        QTimer.singleShot(0, lambda: self._reflow_now("all"))

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
            # DB başarısızsa yeniden yükle
            self.reload_items()

    def on_favorite_toggled(self, row_id: int, fav: bool):
        try:
            self.storage.set_favorite(row_id, fav)
        except Exception:
            pass

        # All sekmesindeki butonu senkronla
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
        QTimer.singleShot(0, lambda: self._reflow_now("fav"))

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
        self._items_fav.insert(0, wf)

        self._reflow_now("fav")
        wf.setVisible(self._match_row_text(row2, (self.search.text() or "").lower().strip()))
        self._reflow_now("fav")

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
            self._reflow_now("fav")

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
        self._reflow_now("all")

    # ---------- Notlar: toplu sil ----------
    def _clear_all_notes(self):
        mb = QMessageBox(self)
        mb.setWindowTitle(self._tr("notes.clear_all.title", "Confirm"))
        mb.setText(self._tr("notes.clear_all.prompt", "Delete all notes? This cannot be undone."))
        mb.setIcon(QMessageBox.Warning)
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        if mb.exec() != QMessageBox.Yes:
            return

        try:
            if hasattr(self.storage, "clear_notes"):
                self.storage.clear_notes()
            else:
                # Fallback: listeleyip teker teker sil
                while True:
                    rows = self.storage.list_notes(limit=100, offset=0)
                    if not rows:
                        break
                    for r in rows:
                        try:
                            self.storage.delete_note(int(row_val(r, "id", -1)))
                        except Exception:
                            pass
        finally:
            # UI'ı temizle
            for w in list(self._note_cards):
                try:
                    self.flow_notes.removeWidget(w)
                except Exception:
                    pass
                w.setParent(None)
                w.deleteLater()
            self._note_cards.clear()
            self._offset_notes = 0
            self._no_more_notes = False
            self._reflow_now("notes")

    def import_note(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Notu İçe Aktar", "", "JSON Dosyası (*.json)")
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                json_data = f.read()
            ok = import_items_from_json(self.storage, json_data)
            if ok:
                self.reload_items()
                QMessageBox.information(self, "Başarılı", "Not başarıyla eklendi.")
            else:
                QMessageBox.warning(self, "Hata", "Not eklenirken hata oluştu.")

    def _add_reminder_dialog(self):
        """Yeni hatırlatma dialog'u aç"""
        dlg = ReminderDialog(self)
        if not dlg.exec():
            return
        
        data = dlg.get_data()
        
        # DB'ye ekle
        from datetime import datetime
        created_at = datetime.now().isoformat()
        row = None
        try:
            row = self.storage.add_reminder(
                title=data["title"],
                description=data["description"],
                reminder_time=data["reminder_time"],
                repeat_type=data["repeat_type"],
                created_at=created_at
            )
        except Exception:
            row = None
        
        if row is None:
            try:
                rows = self.storage.list_reminders(limit=1, offset=0)
                row = rows[0] if rows else {
                    "id": -1, 
                    "title": data["title"],
                    "description": data["description"],
                    "reminder_time": data["reminder_time"],
                    "repeat_type": data["repeat_type"],
                    "is_active": 1,
                    "created_at": created_at
                }
            except Exception:
                return
        
        # UI'ye ekle
        self._add_reminder_card(row)
        self.apply_filter(self.search.text())
        
        # Hatırlatmalar sekmesindeyse en üste kaydır
        if self.tabs.currentWidget() is self.tab_reminders:
            sb = self.scroll_reminders.verticalScrollBar()
            sb.setValue(sb.minimum())
        
        QTimer.singleShot(0, lambda: self._reflow_now("reminders"))
        QTimer.singleShot(50, lambda: self._reflow_now("reminders"))
        
        if self._toast and self.settings.get("show_toast", True):
            self._toast.show_message(self._tr("reminders.added", "Hatırlatma eklendi."))

    def _add_reminder_card(self, row):
        """Hatırlatma kartı ekle"""
        w = ReminderWidget(row, self.container_reminders)
        
        # Sinyaller
        w.on_edit_requested.connect(self._edit_reminder)
        w.on_delete_requested.connect(self._delete_reminder)
        w.on_toggle_requested.connect(self._toggle_reminder)
        
        # En üste ekle
        try:
            self.flow_reminders.insertWidget(0, w)
            if not hasattr(self, "_reminder_cards"):
                self._reminder_cards = []
            self._reminder_cards.insert(0, w)
        except Exception:
            self.flow_reminders.addWidget(w)
            self._reminder_cards.append(w)
        
        # Görünürlük
        q = (self.search.text() or "").lower().strip()
        try:
            lbls = w.findChildren(QLabel)
            full_text = " ".join([(l.text() or "") for l in lbls]).lower() if lbls else ""
            w.setVisible((q in full_text) if q else True)
        except Exception:
            w.setVisible(True)
        
        w.show()
        self._reflow_now("reminders")

    def _edit_reminder(self, reminder_id: int):
        """Hatırlatmayı düzenle"""
        reminder = self.storage.get_reminder(reminder_id)
        if not reminder:
            return
        
        dlg = ReminderDialog(self, reminder)
        if not dlg.exec():
            return
        
        data = dlg.get_data()
        
        try:
            self.storage.update_reminder(
                reminder_id=reminder_id,
                title=data["title"],
                description=data["description"],
                reminder_time=data["reminder_time"],
                repeat_type=data["repeat_type"]
            )
        except Exception:
            pass
        
        # UI'yi güncelle
        w = next((card for card in self._reminder_cards if card.reminder_id == reminder_id), None)
        if w:
            # Widget'ı yeniden oluştur
            idx = self._reminder_cards.index(w)
            self.flow_reminders.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
            self._reminder_cards.remove(w)
            
            # Yeni widget ekle
            new_reminder = self.storage.get_reminder(reminder_id)
            if new_reminder:
                new_w = ReminderWidget(new_reminder, self.container_reminders)
                new_w.on_edit_requested.connect(self._edit_reminder)
                new_w.on_delete_requested.connect(self._delete_reminder)
                new_w.on_toggle_requested.connect(self._toggle_reminder)
                
                self.flow_reminders.insertWidget(idx, new_w)
                self._reminder_cards.insert(idx, new_w)
                
                q = (self.search.text() or "").lower().strip()
                lbls = new_w.findChildren(QLabel)
                full_text = " ".join([(l.text() or "") for l in lbls]).lower() if lbls else ""
                new_w.setVisible((q in full_text) if q else True)
        
        self._reflow_now("reminders")
        
        if self._toast and self.settings.get("show_toast", True):
            self._toast.show_message(self._tr("reminders.updated", "Hatırlatma güncellendi."))

    def _delete_reminder(self, reminder_id: int):
        """Hatırlatmayı sil"""
        mb = QMessageBox(self)
        mb.setWindowTitle(self._tr("confirm.delete.title", "Silme Onayı"))
        mb.setText(self._tr("confirm.delete.reminder", "Bu hatırlatmayı silmek istediğinizden emin misiniz?"))
        mb.setIcon(QMessageBox.Warning)
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        
        if mb.exec() != QMessageBox.Yes:
            return
        
        try:
            self.storage.delete_reminder(reminder_id)
        except Exception:
            pass
        
        # UI'den kaldır
        w = next((card for card in self._reminder_cards if card.reminder_id == reminder_id), None)
        if w:
            try:
                self.flow_reminders.removeWidget(w)
            except Exception:
                pass
            if w in self._reminder_cards:
                self._reminder_cards.remove(w)
            w.setParent(None)
            w.deleteLater()
        
        self._reflow_now("reminders")

    def _toggle_reminder(self, reminder_id: int, is_active: bool):
        """Hatırlatmayı aktif/pasif yap"""
        try:
            self.storage.set_reminder_active(reminder_id, is_active)
        except Exception:
            pass

    def _clear_all_reminders(self):
        """Tüm hatırlatmaları sil"""
        mb = QMessageBox(self)
        mb.setWindowTitle(self._tr("reminders.clear_all.title", "Onay"))
        mb.setText(self._tr("reminders.clear_all.prompt", "Tüm hatırlatmalar silinecek. Emin misiniz?"))
        mb.setIcon(QMessageBox.Warning)
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        
        if mb.exec() != QMessageBox.Yes:
            return
        
        try:
            if hasattr(self.storage, "clear_reminders"):
                self.storage.clear_reminders()
        except Exception:
            pass
        
        # UI'ı temizle
        for w in list(self._reminder_cards):
            try:
                self.flow_reminders.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._reminder_cards.clear()
        self._offset_reminders = 0
        self._no_more_reminders = False
        self._reflow_now("reminders")