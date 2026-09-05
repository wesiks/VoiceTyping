import webbrowser
import requests
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QButtonGroup, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient

from app_settings import load_settings, save_settings, set_windows_autostart
from themes import THEMES, get_theme

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
        
        # Track
        track_color = self._accent if self._checked else QColor(44, 44, 54)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, 40, 22, 11, 11)
        
        # Thumb
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(int(self._thumb_pos), 2, 18, 18)


class ThemeCard(QPushButton):
    """Custom non-flat theme selector pill with circular swatch."""
    def __init__(self, theme_id, theme_info, is_active=False, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self.info = theme_info
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def set_active(self, active):
        self.setChecked(active)
        self._update_style()

    def _update_style(self):
        accent = self.info["accent"]
        bg = "#23232C" if self.isChecked() else "#1A1A22"
        border = f"1.5px solid {accent}" if self.isChecked() else "1px solid #2C2C38"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #FAF8F5;
                border: {border};
                border-radius: 8px;
                padding-left: 10px;
                padding-right: 12px;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #242430;
                border-color: {accent};
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw color circle on the left
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self.info["accent"])))
        painter.drawEllipse(12, 13, 10, 10)


class SettingsWindow(QDialog):
    theme_changed = pyqtSignal(str)
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Frameless modern window with translucent rounded body
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(540, 650)
        
        self._drag_pos = None
        self.settings = load_settings()
        self.theme = get_theme(self.settings.get("theme", "claude"))
        
        self._init_ui()

    def _init_ui(self):
        # Master layout inside translucent padding for drop shadow
        master_layout = QVBoxLayout(self)
        master_layout.setContentsMargins(16, 16, 16, 16)
        
        # Container Card (Machined obsidian body)
        self.card = QFrame()
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet("""
            QFrame#MainCard {
                background-color: #121216;
                border: 1px solid #262632;
                border-radius: 16px;
            }
            QLabel {
                color: #FAF8F5;
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            }
            QFrame.subcard {
                background-color: #191920;
                border: 1px solid #262632;
                border-radius: 10px;
                padding: 12px;
            }
            QLineEdit {
                background-color: #20202A;
                border: 1px solid #303040;
                border-radius: 8px;
                color: #FAF8F5;
                padding: 7px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #E06A38;
            }
            QComboBox {
                background-color: #20202A;
                border: 1px solid #303040;
                border-radius: 8px;
                color: #FAF8F5;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1C1C24;
                color: #FAF8F5;
                selection-background-color: #2D2D3A;
                border: 1px solid #303040;
            }
            QPushButton.primary {
                background-color: #E06A38;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 9px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton.primary:hover {
                background-color: #F07A48;
            }
            QPushButton.secondary {
                background-color: #20202A;
                color: #D4D4DC;
                border: 1px solid #303040;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
            }
            QPushButton.secondary:hover {
                background-color: #2A2A38;
            }
        """)

        # Soft drop shadow around window
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 110))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(22, 16, 22, 22)
        card_layout.setSpacing(14)

        # 1. Custom Minimalist Title Bar
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 4)
        
        lbl_title = QLabel("Параметры VoiceTyping")
        lbl_title.setFont(QFont("Segoe UI Variable Text", 12, QFont.Weight.Bold))
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
                background-color: #242430;
                color: #FFFFFF;
            }
        """)
        btn_close.clicked.connect(self.close)
        title_bar.addWidget(btn_close)
        card_layout.addLayout(title_bar)

        # 2. API Section
        api_card = QFrame()
        api_card.setProperty("class", "subcard")
        api_lay = QVBoxLayout(api_card)
        api_lay.setSpacing(8)

        lbl_api = QLabel("Ключ Groq API")
        lbl_api.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.DemiBold))
        api_lay.addWidget(lbl_api)

        h_api = QHBoxLayout()
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("gsk_...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setText(self.settings.get("groq_api_key", ""))
        h_api.addWidget(self.api_input)

        btn_test = QPushButton("Проверить")
        btn_test.setProperty("class", "secondary")
        btn_test.clicked.connect(self._check_api_key)
        h_api.addWidget(btn_test)
        api_lay.addLayout(h_api)

        lbl_link = QLabel('<a style="color: #E06A38; text-decoration: none;" href="https://console.groq.com/keys">Получить бесплатный ключ на console.groq.com</a>')
        lbl_link.setOpenExternalLinks(True)
        lbl_link.setFont(QFont("Segoe UI Variable Text", 9))
        api_lay.addWidget(lbl_link)

        card_layout.addWidget(api_card)

        # 3. Theme Section
        theme_card = QFrame()
        theme_card.setProperty("class", "subcard")
        theme_lay = QVBoxLayout(theme_card)
        theme_lay.setSpacing(10)

        lbl_theme = QLabel("Цветовая тема")
        lbl_theme.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.DemiBold))
        theme_lay.addWidget(lbl_theme)

        h_themes = QHBoxLayout()
        h_themes.setSpacing(8)

        current_theme_id = self.settings.get("theme", "claude")
        self.theme_buttons = []
        for tid, tinfo in THEMES.items():
            btn = ThemeCard(tid, tinfo, is_active=(tid == current_theme_id))
            btn.setText(f"      {tinfo['name']}")
            btn.clicked.connect(lambda checked, t=tid: self._on_theme_selected(t))
            self.theme_buttons.append(btn)
            h_themes.addWidget(btn)

        theme_lay.addLayout(h_themes)
        card_layout.addWidget(theme_card)

        # 4. Controls Section
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "subcard")
        ctrl_lay = QVBoxLayout(ctrl_card)
        ctrl_lay.setSpacing(12)

        # Hotkey row
        h_hotkey = QHBoxLayout()
        h_hotkey.addWidget(QLabel("Клавиша Push-to-Talk:"))
        self.combo_hotkey = QComboBox()
        self.combo_hotkey.addItems(["F8", "F4", "F7", "Caps_Lock", "Scroll_Lock", "Pause", "Insert"])
        cur_hotkey = self.settings.get("hotkey", "f8").upper()
        idx = self.combo_hotkey.findText(cur_hotkey)
        if idx >= 0:
            self.combo_hotkey.setCurrentIndex(idx)
        h_hotkey.addWidget(self.combo_hotkey)
        ctrl_lay.addLayout(h_hotkey)

        # Sound toggle row
        h_sound = QHBoxLayout()
        h_sound.addWidget(QLabel("Мягкий звуковой сигнал при старте/остановке"))
        h_sound.addStretch()
        self.toggle_sound = ModernToggle(
            checked=self.settings.get("sound_enabled", True),
            accent_color=self.theme["accent"]
        )
        h_sound.addWidget(self.toggle_sound)
        ctrl_lay.addLayout(h_sound)

        # Autostart toggle row
        h_auto = QHBoxLayout()
        h_auto.addWidget(QLabel("Запускать при включении Windows"))
        h_auto.addStretch()
        self.toggle_autostart = ModernToggle(
            checked=self.settings.get("autostart", False),
            accent_color=self.theme["accent"]
        )
        h_auto.addWidget(self.toggle_autostart)
        ctrl_lay.addLayout(h_auto)

        card_layout.addWidget(ctrl_card)

        # 5. Inline Toast / Status Message
        self.toast_label = QLabel("")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Medium))
        self.toast_label.setFixedHeight(22)
        card_layout.addWidget(self.toast_label)

        # 6. Save Button
        h_bottom = QHBoxLayout()
        h_bottom.addStretch()

        self.btn_save = QPushButton("Сохранить настройки")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setStyleSheet(f"background-color: {self.theme['accent']};")
        self.btn_save.clicked.connect(self._save)
        h_bottom.addWidget(self.btn_save)

        card_layout.addLayout(h_bottom)
        master_layout.addWidget(self.card)

    def mousePressEvent(self, event):
        """Allows dragging the frameless window from its header."""
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
        QTimer.singleShot(3500, lambda: self.toast_label.setText(""))

    def _on_theme_selected(self, theme_id):
        self.settings["theme"] = theme_id
        self.theme = get_theme(theme_id)
        
        for btn in self.theme_buttons:
            btn.set_active(btn.theme_id == theme_id)

        self.toggle_sound.set_accent(self.theme["accent"])
        self.toggle_autostart.set_accent(self.theme["accent"])
        self.btn_save.setStyleSheet(f"background-color: {self.theme['accent']};")
        
        self.theme_changed.emit(theme_id)

    def _check_api_key(self):
        key = self.api_input.text().strip()
        if not key:
            self._show_toast("Введите ключ для проверки", is_error=True)
            return

        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5
            )
            if r.status_code == 200:
                self._show_toast("Ключ успешно подтвержден")
            else:
                self._show_toast(f"Неверный ключ (код {r.status_code})", is_error=True)
        except Exception as e:
            self._show_toast(f"Ошибка соединения: {e}", is_error=True)

    def _save(self):
        self.settings["groq_api_key"] = self.api_input.text().strip()
        self.settings["hotkey"] = self.combo_hotkey.currentText().lower()
        self.settings["sound_enabled"] = self.toggle_sound.isChecked()
        
        autostart = self.toggle_autostart.isChecked()
        self.settings["autostart"] = autostart
        set_windows_autostart(autostart)

        save_settings(self.settings)
        self.settings_saved.emit(self.settings)
        self._show_toast("Настройки сохранены")
        QTimer.singleShot(600, self.accept)
