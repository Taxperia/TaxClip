"""Haulbase-style chrome widgets and stylesheet for SettingsDialog."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFormLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QSizePolicy,
)


SETTINGS_STYLE = """
QDialog#SettingsDialog {
    background: transparent;
    color: #F5F5F5;
}

QFrame#SettingsSurface {
    background: #111115;
    border: 1px solid #2B2D36;
    border-radius: 14px;
}

QWidget#SettingsHeader,
QWidget#SettingsFooter,
QWidget#SettingsContent {
    background: transparent;
}

QLabel#SettingsTitle {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 700;
    background: transparent;
}

QLabel#SettingsSubtitle {
    color: #8A8A8A;
    font-size: 12px;
    background: transparent;
}

QLabel#PageTitle {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
    background: transparent;
}

QLabel#PageSubtitle {
    color: #8A8A8A;
    font-size: 12px;
    background: transparent;
    padding-bottom: 8px;
}

QLabel#SidebarFooterHint {
    color: #777984;
    font-size: 11px;
    background: transparent;
}

QLabel#SettingRowTitle {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QLabel#SettingRowDesc {
    color: #8A8A8A;
    font-size: 12px;
    background: transparent;
}

QLabel#SettingsSectionTitle {
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
    padding-top: 16px;
    padding-bottom: 5px;
}

QLabel#SettingsInfoText {
    color: #8A8A8A;
    font-size: 11px;
    background: transparent;
    padding-top: 5px;
    padding-bottom: 8px;
}

QFrame#AboutHeroCard {
    background: #1E1E1E;
    border: 1px solid #333333;
    border-radius: 12px;
}

QLabel#AboutAppIcon {
    background: #2A2A2A;
    border: 1px solid #4A4A4A;
    border-radius: 12px;
}

QLabel#AboutKicker {
    color: #F2A65A;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}

QLabel#AboutProductName {
    color: #FFFFFF;
    font-size: 22px;
    font-weight: 750;
    background: transparent;
}

QLabel#AboutProductDesc {
    color: #8A8A8A;
    font-size: 12px;
    background: transparent;
}

QLabel#AboutVersionBadge {
    color: #F0F0F0;
    background: #2A2A2A;
    border: 1px solid #4A4A4A;
    border-radius: 10px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
}

QFrame#AboutFeatureCard {
    background: #181818;
    border: 1px solid #333333;
    border-radius: 10px;
    min-height: 112px;
}

QLabel#AboutFeatureIcon {
    background: #2A2A2A;
    border: none;
    border-radius: 7px;
}

QLabel#AboutFeatureTitle,
QLabel#AboutSectionTitle {
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 650;
    background: transparent;
}

QLabel#AboutFeatureDesc,
QLabel#AboutSectionDesc {
    color: #8A8A8A;
    font-size: 11px;
    background: transparent;
}

QFrame#AboutUpdateCard,
QFrame#AboutLinksCard {
    background: #181818;
    border: 1px solid #333333;
    border-radius: 10px;
}

QPushButton#AboutPrimaryButton {
    background: #F2A65A;
    color: #1A1208;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 700;
}

QPushButton#AboutPrimaryButton:hover {
    background: #F5B56F;
}

QPushButton#AboutLinkButton {
    background: transparent;
    color: #C7C8CF;
    border: 1px solid #333333;
    border-radius: 7px;
    padding: 6px 11px;
    min-height: 24px;
}

QPushButton#AboutLinkButton:hover {
    color: #FFFFFF;
    background: #2A2A2A;
    border-color: #4A4A4A;
}

QFrame#SidebarDivider {
    background: #292B33;
    max-width: 1px;
    min-width: 1px;
    border: none;
}

QFrame#FooterDivider {
    background: #292B33;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

QFrame#SettingRowDivider {
    background: #292B33;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

QWidget#SettingsSidebar {
    background: transparent;
    border: none;
}

QScrollArea {
    background: transparent;
    border: none;
}

QWidget#SettingsPage {
    background: #111115;
}

QComboBox {
    background: #1E1E1E;
    color: #F0F0F0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 20px;
    min-width: 140px;
}

QComboBox:hover {
    border-color: #4A4A4A;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: #1E1E1E;
    color: #F0F0F0;
    border: 1px solid #333333;
    selection-background-color: #2A2A2A;
    selection-color: #FFFFFF;
    outline: none;
}

