import math
import random
import threading
import requests
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QButtonGroup, QGraphicsDropShadowEffect,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient, QRadialGradient

from app_settings import load_settings, save_settings, set_windows_autostart
from themes import THEMES, get_theme
from font_loader import (
    get_title_font, get_subtitle_font, get_body_font, get_mono_font,
    get_font_families, init_custom_fonts
)
from updater import APP_VERSION, check_github_update, open_release_page

class ModernToggle(QWidget):
    """Custom smooth iOS/macOS-style toggle switch."""
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, accent_color="#E06A38", parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked
        self._accent = QColor(accent_color)
        self._thumb_pos = 20.0 if checked else 2.0
        
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_thumb_pos(self):
        return self._thumb_pos

    def set_thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    thumb_pos = pyqtProperty(float, get_thumb_pos, set_thumb_pos)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._anim.stop()
            self._anim.setStartValue(self._thumb_pos)
            self._anim.setEndValue(20.0 if checked else 2.0)
            self._anim.start()
            self.toggled.emit(self._checked)

    def set_accent(self, color_hex):
        self._accent = QColor(color_hex)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        track_color = self._accent if self._checked else QColor(44, 44, 54)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, 40, 22, 11, 11)
        
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(int(self._thumb_pos), 2, 18, 18)


class ThemeCard(QPushButton):
    """Spacious theme selector pill with circular swatch."""
    def __init__(self, theme_id, theme_info, is_active=False, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self.info = theme_info
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_subtitle_font(11, demi_bold=True))
        self._update_style()

    def set_active(self, active):
        self.setChecked(active)
        self._update_style()

    def _update_style(self):
        accent = self.info["accent"]
        bg = "rgba(38, 38, 52, 0.90)" if self.isChecked() else "rgba(24, 24, 32, 0.65)"
        border = f"1.5px solid {accent}" if self.isChecked() else "1px solid rgba(255, 255, 255, 0.12)"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #FAF8F5;
                border: {border};
                border-radius: 9px;
                padding-left: 32px;
                padding-right: 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: rgba(48, 48, 64, 0.90);
                border-color: {accent};
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self.info["accent"])))
        painter.drawEllipse(13, 14, 10, 10)


class AtmosphericCanvas(QFrame):
    """Background container with floating animated snow particles and ambient breathing glow."""
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.time_counter = 0.0
        self.particles = []
        for _ in range(50):
            depth = random.uniform(0.1, 1.0)
            self.particles.append({
                "x": random.uniform(0, 540),
                "y": random.uniform(0, 680),
                "radius": 0.9 + (depth * 1.8),
                "speed_y": 0.4 + (depth * 0.9),
                "sway_speed": random.uniform(0.015, 0.035),
                "sway_phase": random.uniform(0, math.pi * 2),
                "alpha": int(35 + (depth * 135)),
                "depth": depth
            })

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._update_particles)
        self.anim_timer.start()

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def _update_particles(self):
        self.time_counter += 0.02
        w = max(100, self.width())
        h = max(100, self.height())

        for p in self.particles:
            p["y"] += p["speed_y"]
            p["sway_phase"] += p["sway_speed"]
            p["x"] += math.sin(p["sway_phase"]) * (0.25 + 0.3 * p["depth"])

            if p["y"] > h + 5:
                p["y"] = -5
                p["x"] = random.uniform(0, w)
            if p["x"] < -5:
                p["x"] = w + 5
            elif p["x"] > w + 5:
                p["x"] = -5

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(0, 0, self.width(), self.height())
        radius = 16.0

        painter.setPen(QPen(QColor(255, 255, 255, 22), 1.2))
        painter.setBrush(QBrush(QColor(14, 14, 18, 252)))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        accent_rgb = QColor(self.theme["accent"])
        center_x = self.width() * 0.5
        center_y = self.height() * 0.4
        
        breath = 0.06 + 0.03 * math.sin(self.time_counter * 0.9)
        glow_alpha = int(breath * 255)
        
        rad_grad = QRadialGradient(center_x, center_y, self.width() * 0.55)
        rad_grad.setColorAt(0.0, QColor(accent_rgb.red(), accent_rgb.green(), accent_rgb.blue(), glow_alpha))
        rad_grad.setColorAt(0.65, QColor(accent_rgb.red(), accent_rgb.green(), accent_rgb.blue(), int(glow_alpha * 0.25)))
        rad_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(rad_grad))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        for p in self.particles:
            alpha = p["alpha"]
            r = p["radius"]
            if p["depth"] > 0.65:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, int(alpha * 0.25))))
                painter.drawEllipse(QPoint(int(p["x"]), int(p["y"])), int(r * 2.0), int(r * 2.0))

            painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            painter.drawEllipse(QPoint(int(p["x"]), int(p["y"])), int(r), int(r))

        top_grad = QLinearGradient(0, 1, 0, 16)
        top_grad.setColorAt(0.0, QColor(255, 255, 255, 45))
        top_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(top_grad))
        painter.drawRoundedRect(rect.adjusted(2, 1, -2, -self.height() + 16), radius - 1, radius - 1)


