"""
Lightshot-benzeri Ekran Alıntısı Aracı
- Ekran bölgesi seçimi
- Çizim araçları (kalem, dikdörtgen, ok, daire, metin)
- Kopyalama ve kaydetme
"""
import sys
import math
from enum import Enum, auto
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QApplication, QToolBar, QPushButton, QColorDialog,
    QFileDialog, QToolButton, QHBoxLayout, QVBoxLayout, QLabel,
    QSpinBox, QMenu, QWidgetAction, QSlider, QInputDialog,
    QLineEdit
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QSize, Signal, QTimer, QPointF, QRectF
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QCursor, QFont,
    QGuiApplication, QScreen, QPainterPath, QKeySequence,
    QShortcut, QMouseEvent, QPaintEvent, QKeyEvent,
    QPolygonF
)

from ..storage import ClipItemType
from ..utils import copy_to_clipboard_safely


class DrawingTool(Enum):
    NONE = auto()
    PEN = auto()
    LINE = auto()
    ARROW = auto()
    RECT = auto()
    FILLED_RECT = auto()
    ELLIPSE = auto()
    TEXT = auto()
    HIGHLIGHTER = auto()
    BLUR = auto()
    ERASER = auto()


class DrawingAction:
    """Tek bir çizim işlemi"""
    def __init__(self, tool: DrawingTool, color: QColor, width: int):
        self.tool = tool
        self.color = color
        self.width = width
        self.points: List[QPointF] = []
        self.start_point: Optional[QPointF] = None
        self.end_point: Optional[QPointF] = None
        self.text: str = ""
        self.font_size: int = 16