QLineEdit, QSpinBox {
    background: #1E1E1E;
    color: #F0F0F0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 20px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #F2A65A;
}

QPushButton {
    background: #1E1E1E;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 8px 14px;
    min-height: 28px;
}

QPushButton:hover {
    background: #2A2A2A;
    border-color: #4A4A4A;
}

QPushButton:disabled {
    color: #666666;
    background: #181818;
}

QPushButton#SettingsNavBtn {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #A5A6AF;
    text-align: left;
    padding: 7px 5px;
    font-size: 13px;
    min-height: 21px;
    max-height: 21px;
}

QPushButton#SettingsNavBtn:hover {
    background: #1C1C1C;
    color: #E0E0E0;
    border: none;
}

QPushButton#SettingsNavBtn[active="true"] {
    background: transparent;
    color: #F3F3F5;
    font-weight: 600;
    border: none;
}

QPushButton#SettingsCloseBtn {
    background: transparent;
    border: none;
    color: #B0B0B0;
    font-size: 20px;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 20px;
}

QPushButton#SettingsCloseBtn:hover {
    background: #2A2A2A;
    color: #FFFFFF;
    border: none;
}

QPushButton#SettingsResetBtn {
    background: transparent;
    border: none;
    color: #C7C8CF;
    font-size: 13px;
    padding: 8px 12px;
    min-height: 20px;
}

QPushButton#SettingsResetBtn:hover {
    color: #FFFFFF;
    background: transparent;
    border: none;
}

QPushButton#SettingsDoneBtn {
    background: #F2A65A;
    color: #1A1208;
    border: none;
    border-radius: 8px;
    padding: 8px 0;
    font-size: 13px;
    font-weight: 700;
    min-height: 20px;
    max-height: 20px;
}

QPushButton#SettingsDoneBtn:hover {
    background: #F5B56F;
    border: none;
}

QPushButton#SettingsDoneBtn:pressed {
    background: #E09545;
    border: none;
}

QGroupBox {
    color: #F0F0F0;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #C8C8C8;
}

