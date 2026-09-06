import os
import sys
import math
import shutil
import threading
import requests
import webbrowser
import sounddevice as sd
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QFrame, QStackedWidget,
    QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics, QPainterPath

from app_settings import load_settings, save_settings, set_windows_autostart, get_app_data_dir
from updater import APP_VERSION, check_github_update, open_release_page
from font_loader import get_title_font, get_subtitle_font, get_body_font, get_mono_font

def get_audio_input_devices():
    """Returns list of (device_index, device_name) for available recording devices."""
    inputs = []
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                name = dev.get("name", f"Микрофон {idx}")
                inputs.append((idx, name))
    except Exception:
        pass
    return inputs

def get_cache_size_mb() -> float:
    """Calculates cache and temporary data size in MB."""
    app_dir = get_app_data_dir()
    total = 0
    try:
        for p in app_dir.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except Exception:
        pass
    return round(total / (1024 * 1024), 1)

def clear_cache_dir() -> bool:
    """Clears temporary files without deleting settings.json."""
    app_dir = get_app_data_dir()
    try:
        for p in app_dir.iterdir():
            if p.name != "settings.json":
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
        return True
    except Exception:
        return False

class ModernCheckBox(QCheckBox):
    """Custom pixel-perfect dark checkbox with vector checkmark."""
    def __init__(self, text: str, default_checked: bool = False, parent=None):
        super().__init__(text, parent)
        self.setChecked(default_checked)
        self.setFont(get_body_font(9.5))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        box_size = 18.0
        box_y = (rect.height() - box_size) / 2.0
        box_rect = QRectF(2.0, box_y, box_size, box_size)

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 120, 212)))
            painter.drawRoundedRect(box_rect, 4.0, 4.0)

            # Draw white checkmark
            painter.setPen(QPen(QColor(255, 255, 255), 1.8, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            p = QPainterPath()
            p.moveTo(box_rect.left() + 4.2, box_rect.top() + 9.2)
            p.lineTo(box_rect.left() + 7.4, box_rect.top() + 12.6)
            p.lineTo(box_rect.left() + 13.6, box_rect.top() + 5.4)
            painter.drawPath(p)
        else:
            border_c = QColor(0, 120, 212) if self.underMouse() else QColor(58, 58, 68)
            painter.setPen(QPen(border_c, 1.2))
            painter.setBrush(QBrush(QColor(26, 26, 30)))
            painter.drawRoundedRect(box_rect, 4.0, 4.0)

        # Text
        painter.setFont(self.font())
        painter.setPen(QColor("#E6E6EE"))
        text_rect = QRectF(28.0, 0, rect.width() - 30.0, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

class AppLogoWidget(QWidget):
    """Vector app squircle badge with white mic icon."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(10, 56, 113)))
        painter.drawRoundedRect(rect, 15.0, 15.0)

        # White mic vector
        cx = rect.center().x()
        cy = rect.center().y()
        painter.setPen(QPen(QColor(255, 255, 255), 2.0, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        mic_w = 8.0
        mic_h = 13.0
        painter.drawRoundedRect(QRectF(cx - mic_w/2, cy - 10.0, mic_w, mic_h), mic_w/2, mic_w/2)

        p_bracket = QPainterPath()
        p_bracket.arcMoveTo(QRectF(cx - 7.5, cy - 6.0, 15.0, 13.0), 180)
        p_bracket.arcTo(QRectF(cx - 7.5, cy - 6.0, 15.0, 13.0), 180, -180)
        painter.drawPath(p_bracket)

        painter.drawLine(QPoint(int(cx), int(cy + 7.0)), QPoint(int(cx), int(cy + 11.5)))
        painter.drawLine(QPoint(int(cx - 5.0), int(cy + 11.5)), QPoint(int(cx + 5.0), int(cy + 11.5)))

class VectorEyeButton(QPushButton):
    """Clean vector eye icon button for password visibility toggle."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_open = False

    def set_open(self, open_state: bool):
        self.is_open = open_state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QColor(32, 32, 38) if self.underMouse() else QColor(26, 26, 30)
        painter.setPen(QPen(QColor(44, 44, 52), 1.0))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        cx = rect.center().x()
        cy = rect.center().y()
        c = QColor("#FFFFFF") if self.underMouse() else QColor("#8E8E98")

        painter.setPen(QPen(c, 1.4, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Eye outline
        p = QPainterPath()
        p.moveTo(cx - 8.0, cy)
        p.quadTo(cx, cy - 5.5, cx + 8.0, cy)
        p.quadTo(cx, cy + 5.5, cx - 8.0, cy)
        painter.drawPath(p)

        # Pupil
        painter.setBrush(QBrush(c))
        painter.drawEllipse(QRectF(cx - 2.2, cy - 2.2, 4.4, 4.4))

        # Strikethrough if not open
        if not self.is_open:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPoint(int(cx - 6.5), int(cy + 5.5)), QPoint(int(cx + 6.5), int(cy - 5.5)))

class MicIconWidget(QWidget):
    """Small vector microphone icon for the audio meter row."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        painter.setPen(QPen(QColor("#8E8E98"), 1.3, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        mic_w = 4.4
        mic_h = 7.0
        painter.drawRoundedRect(QRectF(cx - mic_w/2, cy - 6.0, mic_w, mic_h), mic_w/2, mic_w/2)

        p = QPainterPath()
        p.arcMoveTo(QRectF(cx - 4.0, cy - 3.5, 8.0, 7.0), 180)
        p.arcTo(QRectF(cx - 4.0, cy - 3.5, 8.0, 7.0), 180, -180)
        painter.drawPath(p)

        painter.drawLine(QPoint(int(cx), int(cy + 3.5)), QPoint(int(cx), int(cy + 6.0)))
        painter.drawLine(QPoint(int(cx - 2.5), int(cy + 6.0)), QPoint(int(cx + 2.5), int(cy + 6.0)))

class SidebarNavButton(QPushButton):
    """Custom sidebar button with clean vector icon and pill selection."""
    def __init__(self, icon_type: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.button_text = text
        self.is_active = False
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_body_font(9.5, demi_bold=True))

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        btn_rect = QRectF(4, 2, rect.width() - 8, rect.height() - 4)

        if self.is_active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(10, 56, 113)))
            painter.drawRoundedRect(btn_rect, 8.0, 8.0)
            text_color = QColor("#FFFFFF")
            icon_color = QColor("#FFFFFF")
        else:
            if self.underMouse():
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
                painter.drawRoundedRect(btn_rect, 8.0, 8.0)
            text_color = QColor("#A4A4B0")
            icon_color = QColor("#8C8C9A")

        # Draw Icon
        center_y = rect.height() / 2.0
        icon_x = 22.0
        painter.setPen(QPen(icon_color, 1.4, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.icon_type == "mic":
            mic_w = 4.8
            mic_h = 7.6
            painter.drawRoundedRect(QRectF(icon_x - mic_w/2, center_y - 6.2, mic_w, mic_h), mic_w/2, mic_w/2)
            p_bracket = QPainterPath()
            p_bracket.arcMoveTo(QRectF(icon_x - 4.4, center_y - 3.8, 8.8, 7.6), 180)
            p_bracket.arcTo(QRectF(icon_x - 4.4, center_y - 3.8, 8.8, 7.6), 180, -180)
            painter.drawPath(p_bracket)
            painter.drawLine(QPoint(int(icon_x), int(center_y + 3.8)), QPoint(int(icon_x), int(center_y + 6.2)))
            painter.drawLine(QPoint(int(icon_x - 2.8), int(center_y + 6.2)), QPoint(int(icon_x + 2.8), int(center_y + 6.2)))

        elif self.icon_type == "keyboard":
            kw = 15.0
            kh = 10.0
            painter.drawRoundedRect(QRectF(icon_x - kw/2, center_y - kh/2, kw, kh), 2.0, 2.0)
            for kx in [-4, 0, 4]:
                painter.drawPoint(QPoint(int(icon_x + kx), int(center_y - 2)))
            for kx in [-3, 1]:
                painter.drawPoint(QPoint(int(icon_x + kx), int(center_y + 2)))

        elif self.icon_type == "sliders":
            sw = 14.0
            painter.drawLine(QPoint(int(icon_x - sw/2), int(center_y - 3.5)), QPoint(int(icon_x + sw/2), int(center_y - 3.5)))
            painter.drawLine(QPoint(int(icon_x - sw/2), int(center_y + 3.5)), QPoint(int(icon_x + sw/2), int(center_y + 3.5)))
            painter.drawEllipse(QRectF(icon_x - 3.5, center_y - 5.5, 4.0, 4.0))
            painter.drawEllipse(QRectF(icon_x + 0.5, center_y + 1.5, 4.0, 4.0))

        elif self.icon_type == "info":
            ir = 6.8
            painter.drawEllipse(QRectF(icon_x - ir, center_y - ir, ir*2, ir*2))
            painter.drawPoint(QPoint(int(icon_x), int(center_y - 2.8)))
            painter.drawLine(QPoint(int(icon_x), int(center_y - 1.0)), QPoint(int(icon_x), int(center_y + 3.2)))

        # Draw Label
        painter.setFont(self.font())
        painter.setPen(text_color)
        text_rect = QRectF(42.0, 0, rect.width() - 48.0, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.button_text)

class CustomThemeCard(QPushButton):
    """Widget theme card matching Mockup 2."""
    def __init__(self, theme_id: str, title: str, dot_color: str, is_active=False, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self.card_title = title
        self.dot_color = QColor(dot_color)
        self.is_active = is_active
        self.setFixedHeight(76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QColor(24, 24, 28)
        if self.is_active:
            border = QPen(QColor(10, 88, 180), 1.8)
        else:
            border = QPen(QColor(255, 255, 255, 18), 1.0)

        painter.setPen(border)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        # Dot
        cx = rect.center().x()
        cy = rect.top() + 26.0
        r = 7.5
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.dot_color))
        painter.drawEllipse(QRectF(cx - r, cy - r, r*2, r*2))

        # Title
        painter.setFont(get_body_font(10, demi_bold=True))
        painter.setPen(QColor("#FFFFFF" if self.is_active else "#C4C4CE"))
        text_rect = QRectF(rect.left(), rect.top() + 42.0, rect.width(), 24.0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.card_title)

class SettingsWindow(QDialog):
    theme_changed = pyqtSignal(str)
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(650, 680)

        self.settings = load_settings()
        self._drag_pos = None
        self._is_listening_hotkey = False

        self._init_ui()
        self._load_values()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: #121214;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
            }
        """)
        root_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 1. Header Bar
        header = QFrame(self.container)
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 16, 0)

        title_lbl = QLabel("VoiceTyping", header)
        title_lbl.setFont(get_title_font(12, bold=True))
        title_lbl.setStyleSheet("color: #FFFFFF;")

        ver_lbl = QLabel(f"v{APP_VERSION}", header)
        ver_lbl.setFont(get_body_font(10))
        ver_lbl.setStyleSheet("color: #70707B; margin-left: 4px;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(ver_lbl)
        header_layout.addStretch()

        btn_close = QPushButton("✕", header)
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8E8E98;
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
            }
        """)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)

        container_layout.addWidget(header)

        # Header separator
        sep_top = QFrame(self.container)
        sep_top.setFixedHeight(1)
        sep_top.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        container_layout.addWidget(sep_top)

        # 2. Main Body: Sidebar + StackedWidget
        body = QFrame(self.container)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar with width 196px for comfortable text display
        sidebar = QFrame(body)
        sidebar.setFixedWidth(196)
        sidebar.setStyleSheet("background-color: transparent;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(6)

        self.btn_tab_rec = SidebarNavButton("mic", "Запись", sidebar)
        self.btn_tab_keys = SidebarNavButton("keyboard", "Горячие клавиши", sidebar)
        self.btn_tab_gen = SidebarNavButton("sliders", "Общее", sidebar)
        self.btn_tab_about = SidebarNavButton("info", "О приложении", sidebar)

        self.nav_buttons = [self.btn_tab_rec, self.btn_tab_keys, self.btn_tab_gen, self.btn_tab_about]
        for idx, btn in enumerate(self.nav_buttons):
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_tab(i))
            sb_layout.addWidget(btn)

        sb_layout.addStretch()
        body_layout.addWidget(sidebar)

        # Sidebar separator
        sep_mid = QFrame(body)
        sep_mid.setFixedWidth(1)
        sep_mid.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        body_layout.addWidget(sep_mid)

        # Pages container
        self.stack = QStackedWidget(body)
        self.page_recording = self._create_recording_page()
        self.page_hotkeys = self._create_hotkeys_page()
        self.page_general = self._create_general_page()
        self.page_about = self._create_about_page()

        self.stack.addWidget(self.page_recording)
        self.stack.addWidget(self.page_hotkeys)
        self.stack.addWidget(self.page_general)
        self.stack.addWidget(self.page_about)

        body_layout.addWidget(self.stack)
        container_layout.addWidget(body)

        # Bottom separator
        sep_bot = QFrame(self.container)
        sep_bot.setFixedHeight(1)
        sep_bot.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        container_layout.addWidget(sep_bot)

        # 3. Footer Bar
        footer = QFrame(self.container)
        footer.setFixedHeight(56)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_status = QLabel("✓  Установлена последняя версия", footer)
        self.lbl_status.setFont(get_body_font(9.5))
        self.lbl_status.setStyleSheet("color: #34D399;")

        self.btn_save = QPushButton("Сохранить", footer)
        self.btn_save.setFixedSize(130, 32)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setFont(get_body_font(10, demi_bold=True))
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #121214;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #E6E6EE;
            }
            QPushButton:pressed {
                background-color: #CCCCCC;
            }
        """)
        self.btn_save.clicked.connect(self._save_and_close)

        footer_layout.addWidget(self.lbl_status)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_save)

        container_layout.addWidget(footer)

        self._switch_tab(0)

    # ------------------ TAB PAGES ------------------

    def _create_recording_page(self) -> QWidget:
        """Tab 1: Запись (Mockup 4)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # 1. Groq API
        lbl_api = QLabel("Groq API", w)
        lbl_api.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_api.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_api)

        api_row = QHBoxLayout()
        api_row.setSpacing(10)

        self.inp_api = QLineEdit(w)
        self.inp_api.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_api.setFixedHeight(38)
        self.inp_api.setFont(get_mono_font(9.5))
        self.inp_api.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A1E;
                color: #FFFFFF;
                border: 1px solid #2C2C34;
                border-radius: 8px;
                padding: 0 12px;
            }
            QLineEdit:focus {
                border-color: #0A58B4;
            }
        """)
        api_row.addWidget(self.inp_api)

        self.btn_eye = VectorEyeButton(w)
        self.btn_eye.clicked.connect(self._toggle_api_visibility)
        api_row.addWidget(self.btn_eye)

        self.btn_check_api = QPushButton("Проверить ключ", w)
        self.btn_check_api.setFixedSize(130, 38)
        self.btn_check_api.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_api.setFont(get_body_font(9.5, demi_bold=True))
        self.btn_check_api.setStyleSheet("""
            QPushButton {
                background-color: #222228;
                color: #E6E6EE;
                border: 1px solid #363640;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2B2B33;
                border-color: #4A4A58;
            }
        """)
        self.btn_check_api.clicked.connect(self._check_api_key_async)
        api_row.addWidget(self.btn_check_api)

        layout.addLayout(api_row)

        lbl_api_link = QLabel('<a href="https://console.groq.com/keys" style="color: #3B82F6; text-decoration: underline;">Получить API-ключ на console.groq.com ↗</a>', w)
        lbl_api_link.setFont(get_body_font(9.5))
        lbl_api_link.setOpenExternalLinks(True)
        layout.addWidget(lbl_api_link)

        layout.addSpacing(6)

        # 2. Микрофон
        lbl_mic = QLabel("Микрофон", w)
        lbl_mic.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_mic.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_mic)

        self.cmb_mic = QComboBox(w)
        self.cmb_mic.setFixedHeight(38)
        self.cmb_mic.setFont(get_body_font(9.5))
        self.cmb_mic.setStyleSheet("""
            QComboBox {
                background-color: #1A1A1E;
                color: #FFFFFF;
                border: 1px solid #2C2C34;
                border-radius: 8px;
                padding: 0 12px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1A1A1E;
                color: #FFFFFF;
                selection-background-color: #0A3871;
                border: 1px solid #2C2C34;
            }
        """)
        devices = get_audio_input_devices()
        self.cmb_mic.addItem("По умолчанию", None)
        for idx, dev_name in devices:
            self.cmb_mic.addItem(dev_name, idx)
        layout.addWidget(self.cmb_mic)

        # Volume bar with vector mic icon
        meter_row = QHBoxLayout()
        meter_row.setSpacing(10)
        meter_row.addWidget(MicIconWidget(w))

        self.pbar_volume = QProgressBar(w)
        self.pbar_volume.setFixedHeight(6)
        self.pbar_volume.setTextVisible(False)
        self.pbar_volume.setStyleSheet("""
            QProgressBar {
                background-color: #222228;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #00E676;
                border-radius: 3px;
            }
        """)
        self.pbar_volume.setValue(35)
        meter_row.addWidget(self.pbar_volume)
        layout.addLayout(meter_row)

        layout.addSpacing(6)

        # 3. Язык распознавания
        lbl_lang = QLabel("Язык распознавания", w)
        lbl_lang.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_lang.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_lang)

        self.cmb_lang = QComboBox(w)
        self.cmb_lang.setFixedHeight(38)
        self.cmb_lang.setFont(get_body_font(9.5))
        self.cmb_lang.setStyleSheet(self.cmb_mic.styleSheet())
        self.cmb_lang.addItem("Авто", "auto")
        self.cmb_lang.addItem("Русский (ru)", "ru")
        self.cmb_lang.addItem("English (en)", "en")
        layout.addWidget(self.cmb_lang)

        layout.addSpacing(6)

        # 4. Обработка текста
        lbl_proc = QLabel("Обработка текста", w)
        lbl_proc.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_proc.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_proc)

        self.cb_voice_punct = ModernCheckBox("Голосовая пунктуация", True, w)
        self.cb_trailing_space = ModernCheckBox("Завершающий пробел", False, w)
        layout.addWidget(self.cb_voice_punct)
        layout.addWidget(self.cb_trailing_space)

        layout.addStretch()
        return w

    def _create_hotkeys_page(self) -> QWidget:
        """Tab 2: Горячие клавиши (Mockup 3)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(14)

        # 1. Клавиша записи
        lbl_hk = QLabel("Клавиша записи", w)
        lbl_hk.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_hk.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_hk)

        hk_row = QHBoxLayout()
        hk_row.setSpacing(10)

        self.lbl_current_key = QLabel("F8", w)
        self.lbl_current_key.setFixedHeight(40)
        self.lbl_current_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_current_key.setFont(get_mono_font(11, bold=True))
        self.lbl_current_key.setStyleSheet("""
            background-color: #1A1A1E;
            color: #FFFFFF;
            border: 1px solid #2C2C34;
            border-radius: 8px;
        """)
        hk_row.addWidget(self.lbl_current_key, stretch=1)

        self.btn_rebind = QPushButton("↻  Переназначить", w)
        self.btn_rebind.setFixedSize(145, 40)
        self.btn_rebind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rebind.setFont(get_body_font(9.5, demi_bold=True))
        self.btn_rebind.setStyleSheet("""
            QPushButton {
                background-color: #222228;
                color: #E6E6EE;
                border: 1px solid #363640;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2B2B33;
                border-color: #4A4A58;
            }
        """)
        self.btn_rebind.clicked.connect(self._start_listening_key)
        hk_row.addWidget(self.btn_rebind)
        layout.addLayout(hk_row)

        lbl_hk_hint = QLabel("Нажмите новую клавишу, чтобы изменить сочетание.", w)
        lbl_hk_hint.setFont(get_body_font(9.0))
        lbl_hk_hint.setStyleSheet("color: #70707B;")
        layout.addWidget(lbl_hk_hint)

        layout.addSpacing(6)

        # 2. Режим активации
        lbl_mode = QLabel("Режим активации", w)
        lbl_mode.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_mode.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_mode)

        seg_box = QFrame(w)
        seg_box.setFixedHeight(42)
        seg_box.setStyleSheet("""
            QFrame {
                background-color: #1A1A1E;
                border: 1px solid #2C2C34;
                border-radius: 8px;
            }
        """)
        seg_layout = QHBoxLayout(seg_box)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)

        self.btn_mode_hold = QPushButton("Удерживать клавишу", seg_box)
        self.btn_mode_toggle = QPushButton("Одно нажатие", seg_box)

        for b in [self.btn_mode_hold, self.btn_mode_toggle]:
            b.setFixedHeight(32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(get_body_font(9.5, demi_bold=True))

        self.btn_mode_hold.clicked.connect(lambda: self._set_activation_mode("hold"))
        self.btn_mode_toggle.clicked.connect(lambda: self._set_activation_mode("toggle"))
        seg_layout.addWidget(self.btn_mode_hold)
        seg_layout.addWidget(self.btn_mode_toggle)
        layout.addWidget(seg_box)

        lbl_mode_hint = QLabel("«Удерживать» — запись идёт, пока клавиша зажата. «Одно нажатие» — старт и стоп разными нажатиями.", w)
        lbl_mode_hint.setWordWrap(True)
        lbl_mode_hint.setFont(get_body_font(9.0))
        lbl_mode_hint.setStyleSheet("color: #70707B;")
        layout.addWidget(lbl_mode_hint)

        layout.addSpacing(6)

        # 3. Дополнительные сочетания
        lbl_extra = QLabel("Дополнительные сочетания", w)
        lbl_extra.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_extra.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_extra)

        layout.addWidget(self._create_hotkey_card("Отменить последнюю запись", "Esc", w))
        layout.addWidget(self._create_hotkey_card("Открыть настройки", "Ctrl+Shift+V", w))

        layout.addSpacing(6)

        # 4. Checkbox
        self.cb_block_hotkey = ModernCheckBox("Блокировать клавишу в других приложениях", True, w)
        layout.addWidget(self.cb_block_hotkey)

        layout.addStretch()
        return w

    def _create_general_page(self) -> QWidget:
        """Tab 3: Общее (Mockup 2)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(14)

        # 1. Оформление виджета
        lbl_theme = QLabel("Оформление виджета", w)
        lbl_theme.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_theme.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_theme)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)

        self.card_theme_dark = CustomThemeCard("emerald", "Тёмная", "#10B981", is_active=True, parent=w)
        self.card_theme_light = CustomThemeCard("cyan", "Светлая", "#06B6D4", is_active=False, parent=w)
        self.card_theme_minimal = CustomThemeCard("claude", "Минимал", "#E2555F", is_active=False, parent=w)

        self.theme_cards = [self.card_theme_dark, self.card_theme_light, self.card_theme_minimal]
        for c in self.theme_cards:
            c.clicked.connect(lambda checked=False, card=c: self._select_theme_card(card.theme_id))
            theme_row.addWidget(c)

        layout.addLayout(theme_row)
        layout.addSpacing(6)

        # 2. Поведение системы
        lbl_sys = QLabel("Поведение системы", w)
        lbl_sys.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_sys.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_sys)

        self.cb_sound = ModernCheckBox("Звуковые сигналы", True, w)
        self.cb_autostart = ModernCheckBox("Автозапуск с Windows", False, w)
        self.cb_stream = ModernCheckBox("Потоковый предпросмотр", True, w)
        self.cb_updates = ModernCheckBox("Проверка обновлений", True, w)
        self.cb_tray_close = ModernCheckBox("Сворачивать в трей при закрытии", True, w)

        layout.addWidget(self.cb_sound)
        layout.addWidget(self.cb_autostart)
        layout.addWidget(self.cb_stream)
        layout.addWidget(self.cb_updates)
        layout.addWidget(self.cb_tray_close)

        layout.addSpacing(6)

        # 3. Хранение данных
        lbl_data = QLabel("Хранение данных", w)
        lbl_data.setFont(get_subtitle_font(10.5, demi_bold=True))
        lbl_data.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_data)

        card_cache = QFrame(w)
        card_cache.setFixedHeight(44)
        card_cache.setStyleSheet("""
            QFrame {
                background-color: #1A1A1E;
                border: 1px solid #282830;
                border-radius: 8px;
            }
        """)
        cc_layout = QHBoxLayout(card_cache)
        cc_layout.setContentsMargins(14, 0, 10, 0)

        sz = get_cache_size_mb()
        self.lbl_cache_info = QLabel(f"Кэш распознавания — {sz} МБ", card_cache)
        self.lbl_cache_info.setFont(get_body_font(9.5))
        self.lbl_cache_info.setStyleSheet("color: #E6E6EE; border: none;")
        cc_layout.addWidget(self.lbl_cache_info)
        cc_layout.addStretch()

        btn_clear = QPushButton("Очистить", card_cache)
        btn_clear.setFixedSize(90, 28)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setFont(get_body_font(9.0))
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #222228;
                color: #E6E6EE;
                border: 1px solid #363640;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2B2B33;
                border-color: #4A4A58;
            }
        """)
        btn_clear.clicked.connect(self._clear_cache_clicked)
        cc_layout.addWidget(btn_clear)
        layout.addWidget(card_cache)

        layout.addStretch()
        return w

    def _create_about_page(self) -> QWidget:
        """Tab 4: О приложении (Mockup 1)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 26, 28, 20)
        layout.setSpacing(14)

        # Top App Identity with vector mic icon
        top_box = QVBoxLayout()
        top_box.setSpacing(6)
        top_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        app_logo = AppLogoWidget(w)
        top_box.addWidget(app_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("VoiceTyping", w)
        title_lbl.setFont(get_title_font(14, bold=True))
        title_lbl.setStyleSheet("color: #FFFFFF;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_box.addWidget(title_lbl)

        ver_lbl = QLabel(f"Версия {APP_VERSION} (сборка 1187)", w)
        ver_lbl.setFont(get_body_font(9.5))
        ver_lbl.setStyleSheet("color: #8E8E98;")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_box.addWidget(ver_lbl)

        layout.addLayout(top_box)
        layout.addSpacing(10)

        # Check Updates Card
        card_upd = QFrame(w)
        card_upd.setFixedHeight(44)
        card_upd.setStyleSheet("""
            QFrame {
                background-color: #1A1A1E;
                border: 1px solid #282830;
                border-radius: 8px;
            }
        """)
        cu_layout = QHBoxLayout(card_upd)
        cu_layout.setContentsMargins(14, 0, 10, 0)

        lbl_upd = QLabel("Проверка обновлений", card_upd)
        lbl_upd.setFont(get_body_font(9.5))
        lbl_upd.setStyleSheet("color: #E6E6EE; border: none;")
        cu_layout.addWidget(lbl_upd)
        cu_layout.addStretch()

        btn_chk = QPushButton("Проверить", card_upd)
        btn_chk.setFixedSize(100, 28)
        btn_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chk.setFont(get_body_font(9.0))
        btn_chk.setStyleSheet("""
            QPushButton {
                background-color: #222228;
                color: #E6E6EE;
                border: 1px solid #363640;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2B2B33;
                border-color: #4A4A58;
            }
        """)
        btn_chk.clicked.connect(self._manual_check_updates)
        cu_layout.addWidget(btn_chk)
        layout.addWidget(card_upd)

        layout.addSpacing(6)

        # Links
        links = [
            ("Журнал изменений", "https://github.com/wesiks/VoiceTyping/releases"),
            ("Политика конфиденциальности", "https://github.com/wesiks/VoiceTyping#readme"),
            ("Условия использования", "https://github.com/wesiks/VoiceTyping/blob/main/LICENSE"),
            ("Сообщить о проблеме", "https://github.com/wesiks/VoiceTyping/issues")
        ]
        for link_text, link_url in links:
            lbl = QLabel(f'<a href="{link_url}" style="color: #3B82F6; text-decoration: underline;">{link_text}</a>', w)
            lbl.setFont(get_body_font(9.5))
            lbl.setOpenExternalLinks(True)
            layout.addWidget(lbl)

        layout.addStretch()

        # Copyright
        lbl_copy = QLabel("© 2026 VoiceTyping. Все права защищены.", w)
        lbl_copy.setFont(get_body_font(9.0))
        lbl_copy.setStyleSheet("color: #5E5E68;")
        lbl_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_copy)

        return w

    # ------------------ UI HELPERS ------------------

    def _create_hotkey_card(self, title: str, key_badge: str, parent: QWidget) -> QFrame:
        card = QFrame(parent)
        card.setFixedHeight(44)
        card.setStyleSheet("""
            QFrame {
                background-color: #1A1A1E;
                border: 1px solid #282830;
                border-radius: 8px;
            }
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(14, 0, 14, 0)

        lbl_t = QLabel(title, card)
        lbl_t.setFont(get_body_font(9.5))
        lbl_t.setStyleSheet("color: #E6E6EE; border: none;")
        c_layout.addWidget(lbl_t)
        c_layout.addStretch()

        lbl_b = QLabel(key_badge, card)
        lbl_b.setFont(get_mono_font(9.0, bold=True))
        lbl_b.setStyleSheet("""
            background-color: #26262E;
            color: #C8C8D4;
            border: 1px solid #3A3A44;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        c_layout.addWidget(lbl_b)
        return card

    # ------------------ LOGIC & EVENT HANDLING ------------------

    def _switch_tab(self, index: int):
        for idx, btn in enumerate(self.nav_buttons):
            btn.set_active(idx == index)
        self.stack.setCurrentIndex(index)

    def _select_theme_card(self, theme_id: str):
        self.settings["theme"] = theme_id
        for c in self.theme_cards:
            c.set_active(c.theme_id == theme_id)
        self.theme_changed.emit(theme_id)

    def _set_activation_mode(self, mode: str):
        self.settings["activation_mode"] = mode
        if mode == "hold":
            self.btn_mode_hold.setStyleSheet("background-color: #0A3871; color: #FFFFFF; border: none; border-radius: 6px;")
            self.btn_mode_toggle.setStyleSheet("background-color: transparent; color: #8E8E98; border: none;")
        else:
            self.btn_mode_hold.setStyleSheet("background-color: transparent; color: #8E8E98; border: none;")
            self.btn_mode_toggle.setStyleSheet("background-color: #0A3871; color: #FFFFFF; border: none; border-radius: 6px;")

    def _toggle_api_visibility(self):
        if self.inp_api.echoMode() == QLineEdit.EchoMode.Password:
            self.inp_api.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_eye.set_open(True)
        else:
            self.inp_api.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_eye.set_open(False)

    def _check_api_key_async(self):
        key = self.inp_api.text().strip()
        if not key:
            self.btn_check_api.setText("Введите ключ")
            return

        self.btn_check_api.setText("Проверка...")
        self.btn_check_api.setEnabled(False)

        def _worker():
            status_ok = False
            msg = ""
            try:
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": f"VoiceTyping/{APP_VERSION}"
                    },
                    timeout=4.0
                )
                if r.status_code == 200:
                    status_ok = True
                elif r.status_code == 401:
                    msg = "Неверный ключ"
                else:
                    msg = f"Код {r.status_code}"
            except Exception:
                msg = "Ошибка сети"

            def _done():
                self.btn_check_api.setEnabled(True)
                if status_ok:
                    self.btn_check_api.setText("✓ Действителен")
                    self.btn_check_api.setStyleSheet("background-color: #064E3B; color: #34D399; border: 1px solid #059669; border-radius: 8px;")
                else:
                    self.btn_check_api.setText(msg or "Ошибка")
                    self.btn_check_api.setStyleSheet("background-color: #4C0519; color: #FB7185; border: 1px solid #E11D48; border-radius: 8px;")

            QTimer.singleShot(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _start_listening_key(self):
        self._is_listening_hotkey = True
        self.lbl_current_key.setText("Нажмите клавишу...")
        self.lbl_current_key.setStyleSheet("""
            background-color: #0A3871;
            color: #FFFFFF;
            border: 1.5px solid #3B82F6;
            border-radius: 8px;
        """)

    def keyPressEvent(self, event):
        if self._is_listening_hotkey:
            key = event.key()
            from PyQt6.QtCore import Qt as QtCoreQt
            key_map = {
                QtCoreQt.Key.Key_F1: "F1", QtCoreQt.Key.Key_F2: "F2", QtCoreQt.Key.Key_F3: "F3",
                QtCoreQt.Key.Key_F4: "F4", QtCoreQt.Key.Key_F5: "F5", QtCoreQt.Key.Key_F6: "F6",
                QtCoreQt.Key.Key_F7: "F7", QtCoreQt.Key.Key_F8: "F8", QtCoreQt.Key.Key_F9: "F9",
                QtCoreQt.Key.Key_F10: "F10", QtCoreQt.Key.Key_F11: "F11", QtCoreQt.Key.Key_F12: "F12",
                QtCoreQt.Key.Key_CapsLock: "Caps_Lock", QtCoreQt.Key.Key_ScrollLock: "Scroll_Lock",
                QtCoreQt.Key.Key_Pause: "Pause", QtCoreQt.Key.Key_Insert: "Insert"
            }
            res_key = key_map.get(key)
            if not res_key and event.text():
                res_key = event.text().upper()

            if res_key:
                self.settings["hotkey"] = res_key.lower()
                self.lbl_current_key.setText(res_key)
                self.lbl_current_key.setStyleSheet("""
                    background-color: #1A1A1E;
                    color: #FFFFFF;
                    border: 1px solid #2C2C34;
                    border-radius: 8px;
                """)
                self._is_listening_hotkey = False
            return
        super().keyPressEvent(event)

    def _clear_cache_clicked(self):
        clear_cache_dir()
        self.lbl_cache_info.setText("Кэш распознавания — 0.0 МБ")

    def _manual_check_updates(self):
        self.lbl_status.setText("Проверка обновлений...")
        self.lbl_status.setStyleSheet("color: #A4A4B0;")

        def _worker():
            res = check_github_update(current_version=APP_VERSION)
            def _done():
                if res.get("has_update"):
                    latest = res.get("latest_version")
                    self.lbl_status.setText(f"Доступно обновление: v{latest}")
                    self.lbl_status.setStyleSheet("color: #60A5FA;")
                    url = res.get("download_url") or res.get("release_url")
                    open_release_page(url)
                elif res.get("error"):
                    self.lbl_status.setText(f"Ошибка проверки: {res.get('error')}")
                    self.lbl_status.setStyleSheet("color: #F87171;")
                else:
                    self.lbl_status.setText("✓  Установлена последняя версия")
                    self.lbl_status.setStyleSheet("color: #34D399;")
            QTimer.singleShot(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _load_values(self):
        s = self.settings
        self.inp_api.setText(s.get("groq_api_key", ""))
        self.lbl_current_key.setText(s.get("hotkey", "f8").upper())

        mode = s.get("activation_mode", "hold")
        self._set_activation_mode(mode)

        # Theme card selection
        current_theme = s.get("theme", "claude")
        for c in self.theme_cards:
            c.set_active(c.theme_id == current_theme)

        # Checkboxes
        self.cb_sound.setChecked(s.get("sound_enabled", True))
        self.cb_autostart.setChecked(s.get("autostart", False))
        self.cb_stream.setChecked(s.get("stream_preview", True))
        self.cb_updates.setChecked(s.get("check_updates", True))
        self.cb_tray_close.setChecked(s.get("minimize_to_tray", True))
        self.cb_voice_punct.setChecked(s.get("voice_punctuation", True))
        self.cb_trailing_space.setChecked(s.get("trailing_space", False))
        self.cb_block_hotkey.setChecked(s.get("block_hotkey", True))

        # Language
        lang = s.get("language", "ru")
        idx = self.cmb_lang.findData(lang)
        if idx != -1:
            self.cmb_lang.setCurrentIndex(idx)

        # Audio device
        dev_idx = s.get("audio_device", None)
        if dev_idx is not None:
            c_idx = self.cmb_mic.findData(dev_idx)
            if c_idx != -1:
                self.cmb_mic.setCurrentIndex(c_idx)

    def _save_and_close(self):
        self.settings["groq_api_key"] = self.inp_api.text().strip()
        self.settings["sound_enabled"] = self.cb_sound.isChecked()
        self.settings["autostart"] = self.cb_autostart.isChecked()
        self.settings["stream_preview"] = self.cb_stream.isChecked()
        self.settings["check_updates"] = self.cb_updates.isChecked()
        self.settings["minimize_to_tray"] = self.cb_tray_close.isChecked()
        self.settings["voice_punctuation"] = self.cb_voice_punct.isChecked()
        self.settings["trailing_space"] = self.cb_trailing_space.isChecked()
        self.settings["block_hotkey"] = self.cb_block_hotkey.isChecked()
        self.settings["language"] = self.cmb_lang.currentData() or "ru"
        self.settings["audio_device"] = self.cmb_mic.currentData()

        set_windows_autostart(self.settings["autostart"])
        save_settings(self.settings)
        self.settings_saved.emit(self.settings)
        self.close()

    # Window dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 50:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