class ScreenshotOverlay(QWidget):
    """
    Tam ekran overlay - bölge seçimi ve çizim
    Lightshot benzeri deneyim
    """
    screenshot_taken = Signal(bytes)   # PNG bytes
    screenshot_saved = Signal(str)     # dosya yolu
    screenshot_cancelled = Signal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        
        # Pencere ayarları - tam ekran, şeffaf, her şeyin üstünde
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Durumlar
        self._phase = "selecting"  # selecting, drawing
        self._is_selecting = False
        self._selection_start = QPoint()
        self._selection_end = QPoint()
        self._selection_rect = QRect()
        self._has_selection = False
        
        # Kapsamlı ekran görüntüsü (tüm monitörler)
        self._full_pixmap: Optional[QPixmap] = None
        self._screen_geometry = QRect()
        
        # Çizim
        self._current_tool = DrawingTool.PEN
        self._draw_color = QColor("#FF3333")
        self._draw_width = 3
        self._drawing = False
        self._current_action: Optional[DrawingAction] = None
        self._actions: List[DrawingAction] = []
        self._draw_pixmap: Optional[QPixmap] = None
        
        # Toolbar
        self._toolbar: Optional[QWidget] = None
        
        # Text input alanı
        self._text_editing = False
        self._text_pos: Optional[QPointF] = None
        
        # Kısayollar
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Klavye kısayolları"""
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._cancel)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_to_clipboard)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_to_file)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._copy_to_clipboard)

    def start(self):
        """Ekran alıntısını başlat"""
        # Tüm ekranları birleştir
        self._capture_all_screens()
        
        if not self._full_pixmap:
            self._cancel()
            return
        
        # Geometry ayarla
        self.setGeometry(self._screen_geometry)
        
        # Reset state
        self._phase = "selecting"
        self._has_selection = False
        self._selection_rect = QRect()
        self._actions.clear()
        self._draw_pixmap = None
        
        if self._toolbar:
            self._toolbar.hide()
            self._toolbar.deleteLater()
            self._toolbar = None
        
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def _capture_all_screens(self):
        """Tüm ekranlardan tek bir büyük pixmap oluştur"""
        screens = QGuiApplication.screens()
        if not screens:
            return
        
        # Birleşik bounding rect
        combined = QRect()
        for screen in screens:
            combined = combined.united(screen.geometry())
        
        self._screen_geometry = combined
        
        # Büyük boş pixmap
        self._full_pixmap = QPixmap(combined.size())
        self._full_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self._full_pixmap)
        for screen in screens:
            geo = screen.geometry()
            grab = screen.grabWindow(0)
            # Offset: ekranın pozisyonu - combined'ın sol üst köşesi
            painter.drawPixmap(
                geo.x() - combined.x(),
                geo.y() - combined.y(),
                grab
            )
        painter.end()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event: QPaintEvent):
        if not self._full_pixmap:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1) Arka plan: maskelenmiş ekran görüntüsü
        painter.drawPixmap(0, 0, self._full_pixmap)
        
        # 2) Yarı saydam karartma (seçim dışı alan)
        overlay = QColor(0, 0, 0, 120)
        
        if self._has_selection or self._is_selecting:
            rect = self._get_selection_rect()
            
            # Seçim dışı alanı karart
            region = self.rect()
            
            # Üst
            painter.fillRect(QRect(0, 0, region.width(), rect.top()), overlay)
            # Alt
            painter.fillRect(QRect(0, rect.bottom() + 1, region.width(), region.height() - rect.bottom() - 1), overlay)
            # Sol
            painter.fillRect(QRect(0, rect.top(), rect.left(), rect.height()), overlay)
            # Sağ
            painter.fillRect(QRect(rect.right() + 1, rect.top(), region.width() - rect.right() - 1, rect.height()), overlay)
            
            # 3) Seçim çerçevesi
            pen = QPen(QColor("#00AAFF"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            
            # Boyut bilgisi
            self._draw_size_label(painter, rect)
            
            # 4) Seçilmiş alan üzerine çizimler
            if self._has_selection and self._draw_pixmap:
                painter.drawPixmap(rect.topLeft(), self._draw_pixmap)
        else:
            # Seçim yok - tüm ekranı karart
            painter.fillRect(self.rect(), overlay)
            
            # İpucu yazısı
            self._draw_hint(painter)
        
        # 5) Mevcut çizim işlemi (canlı önizleme)
        if self._current_action and self._drawing and self._has_selection:
            self._render_action_live(painter, self._current_action)
        
        painter.end()

    def _draw_hint(self, painter: QPainter):
        """Kullanıcıya seçim ipucu göster"""
        text = "Ekran alıntısı almak için bir bölge seçin  •  ESC: İptal"
        font = QFont("Segoe UI", 14)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))
        
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        
        cx = self.width() // 2
        cy = self.height() // 2
        
        # Arka plan
        bg_rect = QRect(cx - tw // 2 - 20, cy - th // 2 - 10, tw + 40, th + 20)
        painter.setBrush(QColor(0, 0, 0, 180))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 8, 8)
        
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_size_label(self, painter: QPainter, rect: QRect):
        """Seçim boyutu etiketi"""
        text = f"{rect.width()} × {rect.height()}"
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 12
        th = fm.height() + 6
        
        lx = rect.left()
        ly = rect.top() - th - 4
        if ly < 0:
            ly = rect.bottom() + 4
        
        painter.setBrush(QColor(0, 170, 255, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(lx, ly, tw, th), 3, 3)
        
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRect(lx, ly, tw, th), Qt.AlignmentFlag.AlignCenter, text)

    # --------------------------------------------------------- mouse events
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            return
        
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        pos = event.position().toPoint()
        
        if self._phase == "selecting":
            self._is_selecting = True
            self._selection_start = pos
            self._selection_end = pos
            self._has_selection = False
        
        elif self._phase == "drawing":
            # Text aracı özel davranış
            if self._current_tool == DrawingTool.TEXT:
                self._start_text_input(pos)
                return
            
            # Seçim alanı içinde mi?
            sel = self._selection_rect
            if sel.contains(pos):
                self._drawing = True
                local = QPointF(pos.x() - sel.x(), pos.y() - sel.y())
                
                action = DrawingAction(self._current_tool, QColor(self._draw_color), self._draw_width)
                action.start_point = local
                
                if self._current_tool in (DrawingTool.PEN, DrawingTool.HIGHLIGHTER, DrawingTool.ERASER):
                    action.points.append(local)
                
                self._current_action = action
        
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        
        if self._phase == "selecting" and self._is_selecting:
            self._selection_end = pos
            self.update()
        
        elif self._phase == "drawing" and self._drawing and self._current_action:
            sel = self._selection_rect
            # Seçim alanı içinde kısıtla
            cx = max(sel.x(), min(pos.x(), sel.right()))
            cy = max(sel.y(), min(pos.y(), sel.bottom()))
            local = QPointF(cx - sel.x(), cy - sel.y())
            
            self._current_action.end_point = local
            
            if self._current_action.tool in (DrawingTool.PEN, DrawingTool.HIGHLIGHTER, DrawingTool.ERASER):
                self._current_action.points.append(local)
            
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        if self._phase == "selecting" and self._is_selecting:
            self._is_selecting = False
            self._selection_end = event.position().toPoint()
            rect = self._get_selection_rect()
            
            if rect.width() > 5 and rect.height() > 5:
                self._has_selection = True
                self._selection_rect = rect
                self._phase = "drawing"
                self.setCursor(Qt.CursorShape.ArrowCursor)
                
                # Çizim pixmap'i oluştur (seçim boyutunda, transparan)
                self._draw_pixmap = QPixmap(rect.size())
                self._draw_pixmap.fill(Qt.GlobalColor.transparent)
                
                # Toolbar göster
                QTimer.singleShot(50, self._show_toolbar)
            else:
                self._has_selection = False
            
            self.update()
        
        elif self._phase == "drawing" and self._drawing:
            self._drawing = False
            if self._current_action:
                sel = self._selection_rect
                pos = event.position().toPoint()
                cx = max(sel.x(), min(pos.x(), sel.right()))
                cy = max(sel.y(), min(pos.y(), sel.bottom()))
                self._current_action.end_point = QPointF(cx - sel.x(), cy - sel.y())
                
                # Draw pixmap'e işle
                self._commit_action(self._current_action)
                self._actions.append(self._current_action)
                self._current_action = None
            self.update()

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    # --------------------------------------------------------- selection helpers
    def _get_selection_rect(self) -> QRect:
        """Normalize edilmiş seçim dikdörtgeni"""
        return QRect(self._selection_start, self._selection_end).normalized()

    # --------------------------------------------------------- toolbar
    def _show_toolbar(self):
        """Seçim altında araç çubuğu göster"""
        if self._toolbar:
            self._toolbar.hide()
            self._toolbar.deleteLater()
        
        self._toolbar = QWidget(self)
        self._toolbar.setObjectName("screenshotToolbar")
        self._toolbar.setStyleSheet("""
            #screenshotToolbar {
                background: rgba(16, 16, 22, 0.96);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
            #screenshotToolbar QPushButton,
            #screenshotToolbar QToolButton {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.7);
                font-size: 15px;
                padding: 0px;
                padding-top: 0px;
                padding-bottom: 3px;
                margin: 0px;
                border-radius: 6px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            #screenshotToolbar QPushButton:hover,
            #screenshotToolbar QToolButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            #screenshotToolbar QPushButton:checked,
            #screenshotToolbar QToolButton:checked {
                background: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
            #screenshotToolbar QPushButton[accessibleName="action-btn"] {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.85);
                font-weight: 600;
                font-size: 12px;
                padding: 5px 14px;
                border-radius: 6px;
                min-width: 55px;
                max-width: 90px;
            }
            #screenshotToolbar QPushButton[accessibleName="action-btn"]:hover {
                background: rgba(255, 255, 255, 0.18);
                color: #ffffff;
            }
            #screenshotToolbar QPushButton[accessibleName="cancel-btn"] {
                background: transparent;
                color: rgba(255, 255, 255, 0.4);
            }
            #screenshotToolbar QPushButton[accessibleName="cancel-btn"]:hover {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.8);
            }
            #screenshotToolbar QPushButton[accessibleName="width-btn"] {
                font-size: 11px;
                color: rgba(255, 255, 255, 0.6);
                min-width: 38px;
                max-width: 38px;
            }
        """)
        
        layout = QHBoxLayout(self._toolbar)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)
        
        # Çizim araçları (font-based icons)
        tools = [
            (DrawingTool.PEN, "\u2710", "Kalem"),
            (DrawingTool.HIGHLIGHTER, "\u2591", "Fosforlu Kalem"),
            (DrawingTool.LINE, "\u2215", "Çizgi"),
            (DrawingTool.ARROW, "\u279D", "Ok"),
            (DrawingTool.RECT, "\u25A1", "Dikdörtgen"),
            (DrawingTool.FILLED_RECT, "\u25A0", "Dolu Dikdörtgen"),
            (DrawingTool.ELLIPSE, "\u25CB", "Daire/Elips"),
            (DrawingTool.TEXT, "T", "Metin"),
            (DrawingTool.BLUR, "\u2593", "Bulanıklaştır"),
        ]
        
        self._tool_buttons = {}
        for tool, icon, tooltip in tools:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(32, 32)
            if tool == self._current_tool:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tool: self._select_tool(t))
            layout.addWidget(btn)
            self._tool_buttons[tool] = btn
        
        # Ayırıcı
        sep = QWidget()
        sep.setFixedSize(1, 24)
        sep.setStyleSheet("background: rgba(255,255,255,0.1); border: none;")
        layout.addWidget(sep)
        
        # Renk butonu
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(32, 32)
        self._color_btn.setToolTip("Renk Seç")
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self._color_btn)
        
        # Kalınlık
        self._width_btn = QPushButton(f"{self._draw_width}px")
        self._width_btn.setAccessibleName("width-btn")
        self._width_btn.setFixedSize(38, 32)
        self._width_btn.setToolTip("Kalınlık")
        self._width_btn.clicked.connect(self._pick_width)
        layout.addWidget(self._width_btn)
        
        # Ayırıcı
        sep2 = QWidget()
        sep2.setFixedSize(1, 24)
        sep2.setStyleSheet("background: rgba(255,255,255,0.1); border: none;")
        layout.addWidget(sep2)
        
        # Geri al
        undo_btn = QPushButton("\u21B6")
        undo_btn.setFixedSize(32, 32)
        undo_btn.setToolTip("Geri Al (Ctrl+Z)")
        undo_btn.clicked.connect(self._undo)
        layout.addWidget(undo_btn)
        
        # Ayırıcı
        sep3 = QWidget()
        sep3.setFixedSize(1, 24)
        sep3.setStyleSheet("background: rgba(255,255,255,0.1); border: none;")
        layout.addWidget(sep3)
        
        # Kopyala
        copy_btn = QPushButton("Kopyala")
        copy_btn.setAccessibleName("action-btn")
        copy_btn.setToolTip("Panoya Kopyala (Ctrl+C)")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(copy_btn)
        
        # Kaydet
        save_btn = QPushButton("Kaydet")
        save_btn.setAccessibleName("action-btn")
        save_btn.setToolTip("Dosyaya Kaydet (Ctrl+S)")
        save_btn.clicked.connect(self._save_to_file)
        layout.addWidget(save_btn)
        
        # İptal
        cancel_btn = QPushButton("\u2715")
        cancel_btn.setAccessibleName("cancel-btn")
        cancel_btn.setFixedSize(32, 32)
        cancel_btn.setToolTip("İptal (ESC)")
        cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(cancel_btn)
        
        # Toolbar pozisyonu: seçim alanının altında
        self._toolbar.adjustSize()
        tw = self._toolbar.width()
        th = self._toolbar.height()
        
        sel = self._selection_rect
        tx = sel.left()
        ty = sel.bottom() + 8
        
        # Ekrandan taşarsa üste koy
        if ty + th > self.height():
            ty = sel.top() - th - 8
        if ty < 0:
            ty = sel.bottom() + 8
        
        # Yatayda taşmasını engelle
        if tx + tw > self.width():
            tx = self.width() - tw - 10
        if tx < 0:
            tx = 10
        
        self._toolbar.move(tx, ty)
        self._toolbar.show()

    def _select_tool(self, tool: DrawingTool):
        """Çizim aracı seç"""
        self._current_tool = tool
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)
    
    def _update_color_btn(self):
        """Renk düğmesi arka planını güncelle"""
        self._color_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {self._draw_color.name()};
                border: 2px solid rgba(255,255,255,0.15);
                border-radius: 6px;
                min-width: 24px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                border: 2px solid rgba(255,255,255,0.35);
            }}
            """
        )
    
    def _pick_color(self):
        """Renk seçici"""
        color = QColorDialog.getColor(self._draw_color, self, "Renk Seçin")
        if color.isValid():
            self._draw_color = color
            self._update_color_btn()
    
    def _pick_width(self):
        """Kalınlık seçici (basit menü)"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(16, 16, 22, 0.96);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                color: rgba(255, 255, 255, 0.8);
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
        """)
        for w in [1, 2, 3, 5, 8, 12, 20]:
            action = menu.addAction(f"{w}px")
            action.triggered.connect(lambda checked, width=w: self._set_width(width))
        menu.exec(self._width_btn.mapToGlobal(QPoint(0, -menu.sizeHint().height())))
    
    def _set_width(self, w: int):
        self._draw_width = w
        self._width_btn.setText(f"{w}px")

    # --------------------------------------------------------- drawing
    def _commit_action(self, action: DrawingAction):
        """Çizim işlemini draw_pixmap'e uygula"""
        if not self._draw_pixmap:
            return
        
        painter = QPainter(self._draw_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._render_action(painter, action)
        painter.end()
    
    def _render_action(self, painter: QPainter, action: DrawingAction):
        """Tek bir çizim işlemini render et"""
        pen = QPen(action.color, action.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        
        if action.tool == DrawingTool.HIGHLIGHTER:
            c = QColor(action.color)
            c.setAlpha(80)
            pen = QPen(c, max(action.width * 4, 16), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)

        if action.tool == DrawingTool.ERASER:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(Qt.GlobalColor.transparent, max(action.width * 3, 12), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        if action.tool in (DrawingTool.PEN, DrawingTool.HIGHLIGHTER, DrawingTool.ERASER):
            if len(action.points) > 1:
                path = QPainterPath()
                path.moveTo(action.points[0])
                for pt in action.points[1:]:
                    path.lineTo(pt)
                painter.drawPath(path)
            elif len(action.points) == 1:
                painter.drawPoint(action.points[0])
        
        elif action.tool == DrawingTool.LINE:
            if action.start_point and action.end_point:
                painter.drawLine(action.start_point, action.end_point)
        
        elif action.tool == DrawingTool.ARROW:
            if action.start_point and action.end_point:
                self._draw_arrow(painter, action.start_point, action.end_point, pen)
        
        elif action.tool == DrawingTool.RECT:
            if action.start_point and action.end_point:
                r = QRectF(action.start_point, action.end_point).normalized()
                painter.drawRect(r)
        
        elif action.tool == DrawingTool.FILLED_RECT:
            if action.start_point and action.end_point:
                r = QRectF(action.start_point, action.end_point).normalized()
                fill_color = QColor(action.color)
                fill_color.setAlpha(60)
                painter.setBrush(fill_color)
                painter.drawRect(r)
        
        elif action.tool == DrawingTool.ELLIPSE:
            if action.start_point and action.end_point:
                r = QRectF(action.start_point, action.end_point).normalized()
                painter.drawEllipse(r)
        
        elif action.tool == DrawingTool.TEXT:
            if action.start_point and action.text:
                font = QFont("Segoe UI", action.font_size)
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(action.color)
                painter.drawText(action.start_point, action.text)
        
        elif action.tool == DrawingTool.BLUR:
            if action.start_point and action.end_point:
                self._apply_blur_region(painter, action)
        
        # Reset composition mode
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _render_action_live(self, painter: QPainter, action: DrawingAction):
        """Ekran üzerinde canlı çizim önizlemesi (seçim alanı offset'li)"""
        sel = self._selection_rect
        
        painter.save()
        painter.translate(sel.x(), sel.y())
        self._render_action(painter, action)
        painter.restore()

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, pen: QPen):
        """Ok çiz"""
        painter.drawLine(start, end)
        
        # Ok başı
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = max(pen.widthF() * 4, 14)
        
        p1 = QPointF(
            end.x() - arrow_size * math.cos(angle - math.pi / 6),
            end.y() - arrow_size * math.sin(angle - math.pi / 6)
        )
        p2 = QPointF(
            end.x() - arrow_size * math.cos(angle + math.pi / 6),
            end.y() - arrow_size * math.sin(angle + math.pi / 6)
        )
        
        arrow_head = QPolygonF([end, p1, p2])
        painter.setBrush(pen.color())
        painter.drawPolygon(arrow_head)
    
    def _apply_blur_region(self, painter: QPainter, action: DrawingAction):
        """Seçilen bölgeyi bulanıklaştır (pixelize)"""
        if not action.start_point or not action.end_point:
            return
        
        r = QRectF(action.start_point, action.end_point).normalized()
        sel = self._selection_rect
        
        # Kaynak görüntüden bölgeyi al
        src_rect = QRect(
            int(sel.x() + r.x()),
            int(sel.y() + r.y()),
            int(r.width()),
            int(r.height())
        )
        
        if self._full_pixmap and src_rect.width() > 0 and src_rect.height() > 0:
            region = self._full_pixmap.copy(src_rect)
            # Küçült ve geri büyüt = pixelize efekti
            block_size = 8
            small = region.scaled(
                max(1, region.width() // block_size),
                max(1, region.height() // block_size),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            blurred = small.scaled(
                region.width(),
                region.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            painter.drawPixmap(r.toRect(), blurred)

    def _start_text_input(self, pos: QPoint):
        """Metin ekleme diyalogu"""
        sel = self._selection_rect
        if not sel.contains(pos):
            return
        
        local = QPointF(pos.x() - sel.x(), pos.y() - sel.y())
        
        text, ok = QInputDialog.getText(
            self, "Metin Ekle", "Metin:",
            QLineEdit.EchoMode.Normal, ""
        )
        
        if ok and text:
            action = DrawingAction(DrawingTool.TEXT, QColor(self._draw_color), self._draw_width)
            action.start_point = local
            action.text = text
            action.font_size = max(self._draw_width * 4, 14)
            
            self._commit_action(action)
            self._actions.append(action)
            self.update()

    # --------------------------------------------------------- actions
    def _undo(self):
        """Son çizimi geri al"""
        if not self._actions:
            return
        
        self._actions.pop()
        self._rebuild_draw_pixmap()
        self.update()
    
    def _rebuild_draw_pixmap(self):
        """Tüm çizimleri sıfırdan yeniden çiz"""
        if not self._selection_rect.isValid():
            return
        
        self._draw_pixmap = QPixmap(self._selection_rect.size())
        self._draw_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self._draw_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for action in self._actions:
            self._render_action(painter, action)
        painter.end()

    def _get_final_image(self) -> QPixmap:
        """Seçili bölgenin son halini al (çizimler dahil)"""
        sel = self._selection_rect
        
        # Seçili bölgeyi kırp
        cropped = self._full_pixmap.copy(sel)
        
        # Çizimleri üzerine uygula
        if self._draw_pixmap:
            painter = QPainter(cropped)
            painter.drawPixmap(0, 0, self._draw_pixmap)
            painter.end()
        
        return cropped

    def _copy_to_clipboard(self):
        """Seçili bölgeyi panoya kopyala"""
        if not self._has_selection:
            return
        
        final = self._get_final_image()
        
        # PNG bytes olarak sinyal gönder
        from PySide6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        final.save(buf, "PNG")
        png_bytes = buf.data().data()
        buf.close()

        copy_to_clipboard_safely(None, ClipItemType.IMAGE, png_bytes)
        
        self.screenshot_taken.emit(png_bytes)
        self._close_overlay()

    def _save_to_file(self):
        """Seçili bölgeyi dosyaya kaydet"""
        if not self._has_selection:
            return
        
        # Varsayılan yol
        save_dir = Path.home() / "Pictures" / "ClipStack"
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = str(save_dir / f"screenshot_{timestamp}.png")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Ekran Görüntüsünü Kaydet", default_name,
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        
        if not file_path:
            return
        
        final = self._get_final_image()
        ext = Path(file_path).suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "JPEG"
        elif ext == "bmp":
            ext = "BMP"
        else:
            ext = "PNG"
        
        final.save(file_path, ext)
        self.screenshot_saved.emit(file_path)
        self._close_overlay()

    def _cancel(self):
        """İptal"""
        self.screenshot_cancelled.emit()
        self._close_overlay()

    def _close_overlay(self):
        """Overlay'i kapat"""
        if self._toolbar:
            self._toolbar.hide()
        self.hide()
        self.close()