QLabel {
    color: #E8E8E8;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3A3A3A;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #505050;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}
"""


_BASE_PALETTE = {
    "bg": "#111115",
    "border": "#2B2D36",
    "text": "#E8E8E8",
    "strong": "#FFFFFF",
    "muted": "#8A8A8A",
    "subtle": "#777984",
    "divider": "#292B33",
    "control_bg": "#1E1E1E",
    "control_text": "#F0F0F0",
    "control_border": "#333333",
    "focus": "#F2A65A",
    "hover_bg": "#2A2A2A",
    "hover_border": "#4A4A4A",
    "disabled_text": "#666666",
    "disabled_bg": "#181818",
    "nav": "#A5A6AF",
    "nav_hover": "#E0E0E0",
    "nav_active": "#F3F3F5",
    "close": "#B0B0B0",
    "secondary": "#C7C8CF",
    "accent": "#F2A65A",
    "accent_text": "#1A1208",
    "accent_hover": "#F5B56F",
    "accent_pressed": "#E09545",
    "scrollbar": "#3A3A3A",
    "scrollbar_hover": "#505050",
    "toggle_off": "#2B2C34",
    "knob": "#FFFFFF",
}


_THEME_PALETTES = {
    "default": {
        "bg": "#0B1220", "border": "#1F2937", "text": "#E6EDF3",
        "strong": "#F8FAFC", "muted": "#93A8C1", "subtle": "#64748B",
        "divider": "#1F2937", "control_bg": "#0F172A",
        "control_text": "#E6EDF3", "control_border": "#1F2937",
        "focus": "#7AA2FF", "hover_bg": "#15233B",
        "hover_border": "#35507A", "disabled_text": "#64748B",
        "disabled_bg": "#0B1626", "nav": "#94A3B8",
        "nav_hover": "#CBD5E1", "nav_active": "#F8FAFC",
        "close": "#94A3B8", "secondary": "#CBD5E1",
        "accent": "#1D4ED8", "accent_text": "#F8FAFC",
        "accent_hover": "#2563EB", "accent_pressed": "#1E3A8A",
        "scrollbar": "#35507A", "scrollbar_hover": "#40649B",
        "toggle_off": "#334155", "knob": "#FFFFFF",
    },
    "dark": {
        "bg": "#0A0A0A", "border": "#2A2A2A", "text": "#E8E8E8",
        "strong": "#F5F5F5", "muted": "#999999", "subtle": "#777777",
        "divider": "#2A2A2A", "control_bg": "#1A1A1A",
        "control_text": "#E8E8E8", "control_border": "#2A2A2A",
        "focus": "#3B82F6", "hover_bg": "#252525",
        "hover_border": "#404040", "disabled_text": "#666666",
        "disabled_bg": "#151515", "nav": "#888888",
        "nav_hover": "#CCCCCC", "nav_active": "#F5F5F5",
        "close": "#AAAAAA", "secondary": "#C8C8C8",
        "accent": "#2563EB", "accent_text": "#F9FAFB",
        "accent_hover": "#1D4ED8", "accent_pressed": "#1E3A8A",
        "scrollbar": "#2A2A2A", "scrollbar_hover": "#353535",
        "toggle_off": "#303030", "knob": "#FFFFFF",
    },
    "light": {
        "bg": "#F8FAFC", "border": "#CBD5E1", "text": "#0F172A",
        "strong": "#0F172A", "muted": "#64748B", "subtle": "#64748B",
        "divider": "#E2E8F0", "control_bg": "#FFFFFF",
        "control_text": "#0F172A", "control_border": "#E2E8F0",
        "focus": "#2563EB", "hover_bg": "#EAF1FF",
        "hover_border": "#CBD5E1", "disabled_text": "#94A3B8",
        "disabled_bg": "#F1F5F9", "nav": "#475569",
        "nav_hover": "#1E293B", "nav_active": "#0F172A",
        "close": "#475569", "secondary": "#334155",
        "accent": "#2563EB", "accent_text": "#FFFFFF",
        "accent_hover": "#1D4ED8", "accent_pressed": "#1E3A8A",
        "scrollbar": "#CBD5E1", "scrollbar_hover": "#94A3B8",
        "toggle_off": "#CBD5E1", "knob": "#FFFFFF",
    },
    "purple": {
        "bg": "#0E0C16", "border": "#241E40", "text": "#ECE7FF",
        "strong": "#F5F3FF", "muted": "#A99DCB", "subtle": "#786F98",
        "divider": "#241E40", "control_bg": "#141225",
        "control_text": "#ECE7FF", "control_border": "#241E40",
        "focus": "#A78BFA", "hover_bg": "#1B1731",
        "hover_border": "#3B315F", "disabled_text": "#786F98",
        "disabled_bg": "#100E1C", "nav": "#A99DCB",
        "nav_hover": "#D8D0F3", "nav_active": "#F5F3FF",
        "close": "#C8BDF2", "secondary": "#C8BDF2",
        "accent": "#8B5CF6", "accent_text": "#F5F3FF",
        "accent_hover": "#7C3AED", "accent_pressed": "#5B21B6",
        "scrollbar": "#3B315F", "scrollbar_hover": "#524187",
        "toggle_off": "#3B315F", "knob": "#FFFFFF",
    },
    "cyberpunk": {
        "bg": "#0D0221", "border": "#4A176A", "text": "#F0E7FF",
        "strong": "#FFFFFF", "muted": "#A88FD9", "subtle": "#77649D",
        "divider": "#35104F", "control_bg": "#1A0933",
        "control_text": "#F0E7FF", "control_border": "#FF006E",
        "focus": "#FF006E", "hover_bg": "#240A44",
        "hover_border": "#8338EC", "disabled_text": "#77649D",
        "disabled_bg": "#12031F", "nav": "#A88FD9",
        "nav_hover": "#FF4DA0", "nav_active": "#FF006E",
        "close": "#D6C6EE", "secondary": "#D6C6EE",
        "accent": "#FF006E", "accent_text": "#FFFFFF",
        "accent_hover": "#FF1A7F", "accent_pressed": "#CC005B",
        "scrollbar": "#8338EC", "scrollbar_hover": "#9D4EFF",
        "toggle_off": "#3B1A58", "knob": "#FFFFFF",
    },
    "sunset": {
        "bg": "#2D1B3D", "border": "#6B3B5D", "text": "#FFFFFF",
        "strong": "#FFFFFF", "muted": "#E0B8C8", "subtle": "#B88D9E",
        "divider": "#6B3B5D", "control_bg": "#4A2C4F",
        "control_text": "#FFFFFF", "control_border": "#B96567",
        "focus": "#FF8C64", "hover_bg": "#5E3A52",
        "hover_border": "#D0736F", "disabled_text": "#B88D9E",
        "disabled_bg": "#38223F", "nav": "#E0B8C8",
        "nav_hover": "#FFD19A", "nav_active": "#FFBE76",
        "close": "#F0CBD7", "secondary": "#F0CBD7",
        "accent": "#F77F51", "accent_text": "#FFFFFF",
        "accent_hover": "#FF9566", "accent_pressed": "#D66843",
        "scrollbar": "#8C526A", "scrollbar_hover": "#AD667C",
        "toggle_off": "#6B455F", "knob": "#FFFFFF",
    },
    "matrix": {
        "bg": "#0D0D0D", "border": "#00661A", "text": "#00FF41",
        "strong": "#3AFF6B", "muted": "#00B82F", "subtle": "#008A23",
        "divider": "#004D14", "control_bg": "#001A00",
        "control_text": "#00FF41", "control_border": "#00B82F",
        "focus": "#00FF41", "hover_bg": "#003300",
        "hover_border": "#00FF41", "disabled_text": "#007A1F",
        "disabled_bg": "#001400", "nav": "#00B82F",
        "nav_hover": "#3AFF6B", "nav_active": "#00FF41",
        "close": "#00CC33", "secondary": "#00CC33",
        "accent": "#00FF41", "accent_text": "#001A00",
        "accent_hover": "#3AFF6B", "accent_pressed": "#00CC33",
        "scrollbar": "#00661A", "scrollbar_hover": "#009926",
        "toggle_off": "#004D14", "knob": "#FFFFFF",
    },
    "ocean": {
        "bg": "#0A1929", "border": "#1E5A78", "text": "#FFFFFF",
        "strong": "#FFFFFF", "muted": "#B3D9F2", "subtle": "#79A9C5",
        "divider": "#1E4B66", "control_bg": "#16364D",
        "control_text": "#FFFFFF", "control_border": "#297EAA",
        "focus": "#29B6F6", "hover_bg": "#1A4A68",
        "hover_border": "#29B6F6", "disabled_text": "#79A9C5",
        "disabled_bg": "#10283A", "nav": "#B3D9F2",
        "nav_hover": "#80DEEA", "nav_active": "#4DD0E1",
        "close": "#C6E6F5", "secondary": "#C6E6F5",
        "accent": "#0288D1", "accent_text": "#FFFFFF",
        "accent_hover": "#039BE5", "accent_pressed": "#0277BD",
        "scrollbar": "#236184", "scrollbar_hover": "#2C7CA4",
        "toggle_off": "#23516A", "knob": "#FFFFFF",
    },
    "retro": {
        "bg": "#2673BF", "border": "#7591B8", "text": "#FFFFFF",
        "strong": "#FFFFFF", "muted": "#D8E8FA", "subtle": "#B8D0EC",
        "divider": "#7591B8", "control_bg": "#FFFFFF",
        "control_text": "#000000", "control_border": "#7591B8",
        "focus": "#3689D9", "hover_bg": "#E8F2FF",
        "hover_border": "#A0A0A0", "disabled_text": "#777777",
        "disabled_bg": "#D8D8D8", "nav": "#D8E8FA",
        "nav_hover": "#FFFFFF", "nav_active": "#FFFFFF",
        "close": "#FFFFFF", "secondary": "#FFFFFF",
        "accent": "#2E68B0", "accent_text": "#FFFFFF",
        "accent_hover": "#3B7EC9", "accent_pressed": "#1F4F8B",
        "scrollbar": "#D8D8D8", "scrollbar_hover": "#B8B8B8",
        "toggle_off": "#7591B8", "knob": "#FFFFFF",
    },
}


def settings_palette(theme_key: str) -> dict[str, str]:
    palette = dict(_BASE_PALETTE)
    palette.update(_THEME_PALETTES.get(theme_key, _THEME_PALETTES["default"]))
    return palette


def build_settings_style(theme_key: str) -> str:
    """Recolor the reference layout using the application's selected theme."""
    palette = settings_palette(theme_key)
    replacements = {
        "#111115": palette["bg"],
        "#2B2D36": palette["border"],
        "#F5F5F5": palette["text"],
        "#FFFFFF": palette["strong"],
        "#8A8A8A": palette["muted"],
        "#777984": palette["subtle"],
        "#292B33": palette["divider"],
        "#1E1E1E": palette["control_bg"],
        "#F0F0F0": palette["control_text"],
        "#333333": palette["control_border"],
        "#F2A65A": palette["focus"],
        "#2A2A2A": palette["hover_bg"],
        "#4A4A4A": palette["hover_border"],
        "#666666": palette["disabled_text"],
        "#181818": palette["disabled_bg"],
        "#A5A6AF": palette["nav"],
        "#E0E0E0": palette["nav_hover"],
        "#F3F3F5": palette["nav_active"],
        "#B0B0B0": palette["close"],
        "#C7C8CF": palette["secondary"],
        "#1A1208": palette["accent_text"],
        "#F5B56F": palette["accent_hover"],
        "#E09545": palette["accent_pressed"],
        "#E8E8E8": palette["text"],
        "#C8C8C8": palette["secondary"],
        "#3A3A3A": palette["scrollbar"],
        "#505050": palette["scrollbar_hover"],
    }
    # Accent and focus share the same base token in the original style.
    # Replace the Done button rules after the one-pass palette substitution.
    pattern = re.compile("|".join(map(re.escape, replacements)))
    style = pattern.sub(lambda match: replacements[match.group(0)], SETTINGS_STYLE)
    style += (
        "\nQPushButton#SettingsDoneBtn {"
        f" background: {palette['accent']};"
        f" color: {palette['accent_text']};"
        "}\n"
        "QPushButton#SettingsDoneBtn:hover {"
        f" background: {palette['accent_hover']};"
        "}\n"
        "QPushButton#SettingsDoneBtn:pressed {"
        f" background: {palette['accent_pressed']};"
        "}\n"
    )
    return style


class SettingsCloseButton(QPushButton):
    """Thin, font-independent close icon used by the frameless modal."""

    def __init__(self, color="#B7B8C0", parent=None):
        super().__init__(parent)
        self._icon_color = QColor(color)
        self.setObjectName("SettingsCloseBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(
            self._icon_color, 1.5,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
        ))
        cx = self.width() / 2
        cy = self.height() / 2
        painter.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
        painter.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))

    def set_icon_color(self, color):
        self._icon_color = QColor(color)
        self.update()


