import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QRectF, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont
import webbrowser

from font_loader import get_body_font, get_title_font
from tray_icon import create_app_icon

DEFAULT_PRIVACY_TEXT = """<h2>Политика конфиденциальности VoiceTyping</h2>
<p style="color: #8E8E98;"><i>Дата вступления в силу: 8 сентября 2026 г.</i></p>
<p>VoiceTyping уважает вашу конфиденциальность. Приложение разработано для Windows и ставит безопасность ваших данных на первое место.</p>

<h3 style="color: #60A5FA;">1. Обработка звука и распознавание речи</h3>
<ul>
  <li><b>Режим «Только офлайн (Vosk)»:</b> запись и перевод речи в текст происходят <b>100% локально на вашем ПК</b>. Звук не отправляется в сеть, не сохраняется на серверах и не требует интернета или VPN.</li>
  <li><b>Режим «Умный гибрид» и «Только облако»:</b> аудио кратковременно передается по зашифрованному протоколу TLS напрямую в Groq API. Серверов-посредников разработчика нет, аудиопоток не сохраняется третьими лицами.</li>
</ul>

<h3 style="color: #60A5FA;">2. Буфер обмена</h3>
<p>Программа использует системный буфер Windows исключительно для быстрой вставки текста в целевое окно и сразу восстанавливает предыдущий скопированный элемент. Приложение <b>не ведет историю ввода</b> и не передает набранный текст.</p>

<h3 style="color: #60A5FA;">3. Отсутствие телеметрии</h3>
<p>VoiceTyping не собирает личные данные, IP-адреса, пароли и не содержит сторонней рекламы или скрытой аналитики.</p>

<h3 style="color: #60A5FA;">4. Открытый исходный код</h3>
<p>Код программы полностью открыт и доступен для независимой проверки: <a href="https://github.com/wesiks/VoiceTyping" style="color: #3B82F6;">github.com/wesiks/VoiceTyping</a>.</p>
"""

DEFAULT_TERMS_TEXT = """<h2>Условия использования VoiceTyping</h2>
<p style="color: #8E8E98;"><i>Дата вступления в силу: 8 сентября 2026 г.</i></p>

<h3 style="color: #60A5FA;">1. Общие положения и лицензия</h3>
<p>VoiceTyping распространяется на условиях открытой международной лицензии <b>MIT</b>. Программа бесплатна для личного и коммерческого использования, не содержит скрытых платежей или платных подписок.</p>

<h3 style="color: #60A5FA;">2. Права пользователя</h3>
<ul>
  <li>Свободная установка и запуск на любом количестве компьютеров под Windows;</li>
  <li>Свободная настройка всех параметров под свои задачи;</li>
  <li>Изучение исходного кода и создание собственных сборок.</li>
</ul>

<h3 style="color: #60A5FA;">3. Ограничение ответственности</h3>
<p>Программа предоставляется по принципу <b>«КАК ЕСТЬ» («AS IS»)</b> без каких-либо явных или косвенных гарантий. Разработчик не несет ответственности за сбои сторонних сервисов (включая сторонние API) или возможные потери данных.</p>
"""

def _load_doc(filename: str, fallback_html: str) -> str:
    candidates = [
        Path(__file__).resolve().parent.parent / filename,
        Path(sys.executable).parent / filename,
        Path(sys.executable).parent / "_internal" / filename
    ]
    for p in candidates:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                lines = []
                for line in content.splitlines():
                    if line.startswith("# "):
                        lines.append(f"<h2>{line[2:]}</h2>")
                    elif line.startswith("### "):
                        lines.append(f"<h3 style='color: #60A5FA;'>{line[4:]}</h3>")
                    elif line.startswith("## "):
                        lines.append(f"<h3 style='color: #E6E6EE;'>{line[3:]}</h3>")
                    elif line.startswith("- "):
                        lines.append(f"<li>{line[2:]}</li>")
                    elif line.strip() == "---":
                        lines.append("<hr style='border: none; border-top: 1px solid #282834; margin: 12px 0;'>")
                    elif line.strip():
                        lines.append(f"<p>{line}</p>")
                return "".join(lines)
            except Exception:
                pass
    return fallback_html

