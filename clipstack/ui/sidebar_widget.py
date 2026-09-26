from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QPushButton, QFrame, QScrollArea, QSizePolicy,
)

from .. import __app_name__, __version__
from ..utils import svg_icon, resource_path


NAV_ITEMS = [
    ("all", "Tümü", "assets/icons/nav_all.svg"),
    ("text", "Metin", "assets/icons/nav_text.svg"),
    ("image", "Resim", "assets/icons/nav_image.svg"),
    ("files", "Dosyalar", "assets/icons/nav_file.svg"),
    ("fav", "Favoriler", "assets/icons/star.svg"),
    ("notes", "Notlar", "assets/icons/nav_note.svg"),
    ("reminders", "Hatırlatmalar", "assets/icons/nav_reminder.svg"),
    ("snippets", "Snippet", "assets/icons/nav_snippet.svg"),
    ("todos", "Listeler", "assets/icons/nav_todo.svg"),
    ("drawings", "Çizimler", "assets/icons/nav_drawing.svg"),
    ("video", "Video", "assets/icons/video_camera.svg"),
]

class SidebarNavButton(QPushButton):
    def __init__(self, key: str, label: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.key = key
        self._label = label
        self.setObjectName("SidebarNavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 8, 4)
        lay.setSpacing(10)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(20, 20)
        self.icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        try:
            ic = svg_icon(icon_path)
            self.icon_lbl.setPixmap(ic.pixmap(QSize(18, 18)))
        except Exception:
            self.icon_lbl.setText("•")
        lay.addWidget(self.icon_lbl)

        self.text_lbl = QLabel(label)
        self.text_lbl.setObjectName("SidebarNavText")
        self.text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.text_lbl, 1)

        self.count_lbl = QLabel("0")
        self.count_lbl.setObjectName("SidebarCountBadge")
        self.count_lbl.setAlignment(Qt.AlignCenter)
        self.count_lbl.setMinimumWidth(28)
        self.count_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.count_lbl)

        # QPushButton kendi metnini kullanmasın
        self.setText("")
        self.setFlat(True)

    def set_count(self, n: int):
        self.count_lbl.setText(str(n) if n < 1000 else "999+")

    def set_collapsed(self, collapsed: bool):
        self.text_lbl.setVisible(not collapsed)
        self.count_lbl.setVisible(not collapsed)
        self.setToolTip(self._label if collapsed else "")


class AppSidebar(QWidget):
    """Açılır/kapanır sol menü."""

    nav_changed = Signal(str)
    settings_clicked = Signal()
    collapse_toggled = Signal(bool)

    EXPANDED_W = 228
    COLLAPSED_W = 64

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppSidebar")
        self._collapsed = False
        self._buttons: Dict[str, SidebarNavButton] = {}
        self._current = "all"

        self.setFixedWidth(self.EXPANDED_W)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(6)

        # Üst: logo + isim + collapse
        header = QHBoxLayout()
        header.setSpacing(8)
        self.logo = QLabel()
        self.logo.setFixedSize(28, 28)
        try:
            p = resource_path("assets/icons/logo.png")
            if p and p.exists():
                from PySide6.QtGui import QPixmap
                pm = QPixmap(str(p)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo.setPixmap(pm)
            else:
                self.logo.setPixmap(svg_icon("assets/icons/clipboard.svg").pixmap(QSize(24, 24)))
        except Exception:
            self.logo.setText("TC")
        header.addWidget(self.logo)

        self.app_title = QLabel(__app_name__)
        self.app_title.setObjectName("SidebarAppTitle")
        f = QFont()
        f.setBold(True)
        f.setPointSize(12)
        self.app_title.setFont(f)
        header.addWidget(self.app_title, 1)

        self.btn_collapse = QToolButton()
        self.btn_collapse.setObjectName("SidebarCollapseBtn")
        self.btn_collapse.setAutoRaise(True)
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        try:
            self.btn_collapse.setIcon(svg_icon("assets/icons/chevron_left.svg"))
        except Exception:
            self.btn_collapse.setText("«")
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        header.addWidget(self.btn_collapse)
        root.addLayout(header)

        # Nav scroll
        scroll = QScrollArea()
        scroll.setObjectName("SidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        nav_host = QWidget()
        self.nav_layout = QVBoxLayout(nav_host)
        self.nav_layout.setContentsMargins(0, 6, 0, 6)
        self.nav_layout.setSpacing(2)

        for key, label, icon in NAV_ITEMS:
            btn = SidebarNavButton(key, label, icon)
            btn.clicked.connect(lambda checked=False, k=key: self._on_nav(k))
            self.nav_layout.addWidget(btn)
            self._buttons[key] = btn

        self.nav_layout.addStretch(1)
        scroll.setWidget(nav_host)
        root.addWidget(scroll, 1)

        # Ayarlar
        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("SidebarSettingsBtn")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setMinimumHeight(36)
        settings_lay = QHBoxLayout(self.btn_settings)
        settings_lay.setContentsMargins(10, 4, 8, 4)
        settings_lay.setSpacing(10)
        self.settings_icon = QLabel()
        self.settings_icon.setFixedSize(20, 20)
        self.settings_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        try:
            self.settings_icon.setPixmap(svg_icon("assets/icons/gear.svg").pixmap(QSize(18, 18)))
        except Exception:
            pass
        settings_lay.addWidget(self.settings_icon)
        self.settings_text = QLabel("Ayarlar")
        self.settings_text.setAttribute(Qt.WA_TransparentForMouseEvents)
        settings_lay.addWidget(self.settings_text, 1)
        self.btn_settings.setText("")
        self.btn_settings.setFlat(True)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        root.addWidget(self.btn_settings)

        # Sürüm
        self.version_lbl = QLabel(f"{__app_name__}  v{__version__}")
        self.version_lbl.setObjectName("SidebarVersion")
        self.version_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self.version_lbl)

        self._buttons["all"].setChecked(True)

    def _on_nav(self, key: str):
        self.set_current(key)
        self.nav_changed.emit(key)

    def set_current(self, key: str):
        self._current = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def set_counts(self, counts: Dict[str, int]):
        for k, btn in self._buttons.items():
            btn.set_count(int(counts.get(k, 0)))

    def toggle_collapse(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.setFixedWidth(self.COLLAPSED_W if collapsed else self.EXPANDED_W)
        self.app_title.setVisible(not collapsed)
        self.version_lbl.setVisible(not collapsed)
        self.settings_text.setVisible(not collapsed)
        for btn in self._buttons.values():
            btn.set_collapsed(collapsed)
        try:
            icon = "assets/icons/chevron_right.svg" if collapsed else "assets/icons/chevron_left.svg"
            self.btn_collapse.setIcon(svg_icon(icon))
        except Exception:
            pass
        self.collapse_toggled.emit(collapsed)
        # Ayarlara yaz (varsa)
        try:
            win = self.window()
            settings = getattr(win, "settings", None)
            if settings is not None:
                settings.set("sidebar_collapsed", collapsed)
                settings.save()
        except Exception:
            pass

    @property
    def current_key(self) -> str:
        return self._current
