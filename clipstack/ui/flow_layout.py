from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QWidgetItem, QLayoutItem, QStyle, QWidget


class FlowLayout(QLayout):
    """
    PySide6 için sağlam bir FlowLayout.

    - addWidget, insertWidget, removeWidget destekli
    - Görünmeyen widget'ları akıştan çıkarır
    - heightForWidth hesaplar (QScrollArea içinde doğru kaydırma için önemli)
    - hspacing/vspacing negatifse stil metriklerini kullanır
    - EĞER parent QWidget ise ve parent'ta başka bir layout yoksa, kendini parent'a otomatik kurar
    """

    def __init__(self, parent: Optional[QWidget] = None, margin: int = 0, hspacing: int = -1, vspacing: int = -1):
        super().__init__(parent)
        # Güvenli otomatik kurulum: parent bir QWidget ve üzerinde layout yoksa kendimizi kurarız
        if isinstance(parent, QWidget) and parent.layout() is None:
            parent.setLayout(self)

        self._items: List[QLayoutItem] = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    # ---- Zorunlu QLayout arayüzü ----

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def sizeHint(self) -> QSize:
        # QScrollArea, setWidgetResizable(True) iken sizeHint/minimumSize'ı dikkate alır
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        # Öğelerin sizeHint’lerinin birikimini kaba da olsa hesaba kat
        # (Tam yüksekliği _doLayout testOnly ile hesaplıyoruz)
        left, top, right, bottom = self.getContentsMargins()
        # Genişlik bilinmediği için en az bir kartın sığacağı kadar bir tahmin dön
        base = QSize(120, 80)
        for it in self._items:
            w = it.widget()
            # isVisible() parent pencere gizliyken de False döner. Kartın
            # kendisi gizlenmemişse pencere gösterilmeden önce de geometrisi
            # hesaplanmalı; aksi hâlde son kart (0, 0)'da ilk kartın üstüne
            # biner ve bir frame sonra yerine sıçrar.
            if w is not None and w.isHidden():
                continue
            base = base.expandedTo(it.sizeHint())
        return base + QSize(left + right, top + bottom)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._doLayout(rect, testOnly=False)

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        # Çizmeden, verilen genişlik için gereken yüksekliği hesapla
        return self._doLayout(QRect(0, 0, max(0, width), 0), testOnly=True)

    # ---- Kolaylık metotları ----

    def _adopt_widget(self, w: QWidget) -> None:
        """Adopt *w* as a child control, never as an owned native window."""
        parent = self.parentWidget()
        if parent is None:
            return

        # A parentless QWidget starts with a window type.  The one-argument
        # setParent() preserves that type, which leaves skeleton/loader cards
        # as native Windows windows.  Reset the type explicitly.
        if w.parentWidget() is not parent or w.isWindow():
            was_visible = w.isVisible()
            if was_visible:
                w.hide()
            w.setParent(parent, Qt.WindowType.Widget)
            if was_visible:
                w.show()

        # QLayout.addWidget() normally performs this registration, but this
        # custom implementation replaces it.
        self.addChildWidget(w)

    def addWidget(self, w: QWidget) -> None:
        self._adopt_widget(w)
        self._items.append(QWidgetItem(w))
        self.invalidate()

    def insertWidget(self, index: int, w: QWidget) -> None:
        index = max(0, min(index, len(self._items)))
        self._adopt_widget(w)
        self._items.insert(index, QWidgetItem(w))
        self.invalidate()

    def removeWidget(self, w: QWidget) -> None:
        for i, it in enumerate(list(self._items)):
            if it.widget() is w:
                self._items.pop(i)
                self.invalidate()
                break

    def horizontalSpacing(self) -> int:
        if self._hspace >= 0:
            return self._hspace
        return self._smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        if self._vspace >= 0:
            return self._vspace
        return self._smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def _smartSpacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parentWidget()
        style = (parent.style() if parent else self.style())
        if not style:
            return 8
        val = style.pixelMetric(pm, None, parent)
        return 8 if val < 0 else val

    # ---- Yerleşim çekirdeği ----

    def _doLayout(self, rect: QRect, testOnly: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)

        x = effective.x()
        y = effective.y()
        lineHeight = 0

        hSpace = self.horizontalSpacing()
        vSpace = self.verticalSpacing()

        maxRight = effective.x() + max(0, effective.width())

        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue

            hint = it.sizeHint()
            if hint.width() <= 0 or hint.height() <= 0:
                hint = hint.expandedTo(QSize(64, 48))

            # Liste görünümü: satırın tamamını kapla
            if w is not None and getattr(w, "_view_mode", "grid") == "list":
                list_h = max(hint.height(), int(getattr(w, "LIST_H", 72) or 72))
                hint = QSize(max(200, effective.width()), list_h)

            nextX = x + hint.width() + hSpace

            # Satır sonu kontrolü
            if (nextX - hSpace) > maxRight and lineHeight > 0:
                x = effective.x()
                y = y + lineHeight + vSpace
                nextX = x + hint.width() + hSpace
                lineHeight = 0

            if not testOnly:
                it.setGeometry(QRect(QPoint(x, y), hint))

            x = nextX
            lineHeight = max(lineHeight, hint.height())

        # Kullanılan toplam yükseklik
        used = (y + lineHeight) - rect.y()
        return used + top + bottom