class SettingsNavButton(QPushButton):
    """Reference-style sidebar button backed by painted line icons."""

    activated = Signal(int)

    def __init__(
        self,
        index: int,
        icon_name: str,
        label: str,
        parent=None,
        inactive_color="#777984",
        active_color="#F1F1F4",
    ):
        super().__init__(parent)
        self.index = index
        self._icon_name = icon_name
        self._label = label
        self._inactive_color = inactive_color
        self._active_color = active_color
        self.setObjectName("SettingsNavBtn")
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(False)
        self.setFocusPolicy(Qt.NoFocus)
        self._refresh_text()
        self.clicked.connect(lambda: self.activated.emit(self.index))

    def _refresh_text(self):
        self.setText(self._label)

    def set_label(self, label: str):
        self._label = label
        self._refresh_text()

    def set_active(self, active: bool):
        value = "true" if active else "false"
        changed = self.property("active") != value
        self.setProperty("active", value)
        self.setIcon(_settings_nav_icon(
            self._icon_name,
            self._active_color if active else self._inactive_color,
        ))
        self.setIconSize(QSize(17, 17))
        # Re-polishing hidden child widgets while a frameless top-level window
        # is being built can create visible native-window flashes on Windows.
        if changed and self.isVisible():
            self.style().unpolish(self)
            self.style().polish(self)
        self.update()

    def set_theme_colors(self, inactive_color: str, active_color: str):
        self._inactive_color = inactive_color
        self._active_color = active_color
        active = self.property("active") == "true"
        self.setIcon(_settings_nav_icon(
            self._icon_name,
            self._active_color if active else self._inactive_color,
        ))
        self.setIconSize(QSize(17, 17))
        self.update()


