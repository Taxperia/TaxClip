from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal, QDateTime
from PySide6.QtGui import QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
    QProgressBar,
    QInputDialog,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QDateEdit,
    QCheckBox
)

from ..i18n import i18n
from ..settings import Settings
from ..sensitive_detector import ensure_sensitive_access
from ..storage import ClipItemType, Storage, _normalize_search_text, _strip_html_tags
from ..utils import copy_to_clipboard_safely, resource_path, svg_icon
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

        # Üst bar - Arama
        self.search = QLineEdit()
        self.search.setMinimumHeight(32)
        self.search.setPlaceholderText("Ara... (Fuzzy search destekli)")
        self.search.textChanged.connect(self._on_search_changed)
        
        # Gelişmiş filtreler
        self.filter_panel = QWidget()
        self.filter_panel.setVisible(False)  # Başlangıçta gizli
        
        # Tip filtresi
        self.lbl_type_filter = QLabel("Tip:")
        self.cmb_type_filter = QComboBox()
        self.cmb_type_filter.addItem("Tümü", None)
        self.cmb_type_filter.addItem("Metin", [ClipItemType.TEXT, ClipItemType.HTML])
        self.cmb_type_filter.addItem("Resim", [ClipItemType.IMAGE])
        self.cmb_type_filter.currentIndexChanged.connect(self._on_filter_changed)
        
        # Tarih filtresi
        self.lbl_date_filter = QLabel("Tarih:")
        self.cmb_date_filter = QComboBox()
        self.cmb_date_filter.addItem("Tüm Zamanlar", "all")
        self.cmb_date_filter.addItem("Bugün", "today")
        self.cmb_date_filter.addItem("Son 7 Gün", "week")
        self.cmb_date_filter.addItem("Son 30 Gün", "month")
        self.cmb_date_filter.addItem("Özel Tarih", "custom")
        self.cmb_date_filter.currentIndexChanged.connect(self._on_filter_changed)
        
        # Özel tarih seçici (başlangıçta gizli)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setVisible(False)
        self.date_from.dateChanged.connect(self._on_filter_changed)
        
        self.lbl_date_to = QLabel("-")
        self.lbl_date_to.setVisible(False)
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setVisible(False)
        self.date_to.dateChanged.connect(self._on_filter_changed)
        
        # Fuzzy threshold
        self.lbl_fuzzy = QLabel("Benzerlik:")
        self.cmb_fuzzy = QComboBox()
        self.cmb_fuzzy.addItem("%90+ (Kesin)", 90)
        self.cmb_fuzzy.addItem("%70+ (Normal)", 70)
        self.cmb_fuzzy.addItem("%50+ (Esnek)", 50)
        self.cmb_fuzzy.addItem("%30+ (Çok Esnek)", 30)
        self.cmb_fuzzy.setCurrentIndex(1)  # Varsayılan %70
        self.cmb_fuzzy.currentIndexChanged.connect(self._on_filter_changed)
        
        # Filtre toggle butonu
        self.btn_toggle_filters = QPushButton("🔍 Gelişmiş")
        self.btn_toggle_filters.setMinimumHeight(32)
        self.btn_toggle_filters.setCheckable(True)
        self.btn_toggle_filters.clicked.connect(self._toggle_filters)
        
        # Filtre paneli layout
        filter_layout = QHBoxLayout(self.filter_panel)
        filter_layout.setContentsMargins(0, 4, 0, 4)
        filter_layout.addWidget(self.lbl_type_filter)
        filter_layout.addWidget(self.cmb_type_filter)
        filter_layout.addWidget(self.lbl_date_filter)
        filter_layout.addWidget(self.cmb_date_filter)
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(self.lbl_date_to)
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(self.lbl_fuzzy)
        filter_layout.addWidget(self.cmb_fuzzy)
        filter_layout.addStretch()

        # Not Ekle (yalnız Notlar sekmesinde görünür)
        self.btn_add_note = QPushButton()
        self.btn_add_note.setMinimumHeight(32)
        self.btn_add_note.clicked.connect(self._add_note_dialog)
        self.btn_add_note.setVisible(False)
        try:
            p = resource_path("assets/icons/note_add.svg")
            if p and p.exists():
                self.btn_add_note.setIcon(svg_icon(p))
        except Exception:
            pass
        
        self.btn_clear_reminders = QPushButton()
        self.btn_clear_reminders.setMinimumHeight(32)
        self.btn_clear_reminders.clicked.connect(self._clear_all_reminders)
        self.btn_clear_reminders.setVisible(False)
        try:
            p = resource_path("assets/icons/delete.svg")
            if p and p.exists():
                self.btn_clear_reminders.setIcon(svg_icon(p))
        except Exception:
            pass
        
        self.btn_add_reminder = QPushButton()
        self.btn_add_reminder.setMinimumHeight(32)
        self.btn_add_reminder.clicked.connect(self._add_reminder_dialog)
        self.btn_add_reminder.setVisible(False)
        try:
            p = resource_path("assets/icons/alarm_add.svg")
            if p and p.exists():
                self.btn_add_reminder.setIcon(svg_icon(p))
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
                self.btn_clear_notes.setIcon(svg_icon(p))
        except Exception:
            pass
        
        # Yeni snippet ekle
        self.btn_add_snippet = QPushButton()
        self.btn_add_snippet.setMinimumHeight(32)
        self.btn_add_snippet.clicked.connect(self._add_new_snippet)
        self.btn_add_snippet.setVisible(False)
        try:
            p = resource_path("assets/icons/snippet_add.svg")
            if p and p.exists():
                self.btn_add_snippet.setIcon(svg_icon(p))
        except Exception:
            pass
        
        # Tüm snippet'leri temizle
        self.btn_clear_snippets = QPushButton()
        self.btn_clear_snippets.setMinimumHeight(32)
        self.btn_clear_snippets.clicked.connect(self._clear_all_snippets)
        self.btn_clear_snippets.setVisible(False)
        try:
            p = resource_path("assets/icons/delete.svg")
            if p and p.exists():
                self.btn_clear_snippets.setIcon(svg_icon(p))
        except Exception:
            pass

        # Yeni Liste butonu
        self.btn_add_todo = QPushButton()
        self.btn_add_todo.setMinimumHeight(32)
        self.btn_add_todo.clicked.connect(self._create_new_todo_list)
        try:
            self.btn_add_todo.setIcon(svg_icon("assets/icons/note_add.svg"))
        except Exception:
            pass

        self.btn_clear_todos = QPushButton()
        self.btn_clear_todos.setMinimumHeight(32)
        self.btn_clear_todos.setVisible(False)
        self.btn_clear_todos.clicked.connect(self._clear_all_todo_lists)
        try:
            self.btn_clear_todos.setIcon(svg_icon("assets/icons/clear.svg"))
        except Exception:
            pass
        
        # Yeni çizim
        self.btn_add_drawing = QPushButton()
        self.btn_add_drawing.setMinimumHeight(32)
        self.btn_add_drawing.clicked.connect(self._create_new_drawing)
        try:
            self.btn_add_drawing.setIcon(svg_icon("assets/icons/drawing_add.svg"))
        except Exception:
            pass
        
        # Çizimleri temizle
        self.btn_clear_drawings = QPushButton()
        self.btn_clear_drawings.setMinimumHeight(32)
        self.btn_clear_drawings.clicked.connect(self._clear_all_drawings)
        try:
            self.btn_clear_drawings.setIcon(svg_icon("assets/icons/clear.svg"))
        except Exception:
            pass
        
        # Ayarlar
        self.btn_settings = QPushButton()
        self.btn_settings.setMinimumHeight(32)
        self.btn_settings.clicked.connect(self._on_open_settings_clicked)
        try:
            self.btn_settings.setIcon(svg_icon("assets/icons/gear.svg"))
        except Exception:
            pass

        # Geçmişi temizle (tüm öğeler)
        self.btn_clear = QPushButton()
        self.btn_clear.setMinimumHeight(32)
        self.btn_clear.clicked.connect(self.clear_history)
        try:
            self.btn_clear.setIcon(svg_icon("assets/icons/clear.svg"))
        except Exception:
            pass

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_toggle_filters)
        top.addStretch(1)
        top.addWidget(self.btn_add_todo)
        top.addWidget(self.btn_add_note)
        top.addWidget(self.btn_add_reminder)
        top.addWidget(self.btn_add_snippet)
        top.addWidget(self.btn_add_drawing)  # Yeni Çizim butonu
        top.addWidget(self.btn_clear_reminders)  # Tümünü Sil (Hatırlatmalar)
        top.addWidget(self.btn_clear_notes)      # Tümünü Sil (Notlar)
        top.addWidget(self.btn_clear_snippets)   # Tümünü Sil (Snippets)
        top.addWidget(self.btn_clear_todos)      # Tümünü Sil (Listeler)
        top.addWidget(self.btn_clear_drawings)   # Tümünü Sil (Çizimler)
        top.addWidget(self.btn_clear)            # Tümünü Sil (Geçmiş) - solda
        top.addWidget(self.btn_settings)         # Ayarlar - sağda

        # Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setMinimumHeight(200)
        
        # Arama sonucu yok widget'ı
        self._no_results_widget = QWidget()
        no_results_layout = QVBoxLayout(self._no_results_widget)
        no_results_layout.setAlignment(Qt.AlignCenter)
        self._no_results_icon = QLabel("🔍")
        self._no_results_icon.setStyleSheet("font-size: 48px;")
        self._no_results_icon.setAlignment(Qt.AlignCenter)
        self._no_results_label = QLabel("Sonuç bulunamadı")
        self._no_results_label.setStyleSheet("font-size: 16px; color: #888;")
        self._no_results_label.setAlignment(Qt.AlignCenter)
        self._no_results_hint = QLabel("Farklı bir arama terimi deneyin")
        self._no_results_hint.setStyleSheet("font-size: 12px; color: #666;")
        self._no_results_hint.setAlignment(Qt.AlignCenter)
        no_results_layout.addWidget(self._no_results_icon)
        no_results_layout.addWidget(self._no_results_label)
        no_results_layout.addWidget(self._no_results_hint)
        self._no_results_widget.setVisible(False)
        
        # Arama yükleniyor widget'ı
        self._search_loading_widget = QWidget()
        loading_layout = QVBoxLayout(self._search_loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        self._loading_label = QLabel("⏳ Aranıyor...")
        self._loading_label.setStyleSheet("font-size: 16px; color: #888;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(self._loading_label)
        self._search_loading_widget.setVisible(False)

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
        lay_all.addWidget(self._search_loading_widget)
        lay_all.addWidget(self._no_results_widget)
        lay_all.addWidget(self.scroll_all)
        self.tabs.addTab(self.tab_all, "")

        # Metin
        self.tab_text = QWidget()
        self.container_text = QWidget(self.tab_text)
        self.flow_text = FlowLayout(self.container_text, margin=8, hspacing=12, vspacing=12)
        self.container_text.setLayout(self.flow_text)

        self.scroll_text = QScrollArea(self.tab_text)
        self.scroll_text.setWidgetResizable(True)
        self.scroll_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_text.setWidget(self.container_text)

        lay_text = QVBoxLayout(self.tab_text)
        lay_text.setContentsMargins(0, 0, 0, 0)
        lay_text.addWidget(self.scroll_text)
        self.tabs.addTab(self.tab_text, "")

        # Resim
        self.tab_image = QWidget()
        self.container_image = QWidget(self.tab_image)
        self.flow_image = FlowLayout(self.container_image, margin=8, hspacing=12, vspacing=12)
        self.container_image.setLayout(self.flow_image)

        self.scroll_image = QScrollArea(self.tab_image)
        self.scroll_image.setWidgetResizable(True)
        self.scroll_image.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_image.setWidget(self.container_image)

        lay_image = QVBoxLayout(self.tab_image)
        lay_image.setContentsMargins(0, 0, 0, 0)
        lay_image.addWidget(self.scroll_image)
        self.tabs.addTab(self.tab_image, "")

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

         # Hatırlatmalar sekmesi - UZUNLAMASINA KARTLAR İÇİN VBoxLayout
        self.tab_reminders = QWidget()
        self.container_reminders = QWidget(self.tab_reminders)
        self.flow_reminders = QVBoxLayout(self.container_reminders)
        self.flow_reminders.setContentsMargins(8, 8, 8, 8)
        self.flow_reminders.setSpacing(8)
        self.flow_reminders.addStretch()  # Alt kısımda boşluk için
        self.container_reminders.setLayout(self.flow_reminders)
        
        # Container boyutlarını ayarla
        self.container_reminders.setMinimumWidth(400)

        self.scroll_reminders = QScrollArea(self.tab_reminders)
        self.scroll_reminders.setWidgetResizable(True)
        self.scroll_reminders.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_reminders.setWidget(self.container_reminders)

        lay_reminders = QVBoxLayout(self.tab_reminders)
        lay_reminders.setContentsMargins(0, 0, 0, 0)
        lay_reminders.addWidget(self.scroll_reminders, 1)
        self.tabs.addTab(self.tab_reminders, "")
        
        # Snippet sekmesi
        self.tab_snippets = QWidget()
        self.container_snippets = QWidget(self.tab_snippets)
        self.flow_snippets = QVBoxLayout(self.container_snippets)
        self.flow_snippets.setContentsMargins(8, 8, 8, 8)
        self.flow_snippets.setSpacing(8)
        self.flow_snippets.addStretch()
        self.container_snippets.setLayout(self.flow_snippets)
        self.container_snippets.setMinimumWidth(400)
        
        self.scroll_snippets = QScrollArea(self.tab_snippets)
        self.scroll_snippets.setWidgetResizable(True)
        self.scroll_snippets.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_snippets.setWidget(self.container_snippets)
        
        lay_snippets = QVBoxLayout(self.tab_snippets)
        lay_snippets.setContentsMargins(0, 0, 0, 0)
        lay_snippets.addWidget(self.scroll_snippets, 1)
        self.tabs.addTab(self.tab_snippets, "")
        
        # Listeler (Todo) sekmesi
        self.tab_todos = QWidget()
        lay_todos = QVBoxLayout(self.tab_todos)
        lay_todos.setContentsMargins(10, 10, 10, 10)
        lay_todos.setSpacing(10)
        
        # Scroll area
        scroll_todos = QScrollArea()
        scroll_todos.setWidgetResizable(True)
        scroll_todos.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.container_todos = QWidget()
        self.flow_todos = FlowLayout(self.container_todos)
        self.flow_todos.setSpacing(15)
        scroll_todos.setWidget(self.container_todos)
        
        lay_todos.addWidget(scroll_todos)
        self.tabs.addTab(self.tab_todos, "")
        
        self._todo_cards = []
        
        # Çizimler sekmesi - Kart sistemi
        self.tab_drawings = QWidget()
        lay_drawings = QVBoxLayout(self.tab_drawings)
        lay_drawings.setContentsMargins(10, 10, 10, 10)
        lay_drawings.setSpacing(10)
        
        # Not: "Yeni Çizim" butonu üst barda (btn_add_drawing) zaten var
        
        # Scroll area
        scroll_drawings = QScrollArea()
        scroll_drawings.setWidgetResizable(True)
        scroll_drawings.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.container_drawings = QWidget()
        self.flow_drawings = FlowLayout(self.container_drawings)
        self.flow_drawings.setSpacing(15)
        scroll_drawings.setWidget(self.container_drawings)
        self.scroll_drawings = scroll_drawings  # Referansı sakla
        
        lay_drawings.addWidget(scroll_drawings)
        self.tabs.addTab(self.tab_drawings, "")
        
        self._drawing_cards = []
        
        # Video kayıt sekmesi
        self.tab_video = QWidget()
        from .video_control_widget_v2 import VideoControlWidgetV2
        self.video_control_widget = VideoControlWidgetV2(self.tab_video, self.settings)
        lay_video = QVBoxLayout(self.tab_video)
        lay_video.setContentsMargins(0, 0, 0, 0)
        lay_video.addWidget(self.video_control_widget)
        self.tabs.addTab(self.tab_video, "")

        # Sekme değişimi (tablar eklendikten sonra bağla)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Kök
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.filter_panel)  # Filtre panelini ekle
        root.addWidget(self.tabs, 1)

        # Toast
        self._toast = Toast(self)

        # Durum
        self._items_all: List[ItemWidget] = []
        self._items_text: List[ItemWidget] = []
        self._items_image: List[ItemWidget] = []
        self._items_fav: List[ItemWidget] = []
        self._note_cards: List[NoteWidget] = []
        self._reminder_cards: List[ReminderWidget] = []
        self._snippet_cards = []
        self._first_show = True  # İlk açılış kontrolü

        # Sayfalama durumları
        self._offset_all = 0
        self._offset_text = 0
        self._offset_image = 0
        self._offset_fav = 0
        self._offset_notes = 0
        self._offset_reminders = 0
        self._offset_snippets = 0
        self._loading_all = False
        self._loading_text = False
        self._loading_image = False
        self._loading_fav = False
        self._loading_notes = False
        self._loading_reminders = False
        self._loading_snippets = False
        self._no_more_all = False
        self._no_more_text = False
        self._no_more_image = False
        self._no_more_fav = False
        self._no_more_notes = False
        self._no_more_reminders = False
        self._no_more_snippets = False

        # Loader widget’ları ve gecikme timer’ları
        self._loader_all: Optional[LoaderWidget] = None
        self._loader_text: Optional[LoaderWidget] = None
        self._loader_image: Optional[LoaderWidget] = None
        self._loader_fav: Optional[LoaderWidget] = None
        self._loader_notes: Optional[LoaderWidget] = None
        self._loader_reminders: Optional[LoaderWidget] = None
        self._loader_snippets: Optional[LoaderWidget] = None
        self._loader_timer_all: Optional[QTimer] = None
        self._loader_timer_text: Optional[QTimer] = None
        self._loader_timer_image: Optional[QTimer] = None
        self._loader_timer_fav: Optional[QTimer] = None
        self._loader_timer_notes: Optional[QTimer] = None
        self._loader_timer_snippets: Optional[QTimer] = None
        self._loader_timer_reminders: Optional[QTimer] = None

        i18n.languageChanged.connect(self.refresh_texts)
        self.refresh_texts()

        # ESC ile gizle
        QShortcut(QKeySequence("Escape"), self, activated=self.hide)

        # Scroll izleme
        self.scroll_all.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("all"))
        self.scroll_text.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("text"))
        self.scroll_image.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("image"))
        self.scroll_fav.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("fav"))
        self.scroll_notes.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("notes"))
        self.scroll_reminders.verticalScrollBar().valueChanged.connect(lambda _: self._maybe_load_more("reminders"))


        # Başlangıçta buton görünürlüğünü ayarla
        self._on_tab_changed(self.tabs.currentIndex())
        
        # İLK VERİLERİ CONSTRUCTOR'DA YÜKLE (showEvent'e bağımlı kalma)
        QTimer.singleShot(100, self._initial_load)

    def _initial_load(self):
        """Constructor'dan çağrılır - tüm verileri ilk kez yükle"""
        if self._first_show:  # Sadece ilk seferde
            print("[DEBUG] _initial_load: Tüm veriler yükleniyor...")
            
            # Clip items (all, text, image, fav)
            self.reload_items()
            
            # Notlar
            self._offset_notes = 0
            self._no_more_notes = False
            self._loading_notes = False
            self._load_page("notes", first=True)
            
            # Hatırlatmalar
            self._offset_reminders = 0
            self._no_more_reminders = False
            self._loading_reminders = False
            self._load_page("reminders", first=True)
            
            # Snippet'ler
            self._load_snippets()
            
            # Todo listeleri
            self._load_todo_lists()
            
            # Çizimler
            self._load_drawings()
            
            self._first_show = False
            print("[DEBUG] _initial_load: Yükleme tamamlandı!")

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    # ---------- Gelişmiş Arama Fonksiyonları ----------
    
    def _toggle_filters(self):
        """Gelişmiş filtre panelini göster/gizle"""
        is_visible = self.filter_panel.isVisible()
        self.filter_panel.setVisible(not is_visible)
        self.btn_toggle_filters.setText("🔍 Gelişmiş ▲" if not is_visible else "🔍 Gelişmiş ▼")
    
    def _on_search_changed(self):
        """Arama metni değiştiğinde"""
        # Debounce için timer kullan
        if not hasattr(self, '_search_timer'):
            self._search_timer = QTimer()
            self._search_timer.setSingleShot(True)
            self._search_timer.timeout.connect(self._perform_search)
        self._search_timer.stop()
        self._search_timer.start(300)  # 300ms bekle
    
    def _on_filter_changed(self):
        """Filtre değiştiğinde"""
        # Özel tarih seçiliyse tarih seçicileri göster
        is_custom = self.cmb_date_filter.currentData() == "custom"
        self.date_from.setVisible(is_custom)
        self.lbl_date_to.setVisible(is_custom)
        self.date_to.setVisible(is_custom)
        
        # Arama yap
        self._perform_search()
    
    def _perform_search(self):
        """Gelişmiş arama yap"""
        query = self.search.text().strip()
        
        # Filtre paneli açık değilse normal arama yap
        if not self.filter_panel.isVisible():
            # Arama boşsa tüm widget'ları göster
            if not query:
                for w in self._items_all:
                    w.setVisible(True)
                for w in self._items_text:
                    w.setVisible(True)
                for w in self._items_image:
                    w.setVisible(True)
                for w in self._items_fav:
                    w.setVisible(True)
                for card in self._note_cards:
                    card.setVisible(True)
                for card in self._reminder_cards:
                    card.setVisible(True)
                self._refresh_layouts()
            else:
                self.apply_filter(query)
            return
        
        # Tip filtresi
        item_types = self.cmb_type_filter.currentData()
        
        # Tarih filtresi
        date_from = None
        date_to = None
        date_mode = self.cmb_date_filter.currentData()
        
        from datetime import datetime, timedelta
        if date_mode == "today":
            date_from = datetime.now().strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d 23:59:59")
        elif date_mode == "week":
            date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d 23:59:59")
        elif date_mode == "month":
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d 23:59:59")
        elif date_mode == "custom":
            date_from = self.date_from.date().toString("yyyy-MM-dd")
            date_to = self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        # Fuzzy threshold
        fuzzy_threshold = self.cmb_fuzzy.currentData()
        
        # Aramayı yap
        try:
            results = self.storage.search_items(
                query=query,
                item_types=item_types,
                date_from=date_from,
                date_to=date_to,
                fuzzy_threshold=fuzzy_threshold,
                limit=500
            )
            
            # Sonuçları göster
            self._display_search_results(results)
            
        except Exception as e:
            print(f"[ERROR] Arama hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_search_results(self, results: List[dict]):
        """Arama sonuçlarını göster - yüklenmemiş içerikler için widget oluştur"""
        # Önce tüm widget'ları gizle
        for w in self._items_all:
            w.setVisible(False)
        for w in self._items_text:
            w.setVisible(False)
        for w in self._items_image:
            w.setVisible(False)
        for w in self._items_fav:
            w.setVisible(False)
        
        # Mevcut widget ID'lerini topla
        existing_ids_all = {w.row_id for w in self._items_all}
        existing_ids_text = {w.row_id for w in self._items_text}
        existing_ids_image = {w.row_id for w in self._items_image}
        existing_ids_fav = {w.row_id for w in self._items_fav}
        
        # Sonuçları göster veya oluştur
        for row in results:
            row_id = row["id"]
            item_type = int(row.get("item_type", 0))
            is_favorite = bool(row.get("favorite", False))
            
            # ALL sekmesi
            if row_id in existing_ids_all:
                # Widget zaten var, sadece göster
                for w in self._items_all:
                    if w.row_id == row_id:
                        w.setVisible(True)
                        break
            else:
                # Widget yok, oluştur
                w = ItemWidget(row, self.container_all)
                w.on_copy_requested.connect(self.on_copy_requested)
                w.on_delete_requested.connect(self.on_delete_requested)
                w.on_favorite_toggled.connect(self.on_favorite_toggled)
                self.flow_all.addWidget(w)
                self._items_all.append(w)
                w.setVisible(True)
            
            # TEXT sekmesi
            if item_type in (int(ClipItemType.TEXT), int(ClipItemType.HTML)):
                if row_id in existing_ids_text:
                    for w in self._items_text:
                        if w.row_id == row_id:
                            w.setVisible(True)
                            break
                else:
                    w_text = ItemWidget(row, self.container_text)
                    w_text.on_copy_requested.connect(self.on_copy_requested)
                    w_text.on_delete_requested.connect(self.on_delete_requested)
                    w_text.on_favorite_toggled.connect(self.on_favorite_toggled)
                    self.flow_text.addWidget(w_text)
                    self._items_text.append(w_text)
                    w_text.setVisible(True)
            
            # IMAGE sekmesi
            if item_type == int(ClipItemType.IMAGE):
                if row_id in existing_ids_image:
                    for w in self._items_image:
                        if w.row_id == row_id:
                            w.setVisible(True)
                            break
                else:
                    w_image = ItemWidget(row, self.container_image)
                    w_image.on_copy_requested.connect(self.on_copy_requested)
                    w_image.on_delete_requested.connect(self.on_delete_requested)
                    w_image.on_favorite_toggled.connect(self.on_favorite_toggled)
                    self.flow_image.addWidget(w_image)
                    self._items_image.append(w_image)
                    w_image.setVisible(True)
            
            # FAVORITES sekmesi
            if is_favorite:
                if row_id in existing_ids_fav:
                    for w in self._items_fav:
                        if w.row_id == row_id:
                            w.setVisible(True)
                            break
                else:
                    w_fav = ItemWidget(row, self.container_fav)
                    w_fav.on_copy_requested.connect(self.on_copy_requested)
                    w_fav.on_delete_requested.connect(self.on_delete_requested)
                    w_fav.on_favorite_toggled.connect(self.on_favorite_toggled)
                    self.flow_fav.addWidget(w_fav)
                    self._items_fav.append(w_fav)
                    w_fav.setVisible(True)
        
        self._refresh_layouts()

    # ---------- End Gelişmiş Arama ----------

    def _default_search_threshold(self, query: str) -> int:
        normalized_query = _normalize_search_text(query)
        query_terms = [term for term in normalized_query.split(" ") if term]
        if not query_terms:
            return 100
        if len(query_terms) == 1:
            term = query_terms[0]
            if len(term) <= 3:
                return 98
            if len(term) <= 5:
                return 92
            return 84
        if len(normalized_query) <= 8:
            return 88
        return 80

    def set_open_settings_handler(self, fn: Callable[[], None]):
        self._open_settings_handler = fn

    def set_notifier(self, fn: Callable[[str, str], None]):
        self._notifier = fn

    def refresh_texts(self):
        self.setWindowTitle(self._tr("history.title", "ClipStack - History"))
        self.search.setPlaceholderText("Ara... (Fuzzy search destekli)")
        self.btn_add_note.setText(self._tr("notes.add_button_label", "Add Note"))
        self.btn_clear_notes.setText(self._tr("notes.clear_all", "Clear All Notes"))
        self.btn_add_todo.setText(self._tr("todos.add_button_label", "Yeni Liste"))
        self.btn_add_drawing.setText(self._tr("drawings.add_button_label", "Yeni Çizim"))
        self.btn_settings.setText(self._tr("history.settings", "Settings"))
        self.btn_clear.setText(self._tr("history.clear_history", "Clear History"))
        self.tabs.setTabText(0, self._tr("history.tab_all", "All"))
        self.tabs.setTabText(1, self._tr("history.tab_text", "Metin"))
        self.tabs.setTabText(2, self._tr("history.tab_image", "Resim"))
        self.tabs.setTabText(3, self._tr("history.tab_favorites", "Favorites"))
        self.tabs.setTabText(4, self._tr("history.tab_notes", "Notes"))
        self.tabs.setTabText(5, self._tr("history.tab_reminders", "Hatırlatmalar"))
        self.tabs.setTabText(6, self._tr("history.tab_snippets", "Snippet"))
        self.tabs.setTabText(7, self._tr("history.tab_todos", "Listeler"))
        self.tabs.setTabText(8, self._tr("history.tab_drawings", "Çizimler"))
        self.tabs.setTabText(9, self._tr("history.tab_video", "Video Kayıt"))
        self.btn_add_reminder.setText(self._tr("reminders.add_button_label", "Hatırlatma Ekle"))
        self.btn_clear_reminders.setText(self._tr("reminders.clear_all", "Tümünü Sil"))
        self.btn_add_snippet.setText(self._tr("snippets.add_button_label", "Snippet Ekle"))
        self.btn_clear_snippets.setText(self._tr("snippets.clear_all", "Tümünü Sil"))
        self.btn_clear_todos.setText(self._tr("todos.clear_all", "Tümünü Sil"))
        self.btn_clear_drawings.setText(self._tr("drawings.clear_all", "Tümünü Sil"))

    def _on_tab_changed(self, idx: int):
        notes_idx = self.tabs.indexOf(getattr(self, "tab_notes", None))
        reminders_idx = self.tabs.indexOf(getattr(self, "tab_reminders", None))
        snippets_idx = self.tabs.indexOf(getattr(self, "tab_snippets", None))
        todos_idx = self.tabs.indexOf(getattr(self, "tab_todos", None))
        drawings_idx = self.tabs.indexOf(getattr(self, "tab_drawings", None))
        
        only_notes = (idx == notes_idx)
        only_reminders = (idx == reminders_idx)
        only_snippets = (idx == snippets_idx)
        only_todos = (idx == todos_idx)
        only_drawings = (idx == drawings_idx)
        
        # Buton görünürlükleri
        self.btn_add_note.setVisible(only_notes)
        self.btn_clear_notes.setVisible(only_notes)
        self.btn_add_reminder.setVisible(only_reminders)
        self.btn_clear_reminders.setVisible(only_reminders)
        self.btn_add_snippet.setVisible(only_snippets)
        self.btn_clear_snippets.setVisible(only_snippets)
        self.btn_add_todo.setVisible(only_todos)
        self.btn_clear_todos.setVisible(only_todos)
        self.btn_add_drawing.setVisible(only_drawings)
        self.btn_clear_drawings.setVisible(only_drawings)
        self.btn_clear.setVisible(not only_notes and not only_reminders and not only_snippets and not only_todos and not only_drawings)
        
        # Snippet sekmesinde yükle
        if only_snippets and not self._snippet_cards:
            self._load_snippets()
        
        # Çizimler sekmesi açıldığında layout yenile
        if only_drawings:
            QTimer.singleShot(10, self._refresh_drawings_layout)
            QTimer.singleShot(100, self._refresh_drawings_layout)
        
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
        
        # Layout'u yenile (kartlar zaten constructor'da yüklendi)
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
        elif which == "text":
            flow = self.flow_text
            container = self.container_text
            scroll = self.scroll_text
        elif which == "image":
            flow = self.flow_image
            container = self.container_image
            scroll = self.scroll_image
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
            # VBoxLayout için setGeometry gerekli değil
            if which not in ("reminders",):
                flow.setGeometry(container.rect())
        except Exception:
            pass

        container.updateGeometry()
        container.adjustSize()
        container.update()  # Yeniden çizim zorla
        
        if scroll and scroll.viewport():
            scroll.viewport().update()
            
        # Hatırlatmalar için özel güncelleme
        if which == "reminders":
            print(f"[DEBUG] _reflow_now: {len(self._reminder_cards) if hasattr(self, '_reminder_cards') else 0} hatırlatma kartı güncelleniyor")

    def _refresh_layouts(self):
        for which in ("all", "text", "image", "fav", "notes", "reminders"):
            self._reflow_now(which)
        # Çizimler için de yenile
        if hasattr(self, 'flow_drawings') and hasattr(self, '_drawing_cards'):
            self._refresh_drawings_layout()

    # ---------- Lazy load ----------

    def reload_items(self):
        # durum sıfırla - SADECE clip items için
        self._clear_flows()
        self._offset_all = self._offset_text = self._offset_image = self._offset_fav = 0
        self._no_more_all = self._no_more_text = self._no_more_image = self._no_more_fav = False
        self._loading_all = self._loading_text = self._loading_image = self._loading_fav = False

        # İlk 9 - clip items
        self._load_page("all", first=True)
        self._load_page("text", first=True)
        self._load_page("image", first=True)
        self._load_page("fav", first=True)
        
        # Notlar ve hatırlatmalar ilk açılışta yüklendiler, tekrar yükleme!


    def _maybe_load_more(self, which: str):
        # Arama aktifken lazy load devre dışı (basitlik)
        if (self.search.text() or "").strip():
            return
        if which == "all":
            scroll = self.scroll_all
        elif which == "text":
            scroll = self.scroll_text
        elif which == "image":
            scroll = self.scroll_image
        elif which == "fav":
            scroll = self.scroll_fav
        elif which == "notes":
            scroll = self.scroll_notes
        else:
            scroll = self.scroll_reminders
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
            elif which == "text":
                self._loader_text = loader
                self.flow_text.addWidget(loader)
                self._reflow_now("text")
            elif which == "image":
                self._loader_image = loader
                self.flow_image.addWidget(loader)
                self._reflow_now("image")
            elif which == "fav":
                self._loader_fav = loader
                self.flow_fav.addWidget(loader)
                self._reflow_now("fav")
            elif which == "notes":
                self._loader_notes = loader
                self.flow_notes.addWidget(loader)
                self._reflow_now("notes")
            else:
                self._loader_reminders = loader
                self.flow_reminders.addWidget(loader)
                self._reflow_now("reminders")
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(_create_and_show)
        t.start(LOADER_DELAY_MS)
        if which == "all":
            self._loader_timer_all = t
        elif which == "text":
            self._loader_timer_text = t
        elif which == "image":
            self._loader_timer_image = t
        elif which == "fav":
            self._loader_timer_fav = t
        elif which == "notes":
            self._loader_timer_notes = t
        else:
            self._loader_timer_reminders = t

    def _hide_loader(self, which: str):
        if which == "all":
            if self._loader_timer_all:
                self._loader_timer_all.stop()
            w = self._loader_all
            self._loader_timer_all = None
            self._loader_all = None
        elif which == "text":
            if self._loader_timer_text:
                self._loader_timer_text.stop()
            w = self._loader_text
            self._loader_timer_text = None
            self._loader_text = None
        elif which == "image":
            if self._loader_timer_image:
                self._loader_timer_image.stop()
            w = self._loader_image
            self._loader_timer_image = None
            self._loader_image = None
        elif which == "fav":
            if self._loader_timer_fav:
                self._loader_timer_fav.stop()
            w = self._loader_fav
            self._loader_timer_fav = None
            self._loader_fav = None
        elif which == "notes":
            if self._loader_timer_notes:
                self._loader_timer_notes.stop()
            w = self._loader_notes
            self._loader_timer_notes = None
            self._loader_notes = None
        else:
            if self._loader_timer_reminders:
                self._loader_timer_reminders.stop()
            w = self._loader_reminders
            self._loader_timer_reminders = None
            self._loader_reminders = None
        if w:
            try:
                if which == "all":
                    layout = self.flow_all
                elif which == "text":
                    layout = self.flow_text
                elif which == "image":
                    layout = self.flow_image
                elif which == "fav":
                    layout = self.flow_fav
                elif which == "notes":
                    layout = self.flow_notes
                else:
                    layout = self.flow_reminders
                layout.removeWidget(w)
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
        elif which == "text":
            if self._loading_text or self._no_more_text:
                return
            self._loading_text = True
        elif which == "image":
            if self._loading_image or self._no_more_image:
                return
            self._loading_image = True
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
            if which in ("all", "text", "image", "fav"):
                limit = PRIME_COUNT if first else PAGE_SIZE
                
                # Text ve image için DB'den tüm verileri çek, sonra filtrele
                # (çünkü offset sistem text/image'e uymuyor)
                if which == "text":
                    # Tüm itemları çek (büyük limit)
                    all_rows = self.storage.list_items(limit=10000, favorites_only=False, offset=0)
                    # Sadece text/html olanları filtrele
                    rows = [r for r in all_rows if int(row_val(r, "item_type", 0)) in (int(ClipItemType.TEXT), int(ClipItemType.HTML))]
                    # Offset ve limit uygula
                    rows = rows[self._offset_text:self._offset_text + limit]
                elif which == "image":
                    # Tüm itemları çek
                    all_rows = self.storage.list_items(limit=10000, favorites_only=False, offset=0)
                    # Sadece image olanları filtrele
                    rows = [r for r in all_rows if int(row_val(r, "item_type", 0)) == int(ClipItemType.IMAGE)]
                    # Offset ve limit uygula
                    rows = rows[self._offset_image:self._offset_image + limit]
                else:
                    # All ve fav için normal offset kullan
                    offset = self._offset_all if which == "all" else self._offset_fav
                    rows = self.storage.list_items(limit=limit, favorites_only=(which == "fav"), offset=offset)
                
                if not rows:
                    if which == "all":
                        self._no_more_all = True
                    elif which == "text":
                        self._no_more_text = True
                    elif which == "image":
                        self._no_more_image = True
                    else:
                        self._no_more_fav = True
                else:
                    for row in rows:
                        self._add_row_widget(which, row, immediate_layout=True)
                    if which == "all":
                        self._offset_all += len(rows)
                    elif which == "text":
                        self._offset_text += len(rows)
                    elif which == "image":
                        self._offset_image += len(rows)
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
            elif which == "text":
                self._loading_text = False
            elif which == "image":
                self._loading_image = False
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
        elif kind == "text":
            w = ItemWidget(row, self.container_text)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_text.addWidget(w)
            self._items_text.append(w)
            which = "text"
        elif kind == "image":
            w = ItemWidget(row, self.container_image)
            w.setVisible(False)
            w.on_copy_requested.connect(self.on_copy_requested)
            w.on_delete_requested.connect(self.on_delete_requested)
            w.on_favorite_toggled.connect(self.on_favorite_toggled)
            self.flow_image.addWidget(w)
            self._items_image.append(w)
            which = "image"
        else:  # fav
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

        for w in self._items_text:
            try:
                self.flow_text.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._items_text.clear()

        for w in self._items_image:
            try:
                self.flow_image.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._items_image.clear()

        for w in self._items_fav:
            try:
                self.flow_fav.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._items_fav.clear()

        # NOT: Notlar ve hatırlatmalar reload_items'da SİLİNMEMELİ!
        # Bunlar ayrı sekmelerde ve ayrı yükleniyorlar

        self.flow_all.invalidate()
        self.flow_fav.invalidate()

    def _match_row_text(self, row_or_widget, query: str) -> bool:
        normalized_query = _normalize_search_text(query)
        if not normalized_query:
            return True
        if isinstance(row_or_widget, ItemWidget):
            item_type = row_or_widget.item_type
            if item_type in (ClipItemType.TEXT, ClipItemType.HTML):
                content = _normalize_search_text(row_or_widget.preview_text or "")
                if not content and item_type == ClipItemType.HTML:
                    content = _strip_html_tags(row_or_widget._row("html_content", "") or "")
                return normalized_query in content
            return False
        else:
            t = int(row_val(row_or_widget, "item_type", 0))
            if t in (int(ClipItemType.TEXT), int(ClipItemType.HTML)):
                content = _normalize_search_text(row_val(row_or_widget, "text_content", "") or "")
                if not content:
                    content = _strip_html_tags(row_val(row_or_widget, "html_content", "") or "")
                return normalized_query in content
            return False

    def apply_filter(self, text: str):
        """Arama filtresi uygula - veritabanında da ara"""
        q = (text or "").lower().strip()
        
        if not q:
            # Arama boş - tüm widget'ları göster
            self._no_results_widget.setVisible(False)
            self._search_loading_widget.setVisible(False)
            for w in self._items_all:
                w.setVisible(True)
            for w in self._items_text:
                w.setVisible(True)
            for w in self._items_image:
                w.setVisible(True)
            for w in self._items_fav:
                w.setVisible(True)
            for card in self._note_cards:
                card.setVisible(True)
            for card in self._reminder_cards:
                card.setVisible(True)
            self._refresh_layouts()
            return
        
        # Notlar için basit arama
        for card in self._note_cards:
            lbls = card.findChildren(QLabel)
            text_join = " ".join([l.text() or "" for l in lbls]) if lbls else ""
            card.setVisible(q in text_join.lower() if q else True)
        # Hatırlatmalar için basit arama
        for card in self._reminder_cards:
            lbls = card.findChildren(QLabel)
            text_join = " ".join([l.text() or "" for l in lbls]) if lbls else ""
            card.setVisible(q in text_join.lower() if q else True)

        # Clipboard geçmişi için her zaman veritabanını tara.
        # Aksi halde yüklü birkaç eşleşme varken eski ama doğru kayıtlar hiç getirilmiyordu.
        self._search_in_database(q)
        
        self._refresh_layouts()
    
    def _search_in_database(self, query: str):
        """Veritabanında arama yap ve sonuçları yükle"""
        self._search_loading_widget.setVisible(True)
        self._no_results_widget.setVisible(False)
        QApplication.processEvents()  # UI'ı güncelle
        
        try:
            # Veritabanında ara (fuzzy search ile)
            threshold = self._default_search_threshold(query)
            results = self.storage.search_items(
                query=query,
                fuzzy_threshold=threshold,
                limit=100
            )
            
            self._search_loading_widget.setVisible(False)
            
            if not results:
                # Sonuç bulunamadı
                self._no_results_widget.setVisible(True)
                self._no_results_label.setText(f"'{query}' için sonuç bulunamadı")
                return
            
            # Sonuçları göster
            self._display_search_results(results)
            self._no_results_widget.setVisible(False)
            
        except Exception as e:
            print(f"[ERROR] Veritabanı araması hatası: {e}")
            self._search_loading_widget.setVisible(False)
            self._no_results_widget.setVisible(True)
            self._no_results_label.setText("Arama sırasında bir hata oluştu")

    # ------------------ Anlık olaylar ------------------

    def on_item_added(self, row):
        if not self.isVisible():
            return

        # Tümü sekmesine ekle
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
        
        # Text sekmesine ekle (eğer metin ise)
        item_type = int(row_val(row, "item_type", 0))
        if item_type in (int(ClipItemType.TEXT), int(ClipItemType.HTML)):
            w_text = ItemWidget(row, self.container_text)
            w_text.setVisible(False)
            w_text.on_copy_requested.connect(self.on_copy_requested)
            w_text.on_delete_requested.connect(self.on_delete_requested)
            w_text.on_favorite_toggled.connect(self.on_favorite_toggled)
            try:
                self.flow_text.insertWidget(0, w_text)
            except Exception:
                self.flow_text.addWidget(w_text)
            self._items_text.insert(0, w_text)
            self._reflow_now("text")
            w_text.setVisible(self._match_row_text(row, (self.search.text() or "").lower().strip()))
        
        # Resim sekmesine ekle (eğer resim ise)
        if item_type == int(ClipItemType.IMAGE):
            w_image = ItemWidget(row, self.container_image)
            w_image.setVisible(False)
            w_image.on_copy_requested.connect(self.on_copy_requested)
            w_image.on_delete_requested.connect(self.on_delete_requested)
            w_image.on_favorite_toggled.connect(self.on_favorite_toggled)
            try:
                self.flow_image.insertWidget(0, w_image)
            except Exception:
                self.flow_image.addWidget(w_image)
            self._items_image.insert(0, w_image)
            self._reflow_now("image")
            w_image.setVisible(self._match_row_text(row, (self.search.text() or "").lower().strip()))
        
        if bool(row_val(row, "favorite", False)):
            self._add_to_favorites_ui(row)
        QTimer.singleShot(0, lambda: self._reflow_now("all"))

    def on_copy_requested(self, row_id: int, data_kind: ClipItemType, payload):
        try:
            row = self.storage.get_item(row_id)
        except Exception:
            row = None

        if row:
            item_type = ClipItemType(row["item_type"])
            if item_type in (ClipItemType.TEXT, ClipItemType.HTML):
                probe_text = row.get("text_content") or row.get("html_content") or ""
            else:
                probe_text = row.get("ocr_text") or ""

            if probe_text and not ensure_sensitive_access(self.settings, probe_text, self):
                QMessageBox.warning(
                    self,
                    "Erişim Engellendi",
                    "Bu içerik hassas veri içeriyor. Kopyalamak için doğrulama gerekli."
                )
                return

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
        """Hatırlatma kartı ekle - VBoxLayout için"""
        w = ReminderWidget(row, self.container_reminders)
        
        # Sinyaller
        w.on_edit_requested.connect(self._edit_reminder)
        w.on_delete_requested.connect(self._delete_reminder)
        w.on_toggle_requested.connect(self._toggle_reminder)
        
        # Liste başlat
        if not hasattr(self, "_reminder_cards"):
            self._reminder_cards = []
        
        # VBoxLayout'a ekle - Stretch'den ÖNCE (son eleman stretch)
        # Layout'taki eleman sayısını kontrol et
        layout_count = self.flow_reminders.count()
        
        # Son eleman stretch ise ondan önce ekle, değilse sona ekle
        if layout_count > 0:
            # Stretch genellikle son elemandır, ondan önce ekle
            insert_at = max(0, layout_count - 1)
            self.flow_reminders.insertWidget(insert_at, w)
        else:
            # Layout boşsa direkt ekle
            self.flow_reminders.addWidget(w)
        
        # Listeye ekle
        self._reminder_cards.append(w)
        
        # Widget'ı aktif et
        w.setAttribute(Qt.WA_StyledBackground, True)
        w.setVisible(True)
        w.show()
        
        print(f"[DEBUG] Hatırlatma kartı eklendi: ID={row.get('id')}, is_active={row.get('is_active')}, layout_index={self.flow_reminders.indexOf(w)}")
        
        # Görünürlük filtreleme
        q = (self.search.text() or "").lower().strip()
        if q:
            try:
                lbls = w.findChildren(QLabel)
                full_text = " ".join([(l.text() or "") for l in lbls]).lower() if lbls else ""
                if q not in full_text:
                    w.setVisible(False)
            except Exception as e:
                print(f"[DEBUG] Filtre hatası: {e}")

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
            card_idx = self._reminder_cards.index(w)
            layout_idx = self.flow_reminders.indexOf(w)
            
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
                
                # Aynı pozisyona ekle
                self.flow_reminders.insertWidget(layout_idx, new_w)
                self._reminder_cards.insert(card_idx, new_w)
                
                q = (self.search.text() or "").lower().strip()
                lbls = new_w.findChildren(QLabel)
                full_text = " ".join([(l.text() or "") for l in lbls]).lower() if lbls else ""
                new_w.setVisible((q in full_text) if q else True)
        
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
            print(f"[DEBUG] Reminder {reminder_id} aktif durumu değiştirildi: {is_active}")
            # Widget'ın görünürlüğünü koru!
        except Exception as e:
            print(f"[DEBUG] Reminder toggle hatası: {e}")
            import traceback
            traceback.print_exc()

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

    def on_reminder_time_updated(self, reminder: dict):
        """Hatırlatma tetiklendiğinde veya zamanı değiştiğinde UI'ı güncelle"""
        try:
            reminder_id = reminder.get("id")
            if not reminder_id:
                return

            print(f"[DEBUG] on_reminder_time_updated çağrıldı: ID={reminder_id}, is_active={reminder.get('is_active')}")

            # Mevcut kartı bul
            existing_card = next((card for card in self._reminder_cards if card.reminder_id == reminder_id), None)

            if existing_card:
                # Yeni veriyi çek
                updated_reminder = self.storage.get_reminder(reminder_id)
                if updated_reminder:
                    print(f"[DEBUG] Hatırlatma güncelleniyor: {updated_reminder.get('title')}, is_active={updated_reminder.get('is_active')}")
                    # Sadece switch durumunu güncelle, kartı yeniden oluşturma
                    existing_card.reminder = updated_reminder
                    existing_card.set_active(bool(updated_reminder.get("is_active", 1)))
                    existing_card._update_content()
                    # Widget'ın görünür olduğundan emin ol!
                    if not existing_card.isVisible():
                        print(f"[DEBUG] UYARI: Widget görünmez durumda, görünür yapılıyor!")
                        existing_card.setVisible(True)
                else:
                    print(f"[DEBUG] Hatırlatma veritabanında bulunamadı: {reminder_id}")
            else:
                print(f"[DEBUG] Widget listede bulunamadı: {reminder_id}")
        except Exception as e:
            print(f"Reminder update error: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_snippets(self):
        """Snippet'leri yükle"""
        try:
            snippets = self.storage.list_snippets()
            for snippet in snippets:
                self._add_snippet_card(snippet)
        except Exception as e:
            print(f"[ERROR] Snippet yükleme hatası: {e}")
    
    def _add_snippet_card(self, snippet: dict):
        """Snippet kartı ekle"""
        from .snippet_card_widget import SnippetCardWidget
        
        w = SnippetCardWidget(snippet, self.storage, parent=self.container_snippets)
        w.on_copy_requested.connect(lambda code: self._on_snippet_copy(code))
        w.on_delete_requested.connect(lambda sid: self._delete_snippet(sid))
        w.on_favorite_toggled.connect(lambda sid: self._toggle_snippet_favorite(sid))
        w.on_edit_requested.connect(lambda sid: self._edit_snippet(sid))
        
        # Layout'a ekle
        layout_count = self.flow_snippets.count()
        if layout_count > 0:
            insert_at = max(0, layout_count - 1)
            self.flow_snippets.insertWidget(insert_at, w)
        else:
            self.flow_snippets.addWidget(w)
        
        self._snippet_cards.append(w)
        w.setVisible(True)
        w.show()
    
    def _on_snippet_copy(self, code: str):
        """Snippet kodunu kopyala"""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        self._toast.show_message("✓ Kod kopyalandı")
    
    def _delete_snippet(self, snippet_id: int):
        """Snippet sil"""
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Question)
        mb.setWindowTitle("Snippet Sil")
        mb.setText("Bu snippet'i silmek istediğinize emin misiniz?")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if mb.exec() != QMessageBox.Yes:
            return
        
        self.storage.delete_snippet(snippet_id)
        
        # Widget'ı bul ve sil
        w = next((card for card in self._snippet_cards if card.snippet_id == snippet_id), None)
        if w:
            self.flow_snippets.removeWidget(w)
            self._snippet_cards.remove(w)
            w.setParent(None)
            w.deleteLater()
    
    def _toggle_snippet_favorite(self, snippet_id: int):
        """Snippet favori durumunu değiştir"""
        self.storage.toggle_snippet_favorite(snippet_id)
        
        # Widget'ı yeniden yükle
        w = next((card for card in self._snippet_cards if card.snippet_id == snippet_id), None)
        if w:
            snippet = self.storage.get_snippet(snippet_id)
            if snippet:
                # Widget'ı kaldır ve yenisini ekle
                index = self.flow_snippets.indexOf(w)
                self.flow_snippets.removeWidget(w)
                self._snippet_cards.remove(w)
                w.deleteLater()
                
                # Yeni widget ekle
                from .snippet_card_widget import SnippetCardWidget
                new_w = SnippetCardWidget(snippet, self.storage, parent=self.container_snippets)
                new_w.on_copy_requested.connect(lambda code: self._on_snippet_copy(code))
                new_w.on_delete_requested.connect(lambda sid: self._delete_snippet(sid))
                new_w.on_favorite_toggled.connect(lambda sid: self._toggle_snippet_favorite(sid))
                new_w.on_edit_requested.connect(lambda sid: self._edit_snippet(sid))
                
                if index >= 0:
                    self.flow_snippets.insertWidget(index, new_w)
                else:
                    self.flow_snippets.addWidget(new_w)
                
                self._snippet_cards.append(new_w)
                new_w.show()
    
    def _edit_snippet(self, snippet_id: int):
        """Snippet düzenle"""
        from .snippet_dialog import SnippetDialog
        
        snippet = self.storage.get_snippet(snippet_id)
        if not snippet:
            return
        
        dlg = SnippetDialog(self, snippet)
        if not dlg.exec():
            return
        
        data = dlg.get_data()
        self.storage.update_snippet(snippet_id, **data)
        
        # Widget'ı güncelle
        w = next((card for card in self._snippet_cards if card.snippet_id == snippet_id), None)
        if w:
            updated_snippet = self.storage.get_snippet(snippet_id)
            if updated_snippet:
                # Widget'ı yeniden oluştur
                index = self.flow_snippets.indexOf(w)
                self.flow_snippets.removeWidget(w)
                self._snippet_cards.remove(w)
                w.deleteLater()
                
                from .snippet_card_widget import SnippetCardWidget
                new_w = SnippetCardWidget(updated_snippet, self.storage, parent=self.container_snippets)
                new_w.on_copy_requested.connect(lambda code: self._on_snippet_copy(code))
                new_w.on_delete_requested.connect(lambda sid: self._delete_snippet(sid))
                new_w.on_favorite_toggled.connect(lambda sid: self._toggle_snippet_favorite(sid))
                new_w.on_edit_requested.connect(lambda sid: self._edit_snippet(sid))
                
                if index >= 0:
                    self.flow_snippets.insertWidget(index, new_w)
                else:
                    self.flow_snippets.addWidget(new_w)
                
                self._snippet_cards.append(new_w)
                new_w.show()
    
    def _add_new_snippet(self):
        """Yeni snippet ekle"""
        from .snippet_dialog import SnippetDialog
        
        dlg = SnippetDialog(self)
        if not dlg.exec():
            return
        
        data = dlg.get_data()
        snippet_id = self.storage.add_snippet(**data)
        
        # Yeni snippet'i yükle
        snippet = self.storage.get_snippet(snippet_id)
        if snippet:
            self._add_snippet_card(snippet)
    
    def _clear_all_snippets(self):
        """Tüm snippet'leri sil"""
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Warning)
        mb.setWindowTitle("Tüm Snippet'leri Sil")
        mb.setText("Tüm snippet'leri silmek istediğinize emin misiniz?")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if mb.exec() != QMessageBox.Yes:
            return
        
        # Tüm snippet'leri sil
        for snippet in self.storage.list_snippets():
            self.storage.delete_snippet(snippet["id"])
        
        # UI'ı temizle
        for w in list(self._snippet_cards):
            self.flow_snippets.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._snippet_cards.clear()
    
    # ==================== TODO LİSTE İŞLEMLERİ ====================
    
    def _load_todo_lists(self):
        """Todo listelerini yükle"""
        try:
            lists = self.storage.list_todo_lists()
            for list_data in lists:
                self._add_todo_card(list_data)
        except Exception as e:
            print(f"[ERROR] Todo listesi yükleme hatası: {e}")
    
    def _add_todo_card(self, list_data: dict):
        """Todo kart ekle"""
        from .todo_card_widget_v2 import TodoCardWidgetV2
        
        w = TodoCardWidgetV2(list_data["id"], list_data, self.storage, parent=self.container_todos)
        w.delete_requested.connect(self._delete_todo_list)
        
        layout_count = self.flow_todos.count()
        if layout_count > 0:
            insert_at = max(0, layout_count - 1)
            self.flow_todos.insertWidget(insert_at, w)
        else:
            self.flow_todos.addWidget(w)
        
        self._todo_cards.append(w)
        w.show()

    def _reload_todo_cards(self):
        """Todo kartlarını veritabanından yeniden yükle."""
        for card in list(self._todo_cards):
            try:
                self.flow_todos.removeWidget(card)
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._todo_cards.clear()
        self._load_todo_lists()

    def _prompt_new_todo_list_data(self) -> tuple[str, list[str]] | tuple[None, None]:
        """Yeni liste için isim ve başlangıç görevlerini al."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Liste")
        dialog.setModal(True)
        dialog.resize(480, 320)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        txt_name = QLineEdit()
        txt_name.setPlaceholderText("Liste adı")
        form.addRow("Liste adı:", txt_name)

        txt_tasks = QPlainTextEdit()
        txt_tasks.setPlaceholderText("Her satıra bir görev yazın")
        txt_tasks.setTabChangesFocus(True)
        txt_tasks.setMinimumHeight(180)
        form.addRow("Başlangıç görevleri:", txt_tasks)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("İptal")
        btn_ok = QPushButton("Oluştur")
        btn_ok.setDefault(True)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        if dialog.exec() != QDialog.Accepted:
            return None, None

        name = (txt_name.text() or "").strip()
        tasks = [line.strip() for line in txt_tasks.toPlainText().splitlines() if line.strip()]
        return name, tasks
    
    def _create_new_todo_list(self):
        """Yeni todo listesi oluştur"""
        name, tasks = self._prompt_new_todo_list_data()
        if not name:
            return
        
        try:
            list_id = self.storage.create_todo_list(name)
            for task in tasks or []:
                self.storage.add_todo(list_id, task)
            self._reload_todo_cards()
            if self._toast:
                self._toast.show_message("✅ Liste oluşturuldu!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Liste oluşturma hatası: {e}")
    
    def _delete_todo_list(self, list_id: int):
        """Todo listesi sil"""
        self._reload_todo_cards()
        if self._toast:
            self._toast.show_message("🗑️ Liste silindi")

    def _clear_all_todo_lists(self):
        """Tüm todo listelerini sil."""
        if not self._todo_cards:
            return

        reply = QMessageBox.question(
            self,
            "Tümünü Sil",
            "Tüm listeleri ve görevleri silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            for list_data in list(self.storage.list_todo_lists(limit=1000)):
                self.storage.delete_todo_list(int(list_data["id"]))
            self._reload_todo_cards()
            if self._toast:
                self._toast.show_message("🗑️ Tüm listeler silindi")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Listeler silinemedi: {e}")
    
    # ==================== ÇİZİM İŞLEMLERİ ====================
    
    def _load_drawings(self):
        """Çizimleri yükle"""
        try:
            # Önce mevcut kartları temizle
            print(f"[DEBUG] _load_drawings: Mevcut kart sayısı: {len(self._drawing_cards)}")
            for card in self._drawing_cards:
                self.flow_drawings.removeWidget(card)
                card.deleteLater()
            self._drawing_cards.clear()
            
            drawings = self.storage.list_drawings()
            print(f"[DEBUG] _load_drawings: Veritabanından {len(drawings)} çizim geldi")
            for drawing in drawings:
                self._add_drawing_card(drawing)
            print(f"[DEBUG] _load_drawings: Yükleme sonrası kart sayısı: {len(self._drawing_cards)}")
            
            # Layout'u zorla güncelle - birden fazla kez (UI render sonrası için)
            QTimer.singleShot(10, self._refresh_drawings_layout)
            QTimer.singleShot(100, self._refresh_drawings_layout)
            QTimer.singleShot(300, self._refresh_drawings_layout)
        except Exception as e:
            print(f"[ERROR] Çizim yükleme hatası: {e}")
    
    def _refresh_drawings_layout(self):
        """Çizim layout'unu zorla yenile"""
        try:
            if not hasattr(self, 'flow_drawings') or not hasattr(self, '_drawing_cards'):
                return
                
            # FlowLayout'u yenile
            self.flow_drawings.invalidate()
            self.flow_drawings.activate()
            
            # Container'ı güncelle
            self.container_drawings.updateGeometry()
            self.container_drawings.adjustSize()
            self.container_drawings.update()
            
            # Scroll area'yı güncelle
            self.scroll_drawings.updateGeometry()
            if self.scroll_drawings.viewport():
                self.scroll_drawings.viewport().update()
            
            # Tüm kartları göster ve güncelle
            for card in self._drawing_cards:
                card.setVisible(True)
                card.show()
                card.update()
                card.raise_()  # Kartı öne getir
            
            # Layout'u tekrar hesapla
            if self.container_drawings.rect().isValid():
                self.flow_drawings.setGeometry(self.container_drawings.rect())
            
            print(f"[DEBUG] _refresh_drawings_layout: {len(self._drawing_cards)} kart yenilendi")
        except Exception as e:
            print(f"[ERROR] Layout yenileme hatası: {e}")
    
    def _add_drawing_card(self, drawing: dict):
        """Çizim kart ekle"""
        from .drawing_card_widget import DrawingCardWidget
        
        # Aynı ID ile kart zaten var mı kontrol et
        drawing_id = drawing.get("id")
        existing = next((c for c in self._drawing_cards if c.drawing_id == drawing_id), None)
        if existing:
            # Varsa güncelle
            existing.drawing = drawing
            existing._load_thumbnail()
            print(f"[DEBUG] Çizim kartı güncellendi: ID={drawing_id}")
            return
        
        w = DrawingCardWidget(drawing, parent=self.container_drawings)
        w.edit_requested.connect(lambda did: self._edit_drawing(did))
        w.delete_requested.connect(lambda did: self._delete_drawing(did))
        
        # Layout'a ekle
        self.flow_drawings.addWidget(w)
        
        self._drawing_cards.append(w)
        w.show()
        
        # Layout'u zorla güncelle
        self.flow_drawings.invalidate()
        self.flow_drawings.activate()
        self.container_drawings.updateGeometry()
        self.container_drawings.adjustSize()
        if hasattr(self, 'scroll_drawings'):
            self.scroll_drawings.updateGeometry()
        
        print(f"[DEBUG] Yeni çizim kartı eklendi: ID={drawing_id}, Toplam kart: {len(self._drawing_cards)}")
    
    def _create_new_drawing(self):
        """Yeni çizim oluştur"""
        from .drawing_modal import DrawingModal
        
        # Boş bir çizim ID'si oluştur
        import tempfile
        import base64
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt
        
        # Boş beyaz resim oluştur
        img = QImage(800, 600, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        
        img.save(tmp_path, "PNG")
        
        with open(tmp_path, "rb") as f:
            img_bytes = f.read()
        
        import os
        os.remove(tmp_path)
        
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        
        # Veritabanına kaydet
        drawing_id = self.storage.add_drawing(img_b64, "Yeni Çizim")
        
        # Modal aç
        modal = DrawingModal(drawing_id, self.storage, self)
        result = modal.exec()
        
        if result:
            # Modal başarıyla kapatıldı (Kaydet butonuyla) - kartı ekle
            self._on_drawing_saved(drawing_id)
            self.activateWindow()
            self.raise_()
        else:
            # İptal edildi - boş çizimi sil
            try:
                self.storage.delete_drawing(drawing_id)
            except:
                pass
    
    def _on_drawing_saved(self, drawing_id: int):
        """Çizim kaydedildi - kartı ekle veya güncelle"""
        # Veritabanından güncel veriyi al
        drawing = self.storage.get_drawing_by_id(drawing_id)
        if not drawing:
            return
        
        # Kartın zaten eklenmiş olup olmadığını kontrol et
        existing_card = next((card for card in self._drawing_cards if card.drawing_id == drawing_id), None)
        
        if existing_card:
            # Varolan kartın verisini güncelle
            existing_card.drawing = drawing
            existing_card._load_thumbnail()
        else:
            # Yeni kart ekle
            self._add_drawing_card(drawing)
        
        self._toast.show_message("✅ Çizim kaydedildi!")
    
    def _on_drawing_created(self, drawing_id: int):
        """Yeni çizim oluşturuldu (eski uyumluluk için)"""
        self._on_drawing_saved(drawing_id)
    
    def _edit_drawing(self, drawing_id: int):
        """Çizim düzenle"""
        from .drawing_modal import DrawingModal
        
        modal = DrawingModal(drawing_id, self.storage, self)
        modal.saved.connect(lambda did: self._on_drawing_updated(did))
        modal.exec()
    
    def _on_drawing_updated(self, drawing_id: int):
        """Çizim güncellendi"""
        w = next((card for card in self._drawing_cards if card.drawing_id == drawing_id), None)
        if w:
            drawing = self.storage.get_drawing_by_id(drawing_id)
            if drawing:
                # Kartı güncelle
                w.drawing = drawing
                w._load_thumbnail()
                self._toast.show_message("✅ Çizim güncellendi!")
    
    def _clear_all_drawings(self):
        """Tüm çizimleri temizle"""
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Icon.Warning)
        mb.setWindowTitle("Tüm Çizimleri Sil")
        mb.setText("Tüm çizimleri silmek istediğinize emin misiniz?")
        mb.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if mb.exec() != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.storage.clear_all_drawings()
            
            for w in self._drawing_cards:
                self.flow_drawings.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
            
            self._drawing_cards.clear()
            self._toast.show_message("✅ Tüm çizimler silindi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")
    
    def _delete_drawing(self, drawing_id: int):
        """Çizim sil"""
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Icon.Question)
        mb.setWindowTitle("Çizim Sil")
        mb.setText("Bu çizimi silmek istediğinize emin misiniz?")
        mb.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if mb.exec() != QMessageBox.StandardButton.Yes:
            return
        
        self.storage.delete_drawing(drawing_id)
        
        w = next((card for card in self._drawing_cards if card.drawing_id == drawing_id), None)
        if w:
            self.flow_drawings.removeWidget(w)
            self._drawing_cards.remove(w)
            w.setParent(None)
            w.deleteLater()
            self._toast.show_message("🗑️ Çizim silindi")
