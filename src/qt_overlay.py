import math
import sys
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics, QLinearGradient, QPainterPath

from themes import get_theme
from font_loader import get_app_font

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
    def __init__(self, theme_id: str = "claude"):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        # Dimensions & padding for multi-layer floating drop shadow
        self.pad_x = 24
        self.pad_y = 20
        self.card_w = 520
        self.card_h = 48
        self.radius = 24
        
        self.win_w = self.card_w + (self.pad_x * 2)
        self.win_h = self.card_h + (self.pad_y * 2)
        
        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()
        
        self.pos_x = (self.screen_w - self.win_w) // 2
        self.target_y = self.screen_h - self.win_h - 45
        self.hidden_y = self.screen_h + 15
        
        self.setGeometry(self.pos_x, self.hidden_y, self.win_w, self.win_h)
        
        # Theme
        self.theme = get_theme(theme_id)
        
        # State
        self.state = "idle"  # "recording", "processing", "done"
        self.display_text = "Слушаю..."
        self.target_level = 0.0
        self.current_level = 0.0
        self.phase = 0.0
        
        # 60 FPS physics & wave animation timer
        self.physics_timer = QTimer(self)
        self.physics_timer.setInterval(16)
        self.physics_timer.timeout.connect(self._physics_step)
        self.physics_timer.start()
        
        # Auto-hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_hud)
        
        # Slide animations
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(190)
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_theme(self, theme_id: str):
        """Switches visual theme in real-time."""
        self.theme = get_theme(theme_id)
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
        self.target_level = 0.0
        self.update()

    def show_done(self, final_text: str):
        self.state = "done"
        self.target_level = 0.0
        if final_text:
            self.display_text = final_text.strip()
        self.update()
        self.hide_timer.start(800)

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
        
        # 1. Soft Layered Floating Shadows
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
        painter.drawRoundedRect(card_rect.adjusted(-2, 3, 2, 7), self.radius + 1, self.radius + 1)
        
        painter.setBrush(QBrush(QColor(0, 0, 0, 45)))
        painter.drawRoundedRect(card_rect.adjusted(-1, 1, 1, 4), self.radius, self.radius)
        
        # 2. Dynamic Ambient Glow & Border from Theme
        t = self.theme
        if self.state == "recording":
            glow_c = QColor(*t["glow"])
            border_c = QColor(*t["border"])
        elif self.state == "processing":
            glow_c = QColor(139, 92, 246, 35)
            border_c = QColor(167, 139, 250, 190)
        elif self.state == "done":
            glow_c = QColor(16, 185, 129, 35)
            border_c = QColor(52, 211, 153, 190)
        else:
            glow_c = QColor(0, 0, 0, 0)
            border_c = QColor(255, 255, 255, 28)

        if glow_c.alpha() > 0:
            painter.setBrush(QBrush(glow_c))
            painter.drawRoundedRect(card_rect.adjusted(-2, -2, 2, 2), self.radius + 2, self.radius + 2)

        # 3. Main Card Body
        bg_c = QColor(*t["card_bg"])
        painter.setPen(QPen(border_c, 1.2))
        painter.setBrush(QBrush(bg_c))
        painter.drawRoundedRect(card_rect, self.radius, self.radius)
        
        # 4. Top Specular Bevel
        top_grad = QLinearGradient(0, card_rect.top() + 1, 0, card_rect.top() + 14)
        top_grad.setColorAt(0.0, QColor(255, 255, 255, 40))
        top_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(top_grad))
        painter.drawRoundedRect(card_rect.adjusted(2, 1, -2, -22), self.radius - 1, self.radius - 1)

        # 5. Dynamic Organic Waveform or Vector Indicators (Zero Emojis)
        center_y = card_rect.center().y()
        start_x = card_rect.left() + 20.0
        gap = 5.2
        bar_w = 2.8
        
        if self.state == "recording":
            max_swing = 22.0
            base_h = 4.0
            
            bar_colors = [QColor(*rgb) for rgb in t["bar_colors"]]
            wave_offsets = [0.0, 0.75, 1.5, 2.25, 3.0]
            center_weights = [0.55, 0.85, 1.0, 0.85, 0.55]
            
            for i in range(5):
                wave_factor = 0.5 + 0.5 * math.sin(self.phase + wave_offsets[i])
                active_h = (self.current_level * max_swing * center_weights[i]) * (0.6 + 0.4 * wave_factor)
                h = max(base_h, base_h + active_h)
                
                bx = start_x + (i * gap)
                by = center_y - (h / 2.0)
                
                painter.setBrush(QBrush(bar_colors[i]))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bx, by, bar_w, h), 1.4, 1.4)
                
        elif self.state == "processing":
            # Clean vector pulsing ring
            cx = card_rect.left() + 30.0
            cy = center_y
            pulse_r = 5.0 + 1.5 * math.sin(self.phase * 1.5)
            painter.setPen(QPen(QColor(167, 139, 250), 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(pulse_r), int(pulse_r))
            
        elif self.state == "done":
            # Clean vector checkmark path
            cx = card_rect.left() + 30.0
            cy = center_y
            painter.setPen(QPen(QColor(52, 211, 153), 2.0, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(cx - 5.0, cy)
            path.lineTo(cx - 1.0, cy + 4.0)
            path.lineTo(cx + 6.0, cy - 4.0)
            painter.drawPath(path)

        # 6. Live Text (Zero Emojis, Clean Typography)
        text_x = card_rect.left() + 54
        text_w = self.card_w - 54 - 20
        text_rect = QRectF(text_x, card_rect.top(), text_w, self.card_h)
        
        font = get_app_font(11, demi_bold=False)
        painter.setFont(font)
        
        if self.state == "recording" and self.display_text == "Слушаю...":
            painter.setPen(QColor(135, 135, 145))
        else:
            painter.setPen(QColor(*t["text"]))
            
        fm = QFontMetrics(font)
        elided = fm.elidedText(self.display_text, Qt.TextElideMode.ElideLeft, int(text_w))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
