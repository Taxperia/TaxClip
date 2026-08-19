"""İçerik filtre çubuğu — Tümü / En Yeni / Tür / Etiket / Uygulama + görünüm."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QMenu, QFrame, QToolButton,
)

from ..utils import svg_icon


class FilterChipBar(QFrame):
    filter_changed = Signal()
    view_mode_changed = Signal(str)  # "grid" | "list"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterChipBar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.sort_mode = "newest"
        self.type_filter = "all"
        self.tag_filter = ""
        self.app_filter = ""
        self.view_mode = "grid"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(8)

        self.btn_all = self._chip("Tümü", "assets/icons/filter_all.svg", checkable=True, checked=True)
        self.btn_all.clicked.connect(lambda: self._set_type("all"))
        lay.addWidget(self.btn_all)

        self.btn_sort = self._chip("En Yeni", "assets/icons/sort.svg")
        self.btn_sort.clicked.connect(self._open_sort_menu)
        lay.addWidget(self.btn_sort)

        self.btn_type = self._chip("Tür", "assets/icons/filter_type.svg")
        self.btn_type.clicked.connect(self._open_type_menu)
        lay.addWidget(self.btn_type)

        self.btn_tag = self._chip("Etiket", "assets/icons/tag.svg")
        self.btn_tag.clicked.connect(self._open_tag_menu)
        lay.addWidget(self.btn_tag)

        self.btn_app = self._chip("Uygulama", "assets/icons/app.svg")
        self.btn_app.clicked.connect(self._open_app_menu)
        lay.addWidget(self.btn_app)

        lay.addStretch(1)

        self.btn_grid = QToolButton()
        self.btn_grid.setObjectName("ViewModeBtn")
        self.btn_grid.setIcon(svg_icon("assets/icons/view_grid.svg"))
        self.btn_grid.setIconSize(QSize(16, 16))
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(True)
        self.btn_grid.setToolTip("Izgara görünümü")
        self.btn_grid.setCursor(Qt.PointingHandCursor)
        self.btn_grid.clicked.connect(lambda: self._set_view("grid"))
        lay.addWidget(self.btn_grid)

        self.btn_list = QToolButton()
        self.btn_list.setObjectName("ViewModeBtn")
        self.btn_list.setIcon(svg_icon("assets/icons/view_list.svg"))
        self.btn_list.setIconSize(QSize(16, 16))
        self.btn_list.setCheckable(True)
        self.btn_list.setToolTip("Liste görünümü")
        self.btn_list.setCursor(Qt.PointingHandCursor)
        self.btn_list.clicked.connect(lambda: self._set_view("list"))
        lay.addWidget(self.btn_list)

        self._apps: list[str] = []
        self._tags: list[str] = []

    def _chip(self, text: str, icon_path: str = "", checkable: bool = False, checked: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("FilterChip")
        b.setCheckable(checkable)
        b.setChecked(checked)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(30)
        b.setIconSize(QSize(14, 14))
        if icon_path:
            try:
                b.setIcon(svg_icon(icon_path))
            except Exception:
                pass
        return b

    def set_available_apps(self, apps: list[str]):
        self._apps = sorted({a for a in apps if a})

    def set_available_tags(self, tags: list[str]):
        self._tags = sorted({t for t in tags if t})

    def _set_type(self, key: str):
        self.type_filter = key
        self.btn_all.setChecked(key == "all")
        labels = {
            "all": "Tür",
            "text": "Metin",
            "image": "Resim",
            "file": "Dosya",
            "code": "Kod",
        }
        self.btn_type.setText(labels.get(key, "Tür") if key != "all" else "Tür")
        self.filter_changed.emit()

    def _set_view(self, mode: str):
        self.view_mode = mode
        self.btn_grid.setChecked(mode == "grid")
        self.btn_list.setChecked(mode == "list")
        self.view_mode_changed.emit(mode)

    def _open_sort_menu(self):
        menu = QMenu(self)
        for key, label in (
            ("newest", "En Yeni"),
            ("oldest", "En Eski"),
            ("used", "En Çok Kullanılan"),
        ):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.sort_mode == key)
            act.triggered.connect(lambda checked=False, k=key, l=label: self._pick_sort(k, l))
        menu.exec(self.btn_sort.mapToGlobal(self.btn_sort.rect().bottomLeft()))

    def _pick_sort(self, key: str, label: str):
        self.sort_mode = key
        self.btn_sort.setText(label)
        self.filter_changed.emit()

    def _open_type_menu(self):
        menu = QMenu(self)
        for key, label in (
            ("all", "Tümü"),
            ("text", "Metin"),
            ("image", "Resim"),
            ("file", "Dosya"),
            ("code", "Kod"),
        ):
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, k=key: self._set_type(k))
        menu.exec(self.btn_type.mapToGlobal(self.btn_type.rect().bottomLeft()))

    def _open_tag_menu(self):
        menu = QMenu(self)
        menu.addAction("Tüm etiketler", lambda: self._pick_tag(""))
        if not self._tags:
            menu.addAction("(etiket yok)").setEnabled(False)
        for t in self._tags[:30]:
            menu.addAction(t, lambda checked=False, x=t: self._pick_tag(x))
        menu.exec(self.btn_tag.mapToGlobal(self.btn_tag.rect().bottomLeft()))

    def _pick_tag(self, tag: str):
        self.tag_filter = tag
        self.btn_tag.setText((tag[:14] + "…") if len(tag) > 14 else (tag or "Etiket"))
        self.filter_changed.emit()

    def _open_app_menu(self):
        menu = QMenu(self)
        menu.addAction("Tüm uygulamalar", lambda: self._pick_app(""))
        if not self._apps:
            menu.addAction("(uygulama yok)").setEnabled(False)
        for a in self._apps[:30]:
            menu.addAction(a, lambda checked=False, x=a: self._pick_app(x))
        menu.exec(self.btn_app.mapToGlobal(self.btn_app.rect().bottomLeft()))

    def _pick_app(self, app: str):
        self.app_filter = app
        short = app.replace(".exe", "") if app else "Uygulama"
        self.btn_app.setText((short[:14] + "…") if len(short) > 14 else short)
        self.filter_changed.emit()