class LegalDocsDialog(QDialog):
    def __init__(self, initial_tab: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(580, 520)
        self._drag_pos = None

        self._privacy_html = _load_doc("PRIVACY.md", DEFAULT_PRIVACY_TEXT)
        self._terms_html = _load_doc("TERMS.md", DEFAULT_TERMS_TEXT)
        self._current_tab = initial_tab

        self._init_ui()
        self._switch_doc(initial_tab)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #141418;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }
        """)
        root_layout.addWidget(self.container)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        header = QFrame(self.container)
        header.setFixedHeight(48)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 0, 14, 0)

        title = QLabel("Правовая информация", header)
        title.setFont(get_title_font(12, bold=True))
        title.setStyleSheet("color: #FFFFFF; border: none;")
        h_layout.addWidget(title)
        h_layout.addStretch()

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
        h_layout.addWidget(btn_close)
        c_layout.addWidget(header)

        switch_bar = QFrame(self.container)
        switch_bar.setFixedHeight(44)
        switch_bar.setStyleSheet("background-color: #1A1A20; border-top: 1px solid rgba(255, 255, 255, 0.06); border-bottom: 1px solid rgba(255, 255, 255, 0.06);")
        sb_layout = QHBoxLayout(switch_bar)
        sb_layout.setContentsMargins(16, 4, 16, 4)
        sb_layout.setSpacing(8)

        self.btn_tab_privacy = QPushButton("Политика конфиденциальности", switch_bar)
        self.btn_tab_terms = QPushButton("Условия использования", switch_bar)

        for b in (self.btn_tab_privacy, self.btn_tab_terms):
            b.setFixedHeight(30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(get_body_font(9, demi_bold=True))

        self.btn_tab_privacy.clicked.connect(lambda: self._switch_doc(0))
        self.btn_tab_terms.clicked.connect(lambda: self._switch_doc(1))

        sb_layout.addWidget(self.btn_tab_privacy)
        sb_layout.addWidget(self.btn_tab_terms)
        sb_layout.addStretch()
        c_layout.addWidget(switch_bar)

        scroll = QScrollArea(self.container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #282834; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        cw_layout = QVBoxLayout(self.content_widget)
        cw_layout.setContentsMargins(20, 16, 20, 16)

        self.lbl_doc = QLabel(self.content_widget)
        self.lbl_doc.setFont(get_body_font(10))
        self.lbl_doc.setStyleSheet("color: #D1D1DB; border: none; line-height: 1.5;")
        self.lbl_doc.setWordWrap(True)
        self.lbl_doc.setOpenExternalLinks(True)
        cw_layout.addWidget(self.lbl_doc)
        cw_layout.addStretch()

        scroll.setWidget(self.content_widget)
        c_layout.addWidget(scroll)

        footer = QFrame(self.container)
        footer.setFixedHeight(50)
        footer.setStyleSheet("border-top: 1px solid rgba(255, 255, 255, 0.06);")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(18, 0, 18, 0)
        f_layout.setSpacing(10)

        self.btn_copy = QPushButton("Скопировать текст", footer)
        self.btn_copy.setFixedSize(140, 30)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setFont(get_body_font(9))
        self.btn_copy.setStyleSheet("""
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
        self.btn_copy.clicked.connect(self._copy_text)
        f_layout.addWidget(self.btn_copy)

        self.btn_web = QPushButton("Открыть на GitHub", footer)
        self.btn_web.setFixedSize(140, 30)
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.setFont(get_body_font(9))
        self.btn_web.setStyleSheet(self.btn_copy.styleSheet())
        self.btn_web.clicked.connect(self._open_web)
        f_layout.addWidget(self.btn_web)

        f_layout.addStretch()

        btn_close_dlg = QPushButton("Закрыть", footer)
        btn_close_dlg.setFixedSize(90, 30)
        btn_close_dlg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close_dlg.setFont(get_body_font(9, demi_bold=True))
        btn_close_dlg.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #121214;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E6E6EE;
            }
        """)
        btn_close_dlg.clicked.connect(self.close)
        f_layout.addWidget(btn_close_dlg)

        c_layout.addWidget(footer)

    def _switch_doc(self, tab_idx: int):
        self._current_tab = tab_idx
        if tab_idx == 0:
            self.btn_tab_privacy.setStyleSheet("background-color: #0A3871; color: #FFFFFF; border: none; border-radius: 6px; padding: 0 12px;")
            self.btn_tab_terms.setStyleSheet("background-color: transparent; color: #8E8E98; border: none; padding: 0 12px;")
            self.lbl_doc.setText(self._privacy_html)
        else:
            self.btn_tab_privacy.setStyleSheet("background-color: transparent; color: #8E8E98; border: none; padding: 0 12px;")
            self.btn_tab_terms.setStyleSheet("background-color: #0A3871; color: #FFFFFF; border: none; border-radius: 6px; padding: 0 12px;")
            self.lbl_doc.setText(self._terms_html)

    def _copy_text(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.lbl_doc.text())
            self.btn_copy.setText("Скопировано")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("Скопировать текст"))

    def _open_web(self):
        if self._current_tab == 0:
            webbrowser.open("https://github.com/wesiks/VoiceTyping/blob/main/PRIVACY.md")
        else:
            webbrowser.open("https://github.com/wesiks/VoiceTyping/blob/main/TERMS.md")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 50:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
