from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QMessageBox, QFrame,
)


class BulkDeleteDialog(QDialog):
    """Ayarlar üzerinden toplu silme — checkbox ile hedef seçimi."""

    TARGETS = [
        ("clips", "Pano geçmişi (tüm içerikler)"),
        ("notes", "Notlar"),
        ("reminders", "Hatırlatmalar"),
        ("snippets", "Snippet'ler"),
        ("todos", "Listeler / görevler"),
        ("drawings", "Çizimler"),
    ]

    def __init__(self, parent=None, on_delete: Optional[Callable[[List[str]], None]] = None):
        super().__init__(parent)
        self.setWindowTitle("Toplu silme")
        self.setMinimumWidth(420)
        self._on_delete = on_delete
        self._checks: Dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        info = QLabel(
            "Silmek istediğiniz içerik türlerini seçin. "
            "Onayladıktan sonra işlem geri alınamaz."
        )
        info.setWordWrap(True)
        info.setObjectName("BulkDeleteInfo")
        lay.addWidget(info)

        box = QFrame()
        box.setObjectName("BulkDeleteBox")
        box_lay = QVBoxLayout(box)
        box_lay.setSpacing(8)
        for key, label in self.TARGETS:
            cb = QCheckBox(label)
            cb.setChecked(False)
            self._checks[key] = cb
            box_lay.addWidget(cb)
        lay.addWidget(box)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_cancel)
        self.btn_delete = QPushButton("Sil")
        self.btn_delete.setProperty("class", "accent")
        self.btn_delete.clicked.connect(self._confirm_and_delete)
        btns.addWidget(self.btn_delete)
        lay.addLayout(btns)

    def selected_targets(self) -> List[str]:
        return [k for k, cb in self._checks.items() if cb.isChecked()]

    def _confirm_and_delete(self):
        targets = self.selected_targets()
        if not targets:
            QMessageBox.information(self, "Toplu silme", "En az bir içerik türü seçin.")
            return
        labels = [lbl for k, lbl in self.TARGETS if k in targets]
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Warning)
        mb.setWindowTitle("Emin misiniz?")
        mb.setText(
            "Aşağıdaki içerikler kalıcı olarak silinecek:\n\n• "
            + "\n• ".join(labels)
            + "\n\nBu işlem geri alınamaz. Devam edilsin mi?"
        )
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        if mb.exec() != QMessageBox.Yes:
            return
        if callable(self._on_delete):
            self._on_delete(targets)
        self.accept()
