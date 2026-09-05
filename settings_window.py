import webbrowser
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QSlider, QFrame,
    QMessageBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from app_settings import load_settings, save_settings, set_windows_autostart
from themes import THEMES

class SettingsWindow(QDialog):
    theme_changed = pyqtSignal(str)
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VoiceTyping — Настройки")
        self.setFixedSize(500, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #141418;
                color: #FAF8F5;
                font-family: 'Segoe UI', 'Segoe UI Variable Text', sans-serif;
            }
            QLabel {
                color: #FAF8F5;
            }
            QFrame.card {
                background-color: #1C1C22;
                border: 1px solid #2B2B36;
                border-radius: 12px;
                padding: 14px;
            }
            QLineEdit {
                background-color: #24242E;
                border: 1px solid #383848;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #E06A38;
            }
            QComboBox {
                background-color: #24242E;
                border: 1px solid #383848;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #24242E;
                color: #FFFFFF;
                selection-background-color: #E06A38;
            }
            QCheckBox {
                color: #FAF8F5;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #383848;
                background-color: #24242E;
            }
            QCheckBox::indicator:checked {
                background-color: #E06A38;
                border-color: #E06A38;
            }
            QPushButton.primary {
                background-color: #E06A38;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton.primary:hover {
                background-color: #F57C48;
            }
            QPushButton.secondary {
                background-color: #24242E;
                color: #E0E0E6;
                border: 1px solid #383848;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
            }
            QPushButton.secondary:hover {
                background-color: #2E2E3C;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2B2B36;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #E06A38;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

        self.settings = load_settings()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("🎙️ Параметры голосового ввода")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(header)

        # 1. API Card
        api_card = QFrame()
        api_card.setProperty("class", "card")
        api_lay = QVBoxLayout(api_card)
        api_lay.setSpacing(8)

        api_title = QLabel("Groq API Ключ")
        api_title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        api_lay.addWidget(api_title)

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

        lbl_link = QLabel('<a style="color: #E06A38; text-decoration: none;" href="https://console.groq.com/keys">Получить бесплатный ключ на console.groq.com ↗</a>')
        lbl_link.setOpenExternalLinks(True)
        lbl_link.setFont(QFont("Segoe UI", 9))
        api_lay.addWidget(lbl_link)

        layout.addWidget(api_card)

        # 2. Themes Card
        theme_card = QFrame()
        theme_card.setProperty("class", "card")
        theme_lay = QVBoxLayout(theme_card)
        theme_lay.setSpacing(10)

        theme_title = QLabel("Цветовая тема виджета")
        theme_title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        theme_lay.addWidget(theme_title)

        self.theme_group = QButtonGroup(self)
        h_themes = QHBoxLayout()
        h_themes.setSpacing(8)

        current_theme = self.settings.get("theme", "claude")
        for tid, tinfo in THEMES.items():
            btn = QPushButton(f"● {tinfo['name']}")
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #24242E;
                    color: {tinfo['accent']};
                    border: 1px solid #383848;
                    border-radius: 8px;
                    padding: 8px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    border: 2px solid {tinfo['accent']};
                    background-color: #2D2A35;
                }}
            """)
            if tid == current_theme:
                btn.setChecked(True)
            
            btn.clicked.connect(lambda checked, t=tid: self._on_theme_selected(t))
            self.theme_group.addButton(btn)
            h_themes.addWidget(btn)

        theme_lay.addLayout(h_themes)
        layout.addWidget(theme_card)

        # 3. Controls & Hotkey Card
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "card")
        ctrl_lay = QVBoxLayout(ctrl_card)
        ctrl_lay.setSpacing(12)

        # Hotkey row
        h_hotkey = QHBoxLayout()
        h_hotkey.addWidget(QLabel("Клавиша (Push-to-Talk):"))
        self.combo_hotkey = QComboBox()
        keys_list = ["F8", "F4", "F7", "Caps_Lock", "Scroll_Lock", "Pause", "Insert"]
        self.combo_hotkey.addItems(keys_list)
        cur_hotkey = self.settings.get("hotkey", "f8").upper()
        idx = self.combo_hotkey.findText(cur_hotkey)
        if idx >= 0:
            self.combo_hotkey.setCurrentIndex(idx)
        h_hotkey.addWidget(self.combo_hotkey)
        ctrl_lay.addLayout(h_hotkey)

        # Sound checkbox
        self.chk_sound = QCheckBox("Мягкий звуковой сигнал при старте/остановке")
        self.chk_sound.setChecked(self.settings.get("sound_enabled", True))
        ctrl_lay.addWidget(self.chk_sound)

        # Autostart checkbox
        self.chk_autostart = QCheckBox("Запускать автоматически при включении Windows")
        self.chk_autostart.setChecked(self.settings.get("autostart", False))
        ctrl_lay.addWidget(self.chk_autostart)

        layout.addWidget(ctrl_card)

        # Save Button
        h_bottom = QHBoxLayout()
        h_bottom.addStretch()

        btn_save = QPushButton("Сохранить настройки")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save)
        h_bottom.addWidget(btn_save)

        layout.addLayout(h_bottom)

    def _on_theme_selected(self, theme_id: str):
        self.settings["theme"] = theme_id
        self.theme_changed.emit(theme_id)

    def _check_api_key(self):
        key = self.api_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Внимание", "Введите API-ключ для проверки.")
            return

        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5
            )
            if r.status_code == 200:
                QMessageBox.information(self, "Успех", "✅ Ключ Groq API успешно проверен и работает!")
            else:
                QMessageBox.critical(self, "Ошибка", f"Неверный ключ Groq API (код {r.status_code}).")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сети", f"Не удалось связаться с сервером Groq:\n{e}")

    def _save(self):
        self.settings["groq_api_key"] = self.api_input.text().strip()
        self.settings["hotkey"] = self.combo_hotkey.currentText().lower()
        self.settings["sound_enabled"] = self.chk_sound.isChecked()
        
        autostart = self.chk_autostart.isChecked()
        self.settings["autostart"] = autostart
        set_windows_autostart(autostart)

        save_settings(self.settings)
        self.settings_saved.emit(self.settings)
        QMessageBox.information(self, "Готово", "Настройки успешно сохранены!")
        self.accept()