class SettingRow(QWidget):
    """Title + description on the left, control on the right (Haulbase row)."""

    def __init__(self, title: str, description: str = "", control: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SettingRowTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setVisible(bool(title))
        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("SettingRowDesc")
        self.desc_label.setWordWrap(True)
        self.desc_label.setVisible(bool(description))
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.desc_label)
        row.addLayout(text_col, 1)

        if control is not None:
            control.setParent(self)
            row.addWidget(control, 0, Qt.AlignVCenter | Qt.AlignRight)

        outer.addLayout(row)
        div = QFrame()
        div.setObjectName("SettingRowDivider")
        div.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(div)
        self.setMinimumHeight(64)

    def set_texts(self, title: str, description: str = ""):
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))
        self.desc_label.setText(description)
        self.desc_label.setVisible(bool(description))


def modernize_form_layout(form: QFormLayout):
    """Convert legacy QFormLayout rows to the shared settings-row design."""
    rows = []
    for row_index in range(form.rowCount()):
        label_item = form.itemAt(row_index, QFormLayout.ItemRole.LabelRole)
        field_item = form.itemAt(row_index, QFormLayout.ItemRole.FieldRole)
        span_item = form.itemAt(row_index, QFormLayout.ItemRole.SpanningRole)
        rows.append((
            _layout_item_payload(label_item),
            _layout_item_payload(field_item),
            _layout_item_payload(span_item),
        ))

    while form.count():
        form.takeAt(0)
    while form.rowCount():
        form.removeRow(0)

    form.setContentsMargins(0, 0, 31, 8)
    form.setHorizontalSpacing(0)
    form.setVerticalSpacing(0)

    for label_payload, field_payload, span_payload in rows:
        if span_payload is not None:
            widget = _payload_widget(span_payload)
            if widget is None:
                continue
            if isinstance(widget, QLabel):
                text = widget.text().strip()
                if not text:
                    widget.hide()
                    continue
                if "<b>" in text.lower():
                    widget.setObjectName("SettingsSectionTitle")
                else:
                    widget.setObjectName("SettingsInfoText")
                    if "#666" in widget.styleSheet() or "#888" in widget.styleSheet():
                        widget.setStyleSheet("")
                widget.setWordWrap(True)
            form.addRow(widget)
            continue

        label_widget = _payload_widget(label_payload)
        field_widget = _payload_widget(field_payload)
        if field_widget is None:
            continue

        title = ""
        if isinstance(label_widget, QLabel):
            title = label_widget.text().strip().rstrip(":")
            label_widget.hide()

        if not title and isinstance(field_widget, QLabel):
            text = field_widget.text().strip()
            if text:
                field_widget.setObjectName("SettingsInfoText")
                if "#666" in field_widget.styleSheet() or "#888" in field_widget.styleSheet():
                    field_widget.setStyleSheet("")
                field_widget.setWordWrap(True)
                form.addRow(field_widget)
            continue

        _normalize_control_widths(field_widget)
        form.addRow(SettingRow(title, "", field_widget))


