"""
Todo List Manager - Tüm todo listelerini yönet
Her liste ayrı bir kart olarak gösterilir
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from .todo_card_widget import TodoCardWidget
from ..ui.flow_layout import FlowLayout


class TodoListManager(QWidget):
    """Todo listesi yöneticisi - flow layout ile kartları gösterir"""
    
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.todo_cards = []
        
        self._init_ui()
        self._load_all_lists()
    
    def _init_ui(self):
        """UI oluştur"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Üst bar
        top_bar = QHBoxLayout()
        
        self.lbl_title = QLabel("📋 Yapılacaklar Listeleri")
        font = self.lbl_title.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lbl_title.setFont(font)
        top_bar.addWidget(self.lbl_title)
        
        top_bar.addStretch()
        
        # Yeni liste butonu
        self.btn_new_list = QPushButton("➕ Yeni Liste")
        self.btn_new_list.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_new_list.clicked.connect(self._create_new_list)
        self.btn_new_list.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #229954;
            }
        """)
        top_bar.addWidget(self.btn_new_list)
        
        # Tümünü Sil butonu
        self.btn_clear_all = QPushButton("🗑️ Tümünü Sil")
        self.btn_clear_all.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear_all.clicked.connect(self._clear_all_lists)
        self.btn_clear_all.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        top_bar.addWidget(self.btn_clear_all)
        
        layout.addLayout(top_bar)
        
        # Scroll area - kartlar için
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        self.flow_layout = FlowLayout(scroll_widget)
        self.flow_layout.setSpacing(15)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)
        
        # Alt bar: İstatistikler
        self.lbl_stats = QLabel("0 liste, 0 görev")
        self.lbl_stats.setStyleSheet("color: #7f8c8d; font-size: 10pt;")
        layout.addWidget(self.lbl_stats)
    
    def _load_all_lists(self):
        """Tüm listeleri yükle"""
        try:
            # Eski kartları temizle
            for card in self.todo_cards:
                self.flow_layout.removeWidget(card)
                card.deleteLater()
            self.todo_cards.clear()
            
            # Önce tüm todo listelerini getir
            todo_lists = self.storage.list_todo_lists(limit=100)
            
            if not todo_lists:
                # Eğer hiç liste yoksa varsayılan listeyi kontrol et
                self._update_stats()
                return
            
            # Her liste için kartları oluştur
            for todo_list in todo_lists:
                list_id = todo_list["id"]
                list_name = todo_list.get("name", "Liste")
                
                # Bu listeye ait todoları getir
                list_todos = self.storage.get_todos_by_list(list_id)
                
                if not list_todos:
                    # Boş liste için de kart oluştur
                    list_todos = []
                
                # Kart oluştur
                card = TodoCardWidget(self.storage, list_todos, self, list_name=list_name, list_id=list_id)
                card.card_deleted.connect(self._on_card_deleted)
                card.todos_changed.connect(self._update_stats)
                
                self.flow_layout.addWidget(card)
                self.todo_cards.append(card)
                
        except Exception as e:
            print(f"[TODO] Liste yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"[TODO] Kart oluşturma hatası: {e}")
        
        self._update_stats()
    
    def _create_new_list(self):
        """Yeni boş liste oluştur"""
        try:
            from datetime import datetime
            
            # Önce liste oluştur
            list_id = self.storage.create_todo_list("Yeni Liste")
            
            # İlk dummy todo ekle
            todo_id = self.storage.add_todo(list_id, "Yeni görev...")
            
            new_todo = {
                "id": todo_id,
                "list_id": list_id,
                "content": "Yeni görev...",
                "completed": False,
                "created_at": datetime.now().isoformat()
            }
            
            # Yeni kart oluştur
            card = TodoCardWidget(self.storage, [new_todo], self)
            card.card_deleted.connect(self._on_card_deleted)
            card.todos_changed.connect(self._update_stats)
            
            # En üste ekle
            self.flow_layout.insertWidget(0, card)
            self.todo_cards.insert(0, card)
            
            self._update_stats()
        except Exception as e:
            print(f"[TODO] Yeni liste oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_all_lists(self):
        """Tüm listeleri sil"""
        from PySide6.QtWidgets import QMessageBox
        
        if not self.todo_cards:
            return
        
        reply = QMessageBox.question(
            self,
            "Tümünü Sil",
            f"Tüm {len(self.todo_cards)} listeyi ve içlerindeki görevleri silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Tüm todo'ları veritabanından sil
            try:
                all_todos = self.storage.list_todos()
                for todo in all_todos:
                    self.storage.delete_todo(todo["id"])
            except Exception as e:
                print(f"[TODO] Silme hatası: {e}")
            
            # UI'dan kaldır
            for card in self.todo_cards:
                self.flow_layout.removeWidget(card)
                card.deleteLater()
            self.todo_cards.clear()
            
            self._update_stats()
    
    def _on_card_deleted(self, list_id: int):
        """Kart silindi"""
        # UI'dan kaldır
        for card in self.todo_cards:
            if card.list_id == list_id:
                self.flow_layout.removeWidget(card)
                self.todo_cards.remove(card)
                card.deleteLater()
                break
        
        self._update_stats()
    
    def _update_stats(self):
        """İstatistikleri güncelle"""
        total_lists = len(self.todo_cards)
        total_todos = sum(len(card.list_todos) for card in self.todo_cards)
        total_completed = sum(
            sum(1 for todo in card.list_todos if todo.get("completed"))
            for card in self.todo_cards
        )
        
        if total_completed > 0:
            self.lbl_stats.setText(f"{total_lists} liste, {total_todos} görev ({total_completed} tamamlandı)")
        else:
            self.lbl_stats.setText(f"{total_lists} liste, {total_todos} görev")
    
    def refresh(self):
        """Dışarıdan yenileme"""
        self._load_all_lists()