class SettingsWindow(QDialog):
    theme_changed = pyqtSignal(str)
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        init_custom_fonts()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(560, 800)
        
        self._drag_pos = None
        self.settings = load_settings()
        self.theme = get_theme(self.settings.get("theme", "claude"))
        
        self._init_ui()

    def _init_ui(self):
        master_layout = QVBoxLayout(self)
        master_layout.setContentsMargins(16, 16, 16, 16)
        
        fams = get_font_families()
        title_fam = fams["title"]
        body_fam = fams["body"]
        mono_fam = fams["mono"]
        
        self.card = AtmosphericCanvas(self.theme)
        self.card.setStyleSheet(f"""
            QLabel {{
                color: #FAF8F5;
                font-family: '{body_fam}', sans-serif;
            }}
            QFrame.subcard {{
                background-color: rgba(22, 22, 30, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 12px;
                padding: 14px;
            }}
            QLineEdit {{
                background-color: rgba(28, 28, 38, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #FAF8F5;
                padding: 8px 12px;
                font-size: 13px;
                font-family: '{mono_fam}', monospace;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {self.theme['accent']};
            }}
            QComboBox {{
                background-color: rgba(28, 28, 38, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                color: #FAF8F5;
                padding: 4px 10px;
                font-size: 12px;
                font-family: '{mono_fam}', monospace;
                font-weight: 600;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1A1A22;
                color: #FAF8F5;
                selection-background-color: #2D2D3A;
                border: 1px solid #303040;
                font-family: '{mono_fam}', monospace;
                font-size: 12px;
            }}
            QPushButton[class="primary"], QPushButton.primary {{
                background-color: {self.theme['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 9px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 600;
                font-family: '{body_fam}', sans-serif;
            }}
            QPushButton[class="primary"]:hover, QPushButton.primary:hover {{
                opacity: 0.9;
            }}
            QPushButton[class="secondary"], QPushButton.secondary {{
                background-color: rgba(38, 38, 52, 0.92);
                color: #FAF8F5;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
                font-family: '{body_fam}', sans-serif;
            }}
            QPushButton[class="secondary"]:hover, QPushButton.secondary:hover {{
                background-color: rgba(52, 52, 70, 0.98);
                border-color: rgba(255, 255, 255, 0.30);
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 130))
        shadow.setOffset(0, 10)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 18, 24, 24)
        card_layout.setSpacing(14)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 4)
        
        lbl_title = QLabel("Параметры VoiceTyping")
        lbl_title.setFont(get_title_font(13, bold=True))
        title_bar.addWidget(lbl_title)
        
        title_bar.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8C8C9A;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.10);
                color: #FFFFFF;
            }
        """)
        btn_close.clicked.connect(self.close)
        title_bar.addWidget(btn_close)
        card_layout.addLayout(title_bar)

        api_card = QFrame()
        api_card.setProperty("class", "subcard")
        api_lay = QVBoxLayout(api_card)
        api_lay.setSpacing(8)

        lbl_api = QLabel("Ключ Groq API")
        lbl_api.setFont(get_subtitle_font(11, demi_bold=True))
        api_lay.addWidget(lbl_api)

        h_api = QHBoxLayout()
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("gsk_...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setText(self.settings.get("groq_api_key", ""))
        self.api_input.setFont(get_mono_font(11))
        h_api.addWidget(self.api_input)

        self.btn_test = QPushButton("Проверить")
        self.btn_test.setProperty("class", "secondary")
        self.btn_test.setFont(get_body_font(10, demi_bold=True))
        self.btn_test.setFixedHeight(32)
        self.btn_test.setFixedWidth(105)
        self.btn_test.clicked.connect(self._check_api_key)
        h_api.addWidget(self.btn_test)
        api_lay.addLayout(h_api)

        self.api_progress = QProgressBar()
        self.api_progress.setFixedHeight(4)
        self.api_progress.setTextVisible(False)
        self.api_progress.setRange(0, 100)
        self.api_progress.setValue(0)
        self.api_progress.setVisible(False)
        self._update_progress_style(self.theme["accent"])
        api_lay.addWidget(self.api_progress)

        h_link = QHBoxLayout()
        self.lbl_link = QLabel(f'<a style="color: {self.theme["accent"]}; text-decoration: underline;" href="https://console.groq.com/keys">Получить бесплатный ключ на console.groq.com/keys</a>')
        self.lbl_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_link.setFont(get_body_font(9, demi_bold=True))
        self.lbl_link.linkActivated.connect(lambda url: webbrowser.open("https://console.groq.com/keys"))
        h_link.addWidget(self.lbl_link)
        h_link.addStretch()
        api_lay.addLayout(h_link)

        lbl_vpn_note = QLabel("Примечание: для регистрации и создания ключа на сайте Groq требуется VPN")
        lbl_vpn_note.setFont(get_body_font(8))
        lbl_vpn_note.setStyleSheet("color: #8C8C9A; margin-top: -3px;")
        api_lay.addWidget(lbl_vpn_note)

        card_layout.addWidget(api_card)

        theme_card = QFrame()
        theme_card.setProperty("class", "subcard")
        theme_lay = QVBoxLayout(theme_card)
        theme_lay.setSpacing(10)

        lbl_theme = QLabel("Цветовая тема")
        lbl_theme.setFont(get_subtitle_font(11, demi_bold=True))
        theme_lay.addWidget(lbl_theme)

        grid_themes = QGridLayout()
        grid_themes.setSpacing(10)

        current_theme_id = self.settings.get("theme", "claude")
        self.theme_buttons = []

        theme_items = list(THEMES.items())
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]

        for idx, (tid, tinfo) in enumerate(theme_items):
            r, c = positions[idx]
            btn = ThemeCard(tid, tinfo, is_active=(tid == current_theme_id))
            btn.setText(tinfo["name"])
            btn.clicked.connect(lambda checked, t=tid: self._on_theme_selected(t))
            self.theme_buttons.append(btn)
            grid_themes.addWidget(btn, r, c)

        theme_lay.addLayout(grid_themes)
        card_layout.addWidget(theme_card)

        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "subcard")
        ctrl_lay = QVBoxLayout(ctrl_card)
        ctrl_lay.setSpacing(12)

        h_hotkey = QHBoxLayout()
        lbl_hotkey = QLabel("Клавиша Push-to-Talk:")
        lbl_hotkey.setFont(get_body_font(11))
        h_hotkey.addWidget(lbl_hotkey)
        h_hotkey.addStretch()
        
        self.combo_hotkey = QComboBox()
        self.combo_hotkey.addItems(["F8", "F4", "F7", "Caps_Lock", "Scroll_Lock", "Pause", "Insert"])
        self.combo_hotkey.setFont(get_mono_font(11, bold=True))
        self.combo_hotkey.setFixedWidth(125)
        self.combo_hotkey.setFixedHeight(28)
        cur_hotkey = self.settings.get("hotkey", "f8").upper()
        idx = self.combo_hotkey.findText(cur_hotkey)
        if idx >= 0:
            self.combo_hotkey.setCurrentIndex(idx)
        h_hotkey.addWidget(self.combo_hotkey)
        ctrl_lay.addLayout(h_hotkey)

        h_sound = QHBoxLayout()
        lbl_sound = QLabel("Мягкий звуковой сигнал при старте/остановке")
        lbl_sound.setFont(get_body_font(11))
        h_sound.addWidget(lbl_sound)
        h_sound.addStretch()
        self.toggle_sound = ModernToggle(
            checked=self.settings.get("sound_enabled", True),
            accent_color=self.theme["accent"]
        )
        h_sound.addWidget(self.toggle_sound)
        ctrl_lay.addLayout(h_sound)

        h_auto = QHBoxLayout()
        lbl_auto = QLabel("Запускать при включении Windows")
        lbl_auto.setFont(get_body_font(11))
        h_auto.addWidget(lbl_auto)
        h_auto.addStretch()
        self.toggle_autostart = ModernToggle(
            checked=self.settings.get("autostart", False),
            accent_color=self.theme["accent"]
        )
        h_auto.addWidget(self.toggle_autostart)
        ctrl_lay.addLayout(h_auto)

        h_stream = QHBoxLayout()
        lbl_stream = QLabel("Потоковый предпросмотр речи")
        lbl_stream.setFont(get_body_font(11))
        h_stream.addWidget(lbl_stream)
        h_stream.addStretch()
        self.toggle_stream = ModernToggle(
            checked=self.settings.get("stream_preview", True),
            accent_color=self.theme["accent"]
        )
        h_stream.addWidget(self.toggle_stream)
        ctrl_lay.addLayout(h_stream)

        lbl_stream_hint = QLabel("Локальный вывод слов на лету (Vosk). Отключите для экономии памяти до ~30 МБ.")
        lbl_stream_hint.setFont(get_body_font(9))
        lbl_stream_hint.setStyleSheet("color: #8C8C9A; padding-left: 2px; margin-top: -2px; margin-bottom: 6px;")
        ctrl_lay.addWidget(lbl_stream_hint)

        h_updates = QHBoxLayout()
        lbl_updates = QLabel("Автоматически проверять обновления")
        lbl_updates.setFont(get_body_font(11))
        h_updates.addWidget(lbl_updates)
        h_updates.addStretch()
        self.toggle_updates = ModernToggle(
            checked=self.settings.get("check_updates", True),
            accent_color=self.theme["accent"]
        )
        h_updates.addWidget(self.toggle_updates)
        ctrl_lay.addLayout(h_updates)

        h_version = QHBoxLayout()
        self.lbl_version = QLabel(f"Версия VoiceTyping: v{APP_VERSION}")
        self.lbl_version.setFont(get_mono_font(10))
        self.lbl_version.setStyleSheet("color: #9E9EA8;")
        h_version.addWidget(self.lbl_version)
        h_version.addStretch()
        self.btn_check_update = QPushButton("Проверить обновления")
        self.btn_check_update.setProperty("class", "secondary")
        self.btn_check_update.setFont(get_body_font(10, demi_bold=True))
        self.btn_check_update.setFixedHeight(28)
        self.btn_check_update.setFixedWidth(175)
        self.btn_check_update.clicked.connect(self._on_check_update_clicked)
        h_version.addWidget(self.btn_check_update)
        ctrl_lay.addLayout(h_version)

        card_layout.addWidget(ctrl_card)

        self.toast_label = QLabel("")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.setFont(get_subtitle_font(10, demi_bold=True))
        self.toast_label.setFixedHeight(22)
        card_layout.addWidget(self.toast_label)

        h_bottom = QHBoxLayout()
        h_bottom.addStretch()

        self.btn_save = QPushButton("Сохранить настройки")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setFont(get_body_font(11, demi_bold=True))
        self.btn_save.setStyleSheet(f"background-color: {self.theme['accent']};")
        self.btn_save.clicked.connect(self._save)
        h_bottom.addWidget(self.btn_save)

        card_layout.addLayout(h_bottom)
        master_layout.addWidget(self.card)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 55:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _show_toast(self, message, is_error=False):
        color = "#F87171" if is_error else "#34D399"
        self.toast_label.setStyleSheet(f"color: {color};")
        self.toast_label.setText(message)
        QTimer.singleShot(4000, lambda: self.toast_label.setText(""))

    def _update_progress_style(self, color_hex):
        self.api_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
                max-height: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 2px;
            }}
        """)

    def _on_theme_selected(self, theme_id):
        self.settings["theme"] = theme_id
        self.theme = get_theme(theme_id)
        
        self.card.set_theme(self.theme)
        for btn in self.theme_buttons:
            btn.set_active(btn.theme_id == theme_id)

        self.toggle_sound.set_accent(self.theme["accent"])
        self.toggle_autostart.set_accent(self.theme["accent"])
        self.toggle_stream.set_accent(self.theme["accent"])
        self.toggle_updates.set_accent(self.theme["accent"])
        self._update_progress_style(self.theme["accent"])
        self.lbl_link.setText(f'<a style="color: {self.theme["accent"]}; text-decoration: underline;" href="https://console.groq.com/keys">Получить бесплатный ключ на console.groq.com/keys</a>')
        self.btn_save.setStyleSheet(f"background-color: {self.theme['accent']};")
        
        self.theme_changed.emit(theme_id)

    def _check_api_key(self):
        key = self.api_input.text().strip()
        if not key:
            self._show_toast("Введите ключ для проверки", is_error=True)
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("Проверка...")
        self.api_progress.setVisible(True)
        self.api_progress.setValue(12)
        self._update_progress_style(self.theme["accent"])
        self.toast_label.setText("")

        self._progress_target = 85
        self._progress_current = 12

        def _step_anim():
            if hasattr(self, "_progress_current") and self._progress_current < self._progress_target:
                self._progress_current += max(1, int((self._progress_target - self._progress_current) * 0.22))
                self.api_progress.setValue(self._progress_current)

        if hasattr(self, "_anim_timer") and self._anim_timer.isActive():
            self._anim_timer.stop()
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(40)
        self._anim_timer.timeout.connect(_step_anim)
        self._anim_timer.start()

        def _worker():
            status = 0
            err_msg = ""
            try:
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "VoiceTyping/1.2.0"
                    },
                    timeout=3.5
                )
                status = r.status_code
            except requests.exceptions.Timeout:
                err_msg = "Превышено время ожидания (проверьте интернет)"
            except requests.exceptions.ConnectionError:
                err_msg = "Ошибка подключения к Groq API"
            except Exception as e:
                err_msg = str(e)

            QTimer.singleShot(0, lambda: self._on_check_api_done(status, err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_check_api_done(self, status: int, err_msg: str):
        if hasattr(self, "_anim_timer") and self._anim_timer.isActive():
            self._anim_timer.stop()

        self.btn_test.setEnabled(True)
        self.btn_test.setText("Проверить")
        self.api_progress.setValue(100)

        if status == 200:
            self._update_progress_style("#34D399")
            self._show_toast("Ключ успешно подтвержден")
            QTimer.singleShot(2200, lambda: self.api_progress.setVisible(False))
        elif status == 401:
            self._update_progress_style("#F87171")
            self._show_toast("Неверный ключ (код 401)", is_error=True)
            QTimer.singleShot(3000, lambda: self.api_progress.setVisible(False))
        elif status == 403:
            self._update_progress_style("#FB923C")
            self._show_toast("Доступ к Groq ограничен (код 403). Включите VPN.", is_error=True)
            QTimer.singleShot(4500, lambda: self.api_progress.setVisible(False))
        elif err_msg:
            self._update_progress_style("#F87171")
            self._show_toast(err_msg, is_error=True)
            QTimer.singleShot(3000, lambda: self.api_progress.setVisible(False))
        else:
            self._update_progress_style("#F87171")
            self._show_toast(f"Ответ сервера: код {status}", is_error=True)
            QTimer.singleShot(3000, lambda: self.api_progress.setVisible(False))

    def _on_check_update_clicked(self):
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("Проверка...")
        self.toast_label.setText("")

        def _worker():
            res = check_github_update(current_version=APP_VERSION)
            QTimer.singleShot(0, lambda: self._handle_update_result(res))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_update_result(self, res: dict):
        self.btn_check_update.setEnabled(True)
        self.btn_check_update.setText("Проверить обновления")

        if res.get("has_update"):
            latest = res.get("latest_version")
            self._show_toast(f"Доступно обновление v{latest}!")
            open_release_page(res.get("download_url") or res.get("release_url"))
        elif res.get("error"):
            self._show_toast(f"{res.get('error')}", is_error=True)
        else:
            self._show_toast(f"У вас актуальная версия (v{APP_VERSION})")

    def _save(self):
        self.settings["groq_api_key"] = self.api_input.text().strip()
        self.settings["hotkey"] = self.combo_hotkey.currentText().lower()
        self.settings["sound_enabled"] = self.toggle_sound.isChecked()
        self.settings["stream_preview"] = self.toggle_stream.isChecked()
        self.settings["check_updates"] = self.toggle_updates.isChecked()
        
        autostart = self.toggle_autostart.isChecked()
        self.settings["autostart"] = autostart
        set_windows_autostart(autostart)

        save_settings(self.settings)
        self.settings_saved.emit(self.settings)
        self._show_toast("Настройки сохранены")
        QTimer.singleShot(600, self.accept)