def _layout_item_payload(item):
    if item is None:
        return None
    widget = item.widget()
    if widget is not None:
        return ("widget", widget)
    layout = item.layout()
    if layout is not None:
        return ("layout", layout)
    return None


def _payload_widget(payload) -> QWidget | None:
    if payload is None:
        return None
    kind, value = payload
    if kind == "widget":
        return value

    source_layout = value
    wrapper = QWidget()
    target = QHBoxLayout(wrapper)
    target.setContentsMargins(0, 0, 0, 0)
    target.setSpacing(max(6, source_layout.spacing()))
    while source_layout.count():
        item = source_layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        spacer = item.spacerItem()
        if widget is not None:
            _normalize_control_widths(widget)
            target.addWidget(widget, 0, item.alignment())
        elif child_layout is not None:
            target.addLayout(child_layout)
        elif spacer is not None:
            target.addItem(spacer)
    return wrapper


def _normalize_control_widths(widget: QWidget):
    if isinstance(widget, QComboBox):
        widget.setFixedWidth(190)
    elif isinstance(widget, QSpinBox):
        widget.setFixedWidth(190)
    elif isinstance(widget, QLineEdit):
        widget.setFixedWidth(260)
    elif isinstance(widget, QAbstractButton):
        if widget.maximumWidth() > 190:
            widget.setMaximumWidth(190)

    for child in widget.findChildren(QWidget):
        if child is widget:
            continue
        if isinstance(child, QComboBox):
            child.setFixedWidth(190)
        elif isinstance(child, QSpinBox):
            child.setFixedWidth(190)
        elif isinstance(child, QLineEdit):
            child.setFixedWidth(260)
        elif isinstance(child, QAbstractButton) and child.maximumWidth() > 190:
            child.setMaximumWidth(190)


