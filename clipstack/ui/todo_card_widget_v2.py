"""Todo liste kartı — ItemCard düzeni."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QMessageBox, QInputDialog,
)

from .card_common import CARD_W, CARD_H, LIST_H, format_card_date, make_type_badge, make_tool_button, apply_card_view_mode


class TodoCardWidgetV2(QWidget):
    delete_requested = Signal(int)
    LIST_H = LIST_H

    def __init__(self, list_id: int, list_data: dict, storage, parent=None):
        super().__init__(parent)
        self.list_id = list_id
        self.storage = storage
        self.list_data = dict(list_data or {})
        self._view_mode = "grid"

        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(make_type_badge("assets/icons/nav_todo.svg", "✓"))

        self.title_lbl = QLabel(self.list_data.get("name", "Liste"))
        self.title_lbl.setObjectName("ItemTitle")
        self.title_lbl.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent; border: none;")
        top.addWidget(self.title_lbl, 1)

        self.btn_more = make_tool_button("MoreButton", "assets/icons/more_vert.svg", "Diğer", "⋮")
        self.btn_more.clicked.connect(self._more_menu)
        top.addWidget(self.btn_more)
        layout.addLayout(top)

        self.preview = QLabel()
        self.preview.setObjectName("ItemPreview")
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-size: 11px;")
        layout.addWidget(self.preview, 1)

        bottom = QHBoxLayout()
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("MetaLabel")
        self.lbl_meta.setStyleSheet("font-size: 10px; color: #94a3b8; background: transparent; border: none;")
        bottom.addWidget(self.lbl_meta, 1)

        self.btn_copy = make_tool_button("CopyButton", "assets/icons/expand.svg", "Aç")
        self.btn_copy.clicked.connect(self._expand_list)
        bottom.addWidget(self.btn_copy)
        layout.addLayout(bottom)

        self._load_items()
        try:
            mode = getattr(getattr(self.window(), "chip_bar", None), "view_mode", "grid")
            self.set_view_mode(mode)
        except Exception:
            pass

    def set_view_mode(self, mode: str):
        apply_card_view_mode(self, mode, getattr(self, "preview", None))
        self.updateGeometry()

    def _load_items(self):
        try:
            items = self.storage.get_todos_by_list(self.list_id) if hasattr(self.storage, "get_todos_by_list") else []
            if not items and hasattr(self.storage, "list_todos_by_list"):
                items = self.storage.list_todos_by_list(self.list_id)
        except Exception:
            items = []
        if not items:
            try:
                # Fallback: list_data içindeki todos
                items = self.list_data.get("todos") or self.list_data.get("items") or []
            except Exception:
                items = []

        lines = []
        done = 0
        for it in items[:4]:
            try:
                text = it.get("content") or it.get("text") or it.get("title") or str(it)
                completed = bool(it.get("completed") or it.get("done"))
            except Exception:
                text, completed = str(it), False
            if completed:
                done += 1
                lines.append(f"✓ {text}")
            else:
                lines.append(f"○ {text}")
        total = len(items)
        self.preview.setText("\n".join(lines) if lines else "Boş liste")
        created = format_card_date(str(self.list_data.get("created_at", "") or ""))
        self.lbl_meta.setText(f"{created} · {done}/{total}" if created else f"{done}/{total} görev")

    def _expand_list(self):
        try:
            from .todo_modal import TodoModal
            dlg = TodoModal(self.list_id, self.storage, self)
            dlg.exec()
            self._load_items()
        except Exception as e:
            QMessageBox.information(self, "Liste", f"Açılamadı: {e}")

    def _more_menu(self):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("Aç", self._expand_list)
        menu.addAction("Yeniden adlandır", self._rename_list)
        menu.addSeparator()
        menu.addAction("Sil", self._delete_list)
        menu.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    def _rename_list(self):
        name, ok = QInputDialog.getText(self, "Liste", "Liste adı:", text=self.list_data.get("name", ""))
        if ok and name.strip():
            try:
                if hasattr(self.storage, "update_todo_list_name"):
                    self.storage.update_todo_list_name(self.list_id, name.strip())
                self.list_data["name"] = name.strip()
                self.title_lbl.setText(name.strip())
            except Exception:
                pass

    def _delete_list(self):
        mb = QMessageBox(self)
        mb.setWindowTitle("Liste")
        mb.setText("Bu listeyi silmek ister misiniz?")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        if mb.exec() == QMessageBox.Yes:
            self.delete_requested.emit(self.list_id)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, QToolButton):
                self._expand_list()
        super().mousePressEvent(event)
