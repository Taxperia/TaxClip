from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidgetItem, QLayoutItem, QStyle

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hspacing=-1, vspacing=-1):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    # --- API ---
    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def addWidget(self, w):
        # QLayout.addWidget -> addItem çağırır, bizde override edildi
        super().addWidget(w)

    def insertWidget(self, index: int, widget):
        # Yeni widget’ı layout hiyerarşisine düzgünce bağla
        self.addChildWidget(widget)
        item = QWidgetItem(widget)
        index = max(0, min(index, len(self._items)))
        self._items.insert(index, item)
        self.invalidate()
        self.update()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._doLayout(QRect(0, 0, width, 0), testOnly=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, testOnly=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.sizeHint())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    # --- Spacing helpers ---
    def horizontalSpacing(self):
        if self._hspace >= 0:
            return self._hspace
        return self._smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspace >= 0:
            return self._vspace
        return self._smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def _smartSpacing(self, pm):
        parent = self.parentWidget()
        style = (parent.style() if parent else self.style())
        if not style:
            return 8
        val = style.pixelMetric(pm, None, parent)
        return 8 if val < 0 else val

    # --- Core layout ---
    def _doLayout(self, rect: QRect, testOnly: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)

        x = effective.x()
        y = effective.y()
        lineHeight = 0

        hSpace = self.horizontalSpacing()
        vSpace = self.verticalSpacing()

        for it in self._items:
            hint = it.sizeHint()
            if hint.width() <= 0 or hint.height() <= 0:
                # Güvenlik: 0 dönerse makul kart ölçüsü varsay
                hint = hint.expandedTo(QSize(120, 80))

            nextX = x + hint.width() + hSpace
            if nextX - hSpace > effective.right() and lineHeight > 0:
                x = effective.x()
                y = y + lineHeight + vSpace
                nextX = x + hint.width() + hSpace
                lineHeight = 0

            if not testOnly:
                it.setGeometry(QRect(QPoint(x, y), hint))

            x = nextX
            lineHeight = max(lineHeight, hint.height())

        return y + lineHeight - rect.y() + bottom