def _settings_nav_icon(name: str, color: str) -> QIcon:
    """Create crisp monochrome line icons matching the supplied reference."""
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(
        QColor(color), 1.45, Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
    ))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "general":
        for y, knob_x in ((4.0, 6.0), (9.0, 12.0), (14.0, 7.5)):
            painter.drawLine(QPointF(2.5, y), QPointF(15.5, y))
            painter.drawEllipse(QPointF(knob_x, y), 1.7, 1.7)
    elif name == "appearance":
        painter.drawEllipse(QRectF(2.5, 2.5, 13, 13))
        painter.drawEllipse(QPointF(6.0, 6.4), 0.7, 0.7)
        painter.drawEllipse(QPointF(10.0, 5.4), 0.7, 0.7)
        painter.drawEllipse(QPointF(13.0, 8.0), 0.7, 0.7)
        painter.drawPath(_path("M 8.8 15.5 C 8.0 13.2 10.4 11.8 12.1 12.8"))
    elif name == "behavior":
        painter.drawLine(QPointF(9, 2.5), QPointF(9, 12.5))
        painter.drawLine(QPointF(5.8, 9.5), QPointF(9, 12.7))
        painter.drawLine(QPointF(12.2, 9.5), QPointF(9, 12.7))
        painter.drawLine(QPointF(3, 15.0), QPointF(15, 15.0))
    elif name == "security":
        painter.drawPath(_path(
            "M 9 2.2 L 14.3 4.4 L 13.6 11.5 "
            "C 12.8 14 10.8 15.2 9 16 "
            "C 7.2 15.2 5.2 14 4.4 11.5 L 3.7 4.4 Z"
        ))
    elif name == "video":
        painter.drawRoundedRect(QRectF(2.3, 4.0, 10.0, 10.0), 2, 2)
        painter.drawPath(_path("M 12.4 7 L 15.8 5.5 L 15.8 12.5 L 12.4 11"))
    elif name == "reminders":
        painter.drawPath(_path(
            "M 4 12.8 L 5.2 11.2 L 5.2 7.4 "
            "C 5.2 4.9 6.8 3.3 9 3.3 "
            "C 11.2 3.3 12.8 4.9 12.8 7.4 "
            "L 12.8 11.2 L 14 12.8 Z"
        ))
        painter.drawArc(QRectF(7.2, 13.0, 3.6, 2.5), 180 * 16, 180 * 16)
    elif name == "sync":
        painter.drawArc(QRectF(3.0, 3.0, 12.0, 12.0), 35 * 16, 135 * 16)
        painter.drawLine(QPointF(3.0, 5.5), QPointF(3.3, 2.4))
        painter.drawLine(QPointF(3.0, 5.5), QPointF(6.0, 5.0))
        painter.drawArc(QRectF(3.0, 3.0, 12.0, 12.0), 215 * 16, 135 * 16)
        painter.drawLine(QPointF(15.0, 12.5), QPointF(14.7, 15.6))
        painter.drawLine(QPointF(15.0, 12.5), QPointF(12.0, 13.0))
    elif name == "tray":
        painter.drawRoundedRect(QRectF(3.0, 2.5, 12.0, 13.0), 2, 2)
        painter.drawLine(QPointF(3.0, 6.2), QPointF(15.0, 6.2))
        painter.drawEllipse(QPointF(9.0, 10.6), 1.2, 1.2)
    else:
        painter.drawEllipse(QRectF(2.7, 2.7, 12.6, 12.6))
        painter.drawPoint(QPointF(9, 6))
        painter.drawLine(QPointF(9, 8.5), QPointF(9, 12.5))

    painter.end()
    return QIcon(pixmap)


def _path(commands: str) -> QPainterPath:
    """Parse the tiny M/L/C/Z path subset used by the icons above."""
    tokens = commands.replace(",", " ").split()
    path = QPainterPath()
    index = 0
    command = ""
    while index < len(tokens):
        token = tokens[index]
        if token in {"M", "L", "C", "Z"}:
            command = token
            index += 1
            if command == "Z":
                path.closeSubpath()
            continue
        if command == "M":
            path.moveTo(float(tokens[index]), float(tokens[index + 1]))
            index += 2
        elif command == "L":
            path.lineTo(float(tokens[index]), float(tokens[index + 1]))
            index += 2
        elif command == "C":
            path.cubicTo(
                float(tokens[index]), float(tokens[index + 1]),
                float(tokens[index + 2]), float(tokens[index + 3]),
                float(tokens[index + 4]), float(tokens[index + 5]),
            )
            index += 6
        else:
            index += 1
    return path
