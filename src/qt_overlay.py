import math
import sys
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics, QLinearGradient, QPainterPath

from themes import get_theme
from font_loader import get_body_font, get_mono_font

class AudioSignalBridge(QObject):
    """Thread-safe signal bridge between audio threads and Qt UI."""
    sig_recording_started = pyqtSignal()
    sig_live_text = pyqtSignal(str)
    sig_audio_level = pyqtSignal(float)
    sig_processing = pyqtSignal()
    sig_done = pyqtSignal(str)
    sig_hide = pyqtSignal()
    sig_theme_changed = pyqtSignal(str)

class ModernHUD(QWidget):
    def __init__(self, theme_id: str = "claude", hotkey: str = "F8"):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.pad_x = 24.0
        self.pad_y = 20.0
        self.card_w = 400.0
        self.card_h = 44.0
        self.radius = 22.0
        
        self.win_w = int(self.card_w + (self.pad_x * 2))
        self.win_h = int(self.card_h + (self.pad_y * 2))
        
        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()
        
        self.pos_x = (self.screen_w - self.win_w) // 2
        self.target_y = self.screen_h - self.win_h - 45
        self.hidden_y = self.screen_h + 15
        
        self.setGeometry(self.pos_x, self.hidden_y, self.win_w, self.win_h)

        self.theme = get_theme(theme_id)
        self.hotkey_str = hotkey.upper().strip()

        self.state = "idle"
        self.display_text = "Слушаю..."
        self.target_level = 0.0
        self.current_level = 0.0
        self.phase = 0.0

        self.physics_timer = QTimer(self)
        self.physics_timer.setInterval(16)
        self.physics_timer.timeout.connect(self._physics_step)
        self.physics_timer.start()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_hud)

        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(190)
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_theme(self, theme_id: str):
        """Switches visual theme in real-time."""
        self.theme = get_theme(theme_id)
        self.update()

    def set_hotkey(self, hotkey: str):
        """Updates active hotkey badge text."""
        if hotkey:
            self.hotkey_str = hotkey.upper().strip()
            self.update()

    def _physics_step(self):
        """Dynamic 60 FPS wave physics and level interpolation."""
        self.phase += 0.22
        if self.phase > 1000.0:
            self.phase = 0.0

        if self.state == "recording":
            self.current_level += (self.target_level - self.current_level) * 0.40
        else:
            self.current_level += (0.0 - self.current_level) * 0.28

        if self.isVisible():
            self.update()

    def set_audio_level(self, level: float):
        self.target_level = max(0.0, min(1.0, level))

    def show_recording(self):
        self.hide_timer.stop()
        self.state = "recording"
        self.display_text = "Слушаю..."
        self.target_level = 0.0
        self.current_level = 0.0
        
        self.show()
        
        self.pos_anim.stop()
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(self.pos_x, self.target_y))
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.pos_anim.start()
        self.update()

    def update_live_text(self, formatted_text: str):
        if formatted_text:
            self.display_text = formatted_text.strip()
            self.update()

    def show_processing(self):
        self.state = "processing"
        self.display_text = "Обработка..."
        self.target_level = 0.0
        self.update()

    def show_done(self, final_text: str):
        self.state = "done"
        self.target_level = 0.0
        if final_text:
            self.display_text = final_text.strip()
        self.update()
        self.hide_timer.start(1600)

    def show_greeting(self, hotkey: str = None):
        """Shows instant visual feedback on startup matching mockup 1."""
        self.hide_timer.stop()
        if hotkey:
            if "•" in hotkey or "готов" in hotkey.lower():
                parts = hotkey.split()
                self.hotkey_str = parts[-1].upper().strip()
            else:
                self.hotkey_str = hotkey.upper().strip()
        self.state = "greeting"
        self.display_text = "VoiceTyping готов • "
        self.target_level = 0.0
        self.show()
        
        self.pos_anim.stop()
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(self.pos_x, self.target_y))
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.pos_anim.start()
        self.update()
        self.hide_timer.start(2600)

    def hide_hud(self):
        self.state = "idle"
        self.pos_anim.stop()
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(self.pos_x, self.hidden_y))
        self.pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.pos_anim.finished.connect(self._on_slide_down_finished)
        self.pos_anim.start()

    def _on_slide_down_finished(self):
        try:
            self.pos_anim.finished.disconnect(self._on_slide_down_finished)
        except Exception:
            pass
        if self.state == "idle":
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        card_rect = QRectF(self.pad_x, self.pad_y, self.card_w, self.card_h)

        # 1. Subtle drop shadow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 90)))
        painter.drawRoundedRect(card_rect.adjusted(-1, 2, 1, 5), self.radius, self.radius)

        # 2. Card background and border
        t = self.theme
        bg_color = QColor(*t["card_bg"])
        border_color = QColor(255, 255, 255, 20)
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(card_rect, self.radius, self.radius)

        accent = QColor(t.get("accent", "#E2555F"))
        dim_dot = QColor(58, 58, 69)
        gray_dot = QColor(101, 100, 109)

        center_y = card_rect.center().y()
        start_x = card_rect.left() + 20.0
        dot_step = 5.8
        bar_w = 2.6

        # 3. Left 5 indicators
        if self.state == "recording":
            max_swing = 15.0
            base_h = 4.6
            wave_offsets = [0.0, 0.75, 1.5, 2.25, 3.0]
            center_weights = [0.50, 0.85, 1.0, 0.85, 0.50]
            for i in range(5):
                wave_factor = 0.5 + 0.5 * math.sin(self.phase + wave_offsets[i])
                active_h = (self.current_level * max_swing * center_weights[i]) * (0.6 + 0.4 * wave_factor)
                h = max(base_h, base_h + active_h)
                bx = start_x + (i * dot_step)
                by = center_y - (h / 2.0)
                painter.setBrush(QBrush(accent))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bx, by, bar_w, h), 1.3, 1.3)
        else:
            h = 5.0
            for i in range(5):
                bx = start_x + (i * dot_step)
                by = center_y - (h / 2.0)
                painter.setBrush(QBrush(dim_dot))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bx, by, bar_w, h), 1.3, 1.3)

        # 4. Right status indicators
        right_dot_x = card_rect.right() - 37.0
        right_icon_x = card_rect.right() - 19.5
        dot_r = 4.8

        right_margin = 44.0

        if self.state == "greeting":
            # Single gray dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gray_dot))
            painter.drawEllipse(QRectF(card_rect.right() - 24.0 - dot_r, center_y - dot_r, dot_r * 2, dot_r * 2))
            right_margin = 38.0

        elif self.state == "recording":
            # Accent dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawEllipse(QRectF(right_dot_x - dot_r, center_y - dot_r, dot_r * 2, dot_r * 2))

            # Mic outline icon
            painter.setPen(QPen(accent, 1.35, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mic_w = 4.6
            mic_h = 7.6
            painter.drawRoundedRect(QRectF(right_icon_x - mic_w / 2, center_y - 6.5, mic_w, mic_h), mic_w / 2, mic_w / 2)
            bracket_w = 8.4
            bracket_h = 7.6
            p_bracket = QPainterPath()
            p_bracket.arcMoveTo(QRectF(right_icon_x - bracket_w / 2, center_y - 4.2, bracket_w, bracket_h), 180)
            p_bracket.arcTo(QRectF(right_icon_x - bracket_w / 2, center_y - 4.2, bracket_w, bracket_h), 180, -180)
            painter.drawPath(p_bracket)
            painter.drawLine(QPoint(int(right_icon_x), int(center_y + 3.4)), QPoint(int(right_icon_x), int(center_y + 5.8)))
            painter.drawLine(QPoint(int(right_icon_x - 2.8), int(center_y + 5.8)), QPoint(int(right_icon_x + 2.8), int(center_y + 5.8)))
            right_margin = 56.0

        elif self.state == "processing":
            # Gray dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gray_dot))
            painter.drawEllipse(QRectF(right_dot_x - dot_r, center_y - dot_r, dot_r * 2, dot_r * 2))

            # Spinner ring
            spinner_r = 5.8
            s_rect = QRectF(right_icon_x - spinner_r, center_y - spinner_r, spinner_r * 2, spinner_r * 2)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(42, 42, 54), 1.5))
            painter.drawEllipse(s_rect)
            painter.setPen(QPen(accent, 1.5, cap=Qt.PenCapStyle.RoundCap))
            start_angle = int((self.phase * 240) % 360 * 16)
            painter.drawArc(s_rect, start_angle, 100 * 16)
            right_margin = 56.0

        elif self.state == "done":
            # Accent dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawEllipse(QRectF(right_dot_x - dot_r, center_y - dot_r, dot_r * 2, dot_r * 2))

            # Checkmark
            painter.setPen(QPen(accent, 1.7, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            p_chk = QPainterPath()
            p_chk.moveTo(right_icon_x - 3.4, center_y + 0.1)
            p_chk.lineTo(right_icon_x - 0.7, center_y + 3.0)
            p_chk.lineTo(right_icon_x + 4.2, center_y - 2.8)
            painter.drawPath(p_chk)
            right_margin = 56.0

        # 5. Center Text
        text_x = start_x + (4 * dot_step) + bar_w + 14.0
        text_w = card_rect.right() - right_margin - text_x

        font = get_body_font(10, demi_bold=True)
        painter.setFont(font)
        fm = QFontMetrics(font)

        if self.state == "greeting":
            prefix = "VoiceTyping готов • "
            painter.setPen(QColor("#E4E4EC"))
            p_w = fm.horizontalAdvance(prefix)
            painter.drawText(QRectF(text_x, card_rect.top(), p_w, self.card_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, prefix)

            # Draw hotkey badge
            badge_x = text_x + p_w + 2.0
            badge_text = self.hotkey_str
            b_font = get_mono_font(9, bold=True)
            b_fm = QFontMetrics(b_font)
            bw = b_fm.horizontalAdvance(badge_text) + 12.0
            bh = 19.0
            badge_rect = QRectF(badge_x, center_y - (bh / 2.0), bw, bh)

            painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255, 14)))
            painter.drawRoundedRect(badge_rect, 4.0, 4.0)

            painter.setFont(b_font)
            painter.setPen(QColor("#C8C8D4"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        else:
            painter.setPen(QColor("#E4E4EC"))
            elided = fm.elidedText(self.display_text, Qt.TextElideMode.ElideRight, int(text_w))
            text_rect = QRectF(text_x, card_rect.top(), text_w, self.card_h)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
