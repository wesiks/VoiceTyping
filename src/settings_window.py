import os
import sys
import math
import random
import shutil
import threading
import requests
import webbrowser
import sounddevice as sd
import numpy as np
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QFrame, QStackedWidget,
    QProgressBar, QSlider, QApplication, QScrollArea
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QPoint, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QFontMetrics, QPainterPath,
    QIcon, QPixmap, QLinearGradient
)

from app_settings import load_settings, save_settings, set_windows_autostart, get_app_data_dir
from updater import APP_VERSION, check_github_update, open_release_page
from font_loader import get_title_font, get_subtitle_font, get_body_font, get_mono_font
from legal_dialog import LegalDocsDialog
from app_logger import open_logs_folder

def get_app_icon_path() -> Path | None:
    """Finds app.ico across development and PyInstaller bundled environments."""
    candidates = [
        Path(__file__).resolve().parent / "app.ico",
        Path(__file__).resolve().parent.parent / "app.ico",
        Path(sys.executable).resolve().parent / "app.ico",
        Path(sys.executable).resolve().parent / "_internal" / "app.ico",
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / "app.ico")
    for p in candidates:
        if p.exists():
            return p
    return None

def get_app_icon() -> QIcon:
    """Returns application QIcon using app.ico or vector fallback."""
    p = get_app_icon_path()
    if p and p.exists():
        ico = QIcon(str(p))
        if not ico.isNull():
            return ico
    from tray_icon import create_app_icon
    return create_app_icon()

class MicLevelMonitor(QObject):
    """Monitors live microphone volume with smooth float precision for settings test meter."""
    level_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stream = None
        self._is_running = False
        self._lock = threading.Lock()

    def start(self, device_idx=None):
        self.stop()
        with self._lock:
            self._is_running = True

            def _audio_cb(indata, frames, time_info, status):
                if not self._is_running:
                    return
                try:
                    float_data = indata.astype(np.float32) / 32768.0
                    rms = float(np.sqrt(np.mean(float_data ** 2)))
                    scaled = min(1.0, rms * 14.0)
                    level = float(np.power(scaled, 0.75))
                    self.level_changed.emit(level)
                except Exception:
                    pass

            try:
                self._stream = sd.InputStream(
                    samplerate=16000,
                    channels=1,
                    dtype="int16",
                    blocksize=1200,
                    device=device_idx,
                    callback=_audio_cb
                )
                self._stream.start()
            except Exception:
                self._stream = None
                self._is_running = False

    def stop(self):
        with self._lock:
            self._is_running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
        self.level_changed.emit(0.0)


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
    """Custom pixel-perfect dark checkbox with vector checkmark and clean text antialiasing."""
    def __init__(self, text: str, default_checked: bool = False, parent=None):
        super().__init__(text, parent)
        self.setChecked(default_checked)
        self.setFont(get_body_font(10))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        box_size = 18.0
        box_y = (rect.height() - box_size) / 2.0
        box_rect = QRectF(2.0, box_y, box_size, box_size)

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 120, 212)))
            painter.drawRoundedRect(box_rect, 4.0, 4.0)

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

        painter.setFont(self.font())
        painter.setPen(QColor("#E6E6EE"))
        text_rect = QRectF(28.0, 0, rect.width() - 30.0, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

class AppLogoWidget(QWidget):
    """Shows the official high-resolution orange app icon badge in 'About'."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self._pixmap = None
        icon_p = get_app_icon_path()
        if icon_p:
            ico = QIcon(str(icon_p))
            if not ico.isNull():
                self._pixmap = ico.pixmap(128, 128)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if self._pixmap and not self._pixmap.isNull():
            p = QPainterPath()
            p.addRoundedRect(rect, 16.0, 16.0)
            painter.setClipPath(p)
            painter.drawPixmap(rect.toRect(), self._pixmap)
        else:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor("#FF7A29"))
            grad.setColorAt(1.0, QColor("#E5501B"))
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1.2))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(rect, 16.0, 16.0)

            cx = rect.center().x()
            cy = rect.center().y()
            painter.setPen(QPen(QColor(255, 255, 255), 2.2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            mic_w = 9.0
            mic_h = 15.0
            painter.drawRoundedRect(QRectF(cx - mic_w/2, cy - 11.0, mic_w, mic_h), mic_w/2, mic_w/2)

            p_bracket = QPainterPath()
            p_bracket.arcMoveTo(QRectF(cx - 8.5, cy - 6.5, 17.0, 14.5), 180)
            p_bracket.arcTo(QRectF(cx - 8.5, cy - 6.5, 17.0, 14.5), 180, -180)
            painter.drawPath(p_bracket)

            painter.drawLine(QPoint(int(cx), int(cy + 8.0)), QPoint(int(cx), int(cy + 13.0)))
            painter.drawLine(QPoint(int(cx - 5.5), int(cy + 13.0)), QPoint(int(cx + 5.5), int(cy + 13.0)))

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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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

        p = QPainterPath()
        p.moveTo(cx - 8.0, cy)
        p.quadTo(cx, cy - 5.5, cx + 8.0, cy)
        p.quadTo(cx, cy + 5.5, cx - 8.0, cy)
        painter.drawPath(p)

        painter.setBrush(QBrush(c))
        painter.drawEllipse(QRectF(cx - 2.2, cy - 2.2, 4.4, 4.4))

        if not self.is_open:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPoint(int(cx - 6.5), int(cy + 5.5)), QPoint(int(cx + 6.5), int(cy - 5.5)))

class SmoothMicMeter(QWidget):
    """High-FPS studio volume meter with animated pulsing microphone icon."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self._target_level = 0.0
        self._current_level = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._physics_step)
        self._timer.start()

    def set_target_level(self, level: float):
        val = float(level)
        if val > 1.0:
            val = val / 100.0
        self._target_level = max(0.0, min(1.0, val))

    def _physics_step(self):
        if not self.isVisible():
            return
        if self._target_level > self._current_level:
            self._current_level += (self._target_level - self._current_level) * 0.25
        else:
            self._current_level += (self._target_level - self._current_level) * 0.08

        if abs(self._target_level - self._current_level) < 0.002 and self._target_level == 0.0:
            self._current_level = 0.0

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cy = h / 2.0

        mic_cx = 12.0
        active_ratio = min(1.0, self._current_level * 1.8)
        pulse = 1.0 + active_ratio * 0.12

        r = int(142 + (16 - 142) * active_ratio)
        g = int(142 + (185 - 142) * active_ratio)
        b = int(152 + (129 - 152) * active_ratio)
        icon_c = QColor(r, g, b)

        painter.setPen(QPen(icon_c, 1.4 * pulse, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        mic_w = 4.6 * pulse
        mic_h = 7.4 * pulse
        painter.drawRoundedRect(QRectF(mic_cx - mic_w/2, cy - 6.2, mic_w, mic_h), mic_w/2, mic_w/2)

        p = QPainterPath()
        p.arcMoveTo(QRectF(mic_cx - 4.4, cy - 3.8, 8.8, 7.6), 180)
        p.arcTo(QRectF(mic_cx - 4.4, cy - 3.8, 8.8, 7.6), 180, -180)
        painter.drawPath(p)

        painter.drawLine(QPoint(int(mic_cx), int(cy + 3.8)), QPoint(int(mic_cx), int(cy + 6.2)))
        painter.drawLine(QPoint(int(mic_cx - 2.8), int(cy + 6.2)), QPoint(int(mic_cx + 2.8), int(cy + 6.2)))

        bar_x = 30.0
        bar_w = w - bar_x - 4.0
        bar_h = 6.0
        bar_y = cy - (bar_h / 2.0)
        bar_rect = QRectF(bar_x, bar_y, bar_w, bar_h)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#202026")))
        painter.drawRoundedRect(bar_rect, 3.0, 3.0)

        fill_w = max(0.0, min(bar_w, bar_w * self._current_level))
        if fill_w > 1.0:
            fill_rect = QRectF(bar_x, bar_y, fill_w, bar_h)
            grad = QLinearGradient(bar_rect.topLeft(), bar_rect.topRight())
            grad.setColorAt(0.0, QColor("#059669"))
            grad.setColorAt(0.65, QColor("#10B981"))
            grad.setColorAt(1.0, QColor("#34D399"))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(fill_rect, 3.0, 3.0)

class SidebarNavButton(QPushButton):
    """Custom sidebar button with clean vector icon and pill selection."""
    def __init__(self, icon_type: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.button_text = text
        self.is_active = False
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_body_font(10, demi_bold=True))

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

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

        painter.setFont(self.font())
        painter.setPen(text_color)
        text_rect = QRectF(42.0, 0, rect.width() - 48.0, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.button_text)

class CustomThemeCard(QPushButton):
    """Widget theme card matching mockups."""
    def __init__(self, theme_id: str, title: str, dot_color: str, is_active=False, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self.card_title = title
        self.dot_color = QColor(dot_color)
        self.is_active = is_active
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QColor(24, 24, 28)
        if self.is_active:
            border = QPen(QColor(10, 88, 180), 1.8)
        else:
            border = QPen(QColor(255, 255, 255, 18), 1.0)

        painter.setPen(border)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        cx = rect.center().x()
        cy = rect.top() + 18.0
        r = 6.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.dot_color))
        painter.drawEllipse(QRectF(cx - r, cy - r, r*2, r*2))

        painter.setFont(get_body_font(9, demi_bold=True))
        painter.setPen(QColor("#FFFFFF" if self.is_active else "#C4C4CE"))
        text_rect = QRectF(rect.left(), rect.top() + 28.0, rect.width(), 20.0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.card_title)


class Snowflake:
    """Individual snowflake with realistic drifting, swaying and depth."""
    def __init__(self, w: float, h: float, initial: bool = True):
        self.w = max(100.0, float(w))
        self.h = max(100.0, float(h))
        self.x = 0.0
        self.y = 0.0
        self.radius = 2.0
        self.speed_y = 1.0
        self.sway_speed = 0.03
        self.sway_amp = 0.8
        self.sway_phase = 0.0
        self.alpha = 180
        self.reset(self.w, self.h, top_only=not initial)

    def reset(self, w: float, h: float, top_only: bool = True):
        self.w = max(100.0, float(w))
        self.h = max(100.0, float(h))
        self.x = random.uniform(4.0, self.w - 4.0)
        if top_only:
            self.y = random.uniform(-25.0, -4.0)
        else:
            self.y = random.uniform(0.0, self.h)

        depth = random.random()
        if depth < 0.5:
            self.radius = random.uniform(1.2, 2.0)
            self.speed_y = random.uniform(0.6, 1.2)
            self.sway_amp = random.uniform(0.4, 0.9)
            self.alpha = random.randint(70, 130)
        elif depth < 0.85:
            self.radius = random.uniform(2.0, 3.2)
            self.speed_y = random.uniform(1.1, 1.8)
            self.sway_amp = random.uniform(0.8, 1.4)
            self.alpha = random.randint(130, 200)
        else:
            self.radius = random.uniform(3.2, 4.4)
            self.speed_y = random.uniform(1.7, 2.5)
            self.sway_amp = random.uniform(1.2, 2.0)
            self.alpha = random.randint(180, 240)

        self.sway_speed = random.uniform(0.02, 0.05)
        self.sway_phase = random.uniform(0.0, math.pi * 2)

    def update(self, w: float, h: float):
        self.w = max(100.0, float(w))
        self.h = max(100.0, float(h))
        self.y += self.speed_y
        self.sway_phase += self.sway_speed
        self.x += math.sin(self.sway_phase) * self.sway_amp

        if self.y > self.h + 10 or self.x < -15 or self.x > self.w + 15:
            self.reset(self.w, self.h, top_only=True)


class SnowEffectWidget(QWidget):
    """Transparent overlay that renders a smooth, festive snowfall animation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

        self._snowflakes: list[Snowflake] = []
        self._flake_count = 55
        self._is_active = False

        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._tick)

    def _init_flakes(self):
        w = float(self.width()) if self.width() > 50 else 650.0
        h = float(self.height()) if self.height() > 50 else 680.0
        self._snowflakes = [Snowflake(w, h, initial=True) for _ in range(self._flake_count)]

    def start(self):
        self._is_active = True
        if not self._snowflakes:
            self._init_flakes()
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self):
        self._is_active = False
        if self._timer.isActive():
            self._timer.stop()
        self.hide()

    def _tick(self):
        if not self.isVisible() or not self._is_active:
            return
        w = float(self.width())
        h = float(self.height())
        for flake in self._snowflakes:
            flake.update(w, h)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._snowflakes and self.width() > 50:
            self._init_flakes()

    def paintEvent(self, event):
        if not self._is_active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        for flake in self._snowflakes:
            painter.setBrush(QBrush(QColor(245, 248, 255, flake.alpha)))
            painter.drawEllipse(QPointF(flake.x, flake.y), flake.radius, flake.radius)
            if flake.radius > 3.0:
                painter.setBrush(QBrush(QColor(255, 255, 255, min(255, flake.alpha + 45))))
                painter.drawEllipse(QPointF(flake.x, flake.y), flake.radius * 0.45, flake.radius * 0.45)


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
        self.setWindowIcon(get_app_icon())

        self.settings = load_settings()
        self._drag_pos = None
        self._is_listening_hotkey = False
        self.mic_monitor = MicLevelMonitor(self)

        self._init_ui()
        self._load_values()

        self.mic_monitor.level_changed.connect(self.mic_meter.set_target_level)
        self.cmb_mic.currentIndexChanged.connect(self._on_mic_device_changed)

        self.snow_widget = SnowEffectWidget(self.container)
        self.snow_widget.setGeometry(self.container.rect())
        if self.settings.get("snow_enabled", True):
            self.snow_widget.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self.stack.currentIndex() == 0:
            self.mic_monitor.start(self.cmb_mic.currentData())
        if hasattr(self, "snow_widget"):
            self.snow_widget.setGeometry(self.container.rect())
            self.snow_widget.raise_()
            if self.settings.get("snow_enabled", True):
                self.snow_widget.start()

    def hideEvent(self, event):
        self.mic_monitor.stop()
        if hasattr(self, "snow_widget"):
            self.snow_widget.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.mic_monitor.stop()
        if hasattr(self, "snow_widget"):
            self.snow_widget.stop()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "snow_widget") and hasattr(self, "container"):
            self.snow_widget.setGeometry(self.container.rect())
            self.snow_widget.raise_()

    def _on_mic_device_changed(self):
        if self.stack.currentIndex() == 0 and self.isVisible():
            self.mic_monitor.start(self.cmb_mic.currentData())


    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(f"""
            QFrame#container {{
                background-color: #121214;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                font-family: "{get_body_font().family()}";
            }}
        """)
        root_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        header = QFrame(self.container)
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 16, 0)
        header_layout.setSpacing(10)

        header_icon = QLabel(header)
        header_icon.setFixedSize(22, 22)
        header_icon.setScaledContents(True)
        header_icon.setPixmap(get_app_icon().pixmap(32, 32))
        header_layout.addWidget(header_icon)

        title_lbl = QLabel("VoiceTyping", header)
        title_lbl.setFont(get_title_font(12, bold=True))
        title_lbl.setStyleSheet("color: #FFFFFF;")

        ver_lbl = QLabel(f"v{APP_VERSION}", header)
        ver_lbl.setFont(get_body_font(10))
        ver_lbl.setStyleSheet("color: #70707B; margin-left: 2px;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(ver_lbl)
        header_layout.addStretch()

        self.btn_snow = QPushButton("❄", header)
        self.btn_snow.setFixedSize(28, 28)
        self.btn_snow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_snow.setToolTip("Эффект снегопада")
        self.btn_snow.clicked.connect(self._toggle_snow)
        header_layout.addWidget(self.btn_snow)

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

        sep_top = QFrame(self.container)
        sep_top.setFixedHeight(1)
        sep_top.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        container_layout.addWidget(sep_top)

        body = QFrame(self.container)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

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

        sep_mid = QFrame(body)
        sep_mid.setFixedWidth(1)
        sep_mid.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        body_layout.addWidget(sep_mid)

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

        sep_bot = QFrame(self.container)
        sep_bot.setFixedHeight(1)
        sep_bot.setStyleSheet("background-color: rgba(255, 255, 255, 0.07);")
        container_layout.addWidget(sep_bot)

        footer = QFrame(self.container)
        footer.setFixedHeight(56)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_status = QLabel("Установлена последняя версия", footer)
        self.lbl_status.setFont(get_body_font(10))
        self.lbl_status.setStyleSheet("color: #34D399;")

        self.btn_close_footer = QPushButton("Закрыть", footer)
        self.btn_close_footer.setFixedSize(96, 32)
        self.btn_close_footer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_footer.setFont(get_body_font(10))
        self.btn_close_footer.setStyleSheet("""
            QPushButton {
                background-color: #1E1E24;
                color: #C8C8D4;
                border: 1px solid #2C2C38;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #282832;
                color: #FFFFFF;
                border-color: #3E3E4C;
            }
        """)
        self.btn_close_footer.clicked.connect(self.close)

        self.btn_save = QPushButton("Сохранить", footer)
        self.btn_save.setFixedSize(126, 32)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setFont(get_body_font(10, demi_bold=True))
        self._btn_save_default_style = """
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
        """
        self.btn_save.setStyleSheet(self._btn_save_default_style)
        self.btn_save.clicked.connect(self._save_settings)

        footer_layout.addWidget(self.lbl_status)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_close_footer)
        footer_layout.addWidget(self.btn_save)

        container_layout.addWidget(footer)

        self._switch_tab(0)


    def _create_recording_page(self) -> QWidget:
        """Tab 1: Запись (Mockup 4)"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #282834; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(12)

        lbl_engine = QLabel("Движок распознавания", w)
        lbl_engine.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_engine.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_engine)

        self.cmb_engine = QComboBox(w)
        self.cmb_engine.setFixedHeight(38)
        self.cmb_engine.setFont(get_body_font(10))
        self.cmb_engine.setStyleSheet("""
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
        self.cmb_engine.addItem("Умный гибрид (Groq Cloud + Vosk)", "auto")
        self.cmb_engine.addItem("Только офлайн (Vosk — без интернета)", "vosk")
        self.cmb_engine.addItem("Только облако (Groq Cloud)", "groq")
        self.cmb_engine.currentIndexChanged.connect(self._on_engine_changed)
        layout.addWidget(self.cmb_engine)

        lbl_api = QLabel("Groq API", w)
        lbl_api.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_api.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_api)

        api_row = QHBoxLayout()
        api_row.setSpacing(10)

        self.inp_api = QLineEdit(w)
        self.inp_api.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_api.setFixedHeight(38)
        self.inp_api.setFont(get_body_font(10))
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
        self.btn_check_api.setFont(get_body_font(10, demi_bold=True))
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
        lbl_api_link.setFont(get_body_font(10))
        lbl_api_link.setOpenExternalLinks(True)
        layout.addWidget(lbl_api_link)

        self.lbl_api_hint = QLabel(w)
        self.lbl_api_hint.setFont(get_body_font(9))
        self.lbl_api_hint.setWordWrap(True)
        self.lbl_api_hint.setStyleSheet("color: #F87171; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 6px 10px;")
        self.lbl_api_hint.hide()
        layout.addWidget(self.lbl_api_hint)

        self.btn_toggle_network = QPushButton("Настройки прокси и сети ▾", w)
        self.btn_toggle_network.setFixedHeight(24)
        self.btn_toggle_network.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_network.setFont(get_body_font(9))
        self.btn_toggle_network.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8E8E98;
                border: none;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_network.clicked.connect(self._toggle_network_frame)
        layout.addWidget(self.btn_toggle_network)

        self.frame_network = QFrame(w)
        self.frame_network.setStyleSheet("background: #16161A; border: 1px solid #282830; border-radius: 8px;")
        fn_layout = QVBoxLayout(self.frame_network)
        fn_layout.setContentsMargins(12, 10, 12, 10)
        fn_layout.setSpacing(6)

        lbl_proxy = QLabel("Прокси (HTTP / SOCKS5, опционально):", self.frame_network)
        lbl_proxy.setFont(get_body_font(9))
        lbl_proxy.setStyleSheet("color: #A4A4B0; border: none;")
        fn_layout.addWidget(lbl_proxy)

        self.inp_proxy = QLineEdit(self.frame_network)
        self.inp_proxy.setPlaceholderText("http://127.0.0.1:10808 или socks5://...")
        self.inp_proxy.setFixedHeight(30)
        self.inp_proxy.setFont(get_body_font(9))
        self.inp_proxy.setStyleSheet("""
            QLineEdit {
                background-color: #1F1F24;
                color: #FFFFFF;
                border: 1px solid #30303A;
                border-radius: 6px;
                padding: 0 8px;
            }
            QLineEdit:focus {
                border-color: #0A58B4;
            }
        """)
        fn_layout.addWidget(self.inp_proxy)

        lbl_base_url = QLabel("Кастомный Base URL (опционально, для зеркал):", self.frame_network)
        lbl_base_url.setFont(get_body_font(9))
        lbl_base_url.setStyleSheet("color: #A4A4B0; border: none;")
        fn_layout.addWidget(lbl_base_url)

        self.inp_base_url = QLineEdit(self.frame_network)
        self.inp_base_url.setPlaceholderText("https://api.groq.com/openai/v1")
        self.inp_base_url.setFixedHeight(30)
        self.inp_base_url.setFont(get_body_font(9))
        self.inp_base_url.setStyleSheet(self.inp_proxy.styleSheet())
        fn_layout.addWidget(self.inp_base_url)

        self.frame_network.hide()
        layout.addWidget(self.frame_network)

        layout.addSpacing(4)

        lbl_mic = QLabel("Микрофон", w)
        lbl_mic.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_mic.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_mic)

        self.cmb_mic = QComboBox(w)
        self.cmb_mic.setFixedHeight(38)
        self.cmb_mic.setFont(get_body_font(10))
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

        self.mic_meter = SmoothMicMeter(w)
        layout.addWidget(self.mic_meter)

        layout.addSpacing(6)

        lbl_lang = QLabel("Язык распознавания", w)
        lbl_lang.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_lang.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_lang)

        self.cmb_lang = QComboBox(w)
        self.cmb_lang.setFixedHeight(38)
        self.cmb_lang.setFont(get_body_font(10))
        self.cmb_lang.setStyleSheet(self.cmb_mic.styleSheet())
        self.cmb_lang.addItem("Авто", "auto")
        self.cmb_lang.addItem("Русский (ru)", "ru")
        self.cmb_lang.addItem("English (en)", "en")
        layout.addWidget(self.cmb_lang)

        layout.addSpacing(6)

        lbl_proc = QLabel("Обработка текста", w)
        lbl_proc.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_proc.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_proc)

        self.cb_voice_punct = ModernCheckBox("Голосовая пунктуация", True, w)
        self.cb_trailing_space = ModernCheckBox("Завершающий пробел", False, w)
        layout.addWidget(self.cb_voice_punct)
        layout.addWidget(self.cb_trailing_space)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def _create_hotkeys_page(self) -> QWidget:
        """Tab 2: Горячие клавиши (Mockup 3)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(14)

        lbl_hk = QLabel("Клавиша записи", w)
        lbl_hk.setFont(get_subtitle_font(11, demi_bold=True))
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

        self.btn_rebind = QPushButton("Переназначить", w)
        self.btn_rebind.setFixedSize(145, 40)
        self.btn_rebind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rebind.setFont(get_body_font(10, demi_bold=True))
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
        lbl_hk_hint.setFont(get_body_font(9))
        lbl_hk_hint.setStyleSheet("color: #70707B;")
        layout.addWidget(lbl_hk_hint)

        layout.addSpacing(6)

        lbl_mode = QLabel("Режим активации", w)
        lbl_mode.setFont(get_subtitle_font(11, demi_bold=True))
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
            b.setFont(get_body_font(10, demi_bold=True))

        self.btn_mode_hold.clicked.connect(lambda: self._set_activation_mode("hold"))
        self.btn_mode_toggle.clicked.connect(lambda: self._set_activation_mode("toggle"))
        seg_layout.addWidget(self.btn_mode_hold)
        seg_layout.addWidget(self.btn_mode_toggle)
        layout.addWidget(seg_box)

        lbl_mode_hint = QLabel("«Удерживать» — запись идёт, пока клавиша зажата. «Одно нажатие» — старт и стоп разными нажатиями.", w)
        lbl_mode_hint.setWordWrap(True)
        lbl_mode_hint.setFont(get_body_font(9))
        lbl_mode_hint.setStyleSheet("color: #70707B;")
        layout.addWidget(lbl_mode_hint)

        layout.addSpacing(6)

        lbl_extra = QLabel("Дополнительные сочетания", w)
        lbl_extra.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_extra.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_extra)

        layout.addWidget(self._create_hotkey_card("Отменить последнюю запись", "Esc", w))
        layout.addWidget(self._create_hotkey_card("Открыть настройки", "Ctrl+Shift+V", w))

        layout.addSpacing(6)

        self.cb_block_hotkey = ModernCheckBox("Блокировать клавишу в других приложениях", True, w)
        layout.addWidget(self.cb_block_hotkey)

        layout.addStretch()
        return w

    def _create_general_page(self) -> QWidget:
        """Tab 3: Общее (Mockup 2)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 18, 28, 16)
        layout.setSpacing(10)

        lbl_theme = QLabel("Оформление виджета", w)
        lbl_theme.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_theme.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_theme)

        theme_grid = QGridLayout()
        theme_grid.setContentsMargins(0, 0, 0, 0)
        theme_grid.setHorizontalSpacing(10)
        theme_grid.setVerticalSpacing(10)

        self.theme_cards = [
            CustomThemeCard("claude", "Claude", "#E2555F", parent=w),
            CustomThemeCard("cyan", "Cyan", "#06B6D4", parent=w),
            CustomThemeCard("emerald", "Emerald", "#10B981", parent=w),
            CustomThemeCard("purple", "Violet", "#8B5CF6", parent=w),
            CustomThemeCard("crimson", "Crimson", "#EF4444", parent=w),
            CustomThemeCard("amber", "Amber", "#F59E0B", parent=w),
        ]

        for i, c in enumerate(self.theme_cards):
            c.clicked.connect(lambda checked=False, card=c: self._select_theme_card(card.theme_id))
            theme_grid.addWidget(c, i // 3, i % 3)

        layout.addLayout(theme_grid)
        layout.addSpacing(6)

        lbl_sys = QLabel("Поведение системы", w)
        lbl_sys.setFont(get_subtitle_font(11, demi_bold=True))
        lbl_sys.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(lbl_sys)

        self.cb_sound = ModernCheckBox("Звуковые сигналы", True, w)
        layout.addWidget(self.cb_sound)

        vol_row = QHBoxLayout()
        vol_row.setContentsMargins(26, 0, 10, 0)
        vol_row.setSpacing(10)
        self.slider_vol = QSlider(Qt.Orientation.Horizontal, w)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setFixedHeight(18)
        self.slider_vol.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #282834;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0A58B4;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 1px solid #0A58B4;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
        """)
        self.lbl_vol_val = QLabel("50%", w)
        self.lbl_vol_val.setFixedWidth(36)
        self.lbl_vol_val.setFont(get_body_font(10))
        self.lbl_vol_val.setStyleSheet("color: #A4A4B0;")
        self.slider_vol.valueChanged.connect(lambda v: self.lbl_vol_val.setText(f"{v}%"))
        vol_row.addWidget(self.slider_vol)
        vol_row.addWidget(self.lbl_vol_val)
        layout.addLayout(vol_row)
        self.cb_sound.toggled.connect(self.slider_vol.setEnabled)

        self.cb_autostart = ModernCheckBox("Автозапуск с Windows", False, w)
        self.cb_stream = ModernCheckBox("Потоковый предпросмотр", True, w)
        self.cb_updates = ModernCheckBox("Проверка обновлений", True, w)
        self.cb_tray_close = ModernCheckBox("Сворачивать в трей при закрытии", True, w)
        self.cb_snow = ModernCheckBox("Падающий снег в настройках", True, w)
        self.cb_snow.toggled.connect(self._on_snow_cb_toggled)

        layout.addWidget(self.cb_autostart)
        layout.addWidget(self.cb_stream)
        layout.addWidget(self.cb_updates)
        layout.addWidget(self.cb_tray_close)
        layout.addWidget(self.cb_snow)


        layout.addSpacing(6)

        lbl_data = QLabel("Хранение данных", w)
        lbl_data.setFont(get_subtitle_font(11, demi_bold=True))
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
        self.lbl_cache_info.setFont(get_body_font(10))
        self.lbl_cache_info.setStyleSheet("color: #E6E6EE; border: none;")
        cc_layout.addWidget(self.lbl_cache_info)
        cc_layout.addStretch()

        btn_clear = QPushButton("Очистить", card_cache)
        btn_clear.setFixedSize(90, 28)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setFont(get_body_font(9))
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
        ver_lbl.setFont(get_body_font(10))
        ver_lbl.setStyleSheet("color: #8E8E98;")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_box.addWidget(ver_lbl)

        layout.addLayout(top_box)
        layout.addSpacing(10)

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
        lbl_upd.setFont(get_body_font(10))
        lbl_upd.setStyleSheet("color: #E6E6EE; border: none;")
        cu_layout.addWidget(lbl_upd)
        cu_layout.addStretch()

        self.lbl_card_upd_status = QLabel(card_upd)
        self.lbl_card_upd_status.setFont(get_body_font(9))
        self.lbl_card_upd_status.setStyleSheet("color: #70707B; border: none; margin-right: 8px;")
        cu_layout.addWidget(self.lbl_card_upd_status)

        self.btn_chk_updates = QPushButton("Проверить", card_upd)
        self.btn_chk_updates.setFixedSize(100, 28)
        self.btn_chk_updates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_chk_updates.setFont(get_body_font(9))
        self.btn_chk_updates.setStyleSheet("""
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
        self.btn_chk_updates.clicked.connect(self._manual_check_updates)
        cu_layout.addWidget(self.btn_chk_updates)
        layout.addWidget(card_upd)

        layout.addSpacing(8)

        btn_privacy = QPushButton("Политика конфиденциальности", w)
        btn_terms = QPushButton("Условия использования", w)
        for b, tab_idx in [(btn_privacy, 0), (btn_terms, 1)]:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(get_body_font(10))
            b.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #3B82F6;
                    border: none;
                    text-align: left;
                    text-decoration: underline;
                    padding: 3px 0;
                }
                QPushButton:hover {
                    color: #60A5FA;
                }
            """)
            b.clicked.connect(lambda checked=False, idx=tab_idx: self._open_legal_docs(idx))
            layout.addWidget(b)

        btn_logs = QPushButton("Открыть журнал работы (логи)", w)
        btn_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logs.setFont(get_body_font(10))
        btn_logs.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #3B82F6;
                border: none;
                text-align: left;
                text-decoration: underline;
                padding: 3px 0;
            }
            QPushButton:hover {
                color: #60A5FA;
            }
        """)
        btn_logs.clicked.connect(lambda checked=False: open_logs_folder())
        layout.addWidget(btn_logs)

        ext_links = [
            ("Журнал изменений на GitHub", "https://github.com/wesiks/VoiceTyping/releases"),
            ("Сообщить о проблеме", "https://github.com/wesiks/VoiceTyping/issues")
        ]
        for link_text, link_url in ext_links:
            lbl = QLabel(f'<a href="{link_url}" style="color: #3B82F6; text-decoration: underline;">{link_text}</a>', w)
            lbl.setFont(get_body_font(10))
            lbl.setOpenExternalLinks(True)
            layout.addWidget(lbl)

        layout.addStretch()

        lbl_copy = QLabel("© 2026 VoiceTyping. Все права защищены.", w)
        lbl_copy.setFont(get_body_font(9))
        lbl_copy.setStyleSheet("color: #5E5E68;")
        lbl_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_copy)

        return w


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
        lbl_t.setFont(get_body_font(10))
        lbl_t.setStyleSheet("color: #E6E6EE; border: none;")
        c_layout.addWidget(lbl_t)
        c_layout.addStretch()

        lbl_b = QLabel(key_badge, card)
        lbl_b.setFont(get_mono_font(9, bold=True))
        lbl_b.setStyleSheet("""
            background-color: #26262E;
            color: #C8C8D4;
            border: 1px solid #3A3A44;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        c_layout.addWidget(lbl_b)
        return card


    def _switch_tab(self, index: int):
        for idx, btn in enumerate(self.nav_buttons):
            btn.set_active(idx == index)
        self.stack.setCurrentIndex(index)
        if hasattr(self, "snow_widget"):
            self.snow_widget.raise_()
        if index == 0 and self.isVisible():
            self.mic_monitor.start(self.cmb_mic.currentData())
        else:
            self.mic_monitor.stop()

    def _toggle_snow(self):
        current = self.settings.get("snow_enabled", True)
        new_state = not current
        self.settings["snow_enabled"] = new_state
        if hasattr(self, "cb_snow"):
            self.cb_snow.blockSignals(True)
            self.cb_snow.setChecked(new_state)
            self.cb_snow.blockSignals(False)
        if hasattr(self, "snow_widget"):
            if new_state:
                self.snow_widget.start()
            else:
                self.snow_widget.stop()
        self._update_snow_btn_style()
        save_settings(self.settings)

    def _on_snow_cb_toggled(self, checked: bool):
        self.settings["snow_enabled"] = checked
        if hasattr(self, "snow_widget"):
            if checked:
                self.snow_widget.start()
            else:
                self.snow_widget.stop()
        self._update_snow_btn_style()

    def _update_snow_btn_style(self):
        if not hasattr(self, "btn_snow"):
            return
        is_on = self.settings.get("snow_enabled", True)
        if is_on:
            self.btn_snow.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 122, 27, 0.18);
                    color: #FF944D;
                    border: 1px solid rgba(255, 122, 27, 0.35);
                    font-size: 13px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 122, 27, 0.28);
                    color: #FFA768;
                }
            """)
        else:
            self.btn_snow.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #555562;
                    border: 1px solid transparent;
                    font-size: 13px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.08);
                    color: #8E8E98;
                }
            """)


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

    def _open_legal_docs(self, initial_tab: int = 0):
        dlg = LegalDocsDialog(initial_tab=initial_tab, parent=self)
        dlg.exec()

    def _toggle_network_frame(self):
        visible = not self.frame_network.isVisible()
        self.frame_network.setVisible(visible)
        if visible:
            self.btn_toggle_network.setText("Настройки прокси и сети ▴")
        else:
            self.btn_toggle_network.setText("Настройки прокси и сети ▾")

    def _on_engine_changed(self):
        mode = self.cmb_engine.currentData()
        if mode == "vosk":
            self.inp_api.setEnabled(False)
            self.btn_check_api.setEnabled(False)
            self.lbl_api_hint.setText("В режиме «Только офлайн» интернет, VPN и API-ключ не требуются. Распознавание выполняется локально на вашем ПК.")
            self.lbl_api_hint.setStyleSheet("color: #34D399; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 6px 10px;")
            self.lbl_api_hint.show()
        else:
            self.inp_api.setEnabled(True)
            self.btn_check_api.setEnabled(True)
            self.lbl_api_hint.hide()

    def _check_api_key_async(self):
        key = self.inp_api.text().strip()
        if not key:
            self.btn_check_api.setText("Введите ключ")
            return

        self.btn_check_api.setText("Проверка...")
        self.btn_check_api.setEnabled(False)
        self.lbl_api_hint.hide()

        proxy_val = self.inp_proxy.text().strip() if hasattr(self, "inp_proxy") else ""
        base_val = self.inp_base_url.text().strip() if hasattr(self, "inp_base_url") else ""

        def _worker():
            status_ok = False
            is_403 = False
            msg = ""
            proxies = {"http": proxy_val, "https": proxy_val} if proxy_val else None
            check_url = f"{base_val.rstrip('/')}/models" if base_val else "https://api.groq.com/openai/v1/models"

            try:
                r = requests.get(
                    check_url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": f"VoiceTyping/{APP_VERSION}"
                    },
                    proxies=proxies,
                    timeout=(2.0, 3.0)
                )
                if r.status_code == 200:
                    status_ok = True
                elif r.status_code == 401:
                    msg = "Неверный ключ"
                elif r.status_code == 403:
                    is_403 = True
                    msg = "Блок РФ (403)"
                else:
                    msg = f"Код {r.status_code}"
            except requests.exceptions.Timeout:
                msg = "Таймаут сети"
            except Exception:
                msg = "Ошибка связи"

            def _done():
                self.btn_check_api.setEnabled(True)
                if status_ok:
                    self.btn_check_api.setText("Ключ действителен")
                    self.btn_check_api.setStyleSheet("background-color: #064E3B; color: #34D399; border: 1px solid #059669; border-radius: 8px;")
                    self.lbl_api_hint.hide()
                else:
                    self.btn_check_api.setText(msg or "Ошибка")
                    self.btn_check_api.setStyleSheet("background-color: #4C0519; color: #FB7185; border: 1px solid #E11D48; border-radius: 8px;")
                    if is_403:
                        self.lbl_api_hint.setText("Доступ к Groq заблокирован для вашего региона (код 403). Включите VPN, укажите прокси ниже или переключитесь на режим «Только офлайн (Vosk)».")
                        self.lbl_api_hint.setStyleSheet("color: #F87171; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 6px 10px;")
                        self.lbl_api_hint.show()
                        if hasattr(self, "frame_network") and not self.frame_network.isVisible():
                            self._toggle_network_frame()
                    elif "Таймаут" in msg or "Ошибка" in msg:
                        self.lbl_api_hint.setText("Не удалось связаться с сервером. Проверьте интернет, VPN или выберите режим «Только офлайн (Vosk)».")
                        self.lbl_api_hint.setStyleSheet("color: #F87171; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 6px 10px;")
                        self.lbl_api_hint.show()

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
        if hasattr(self, "btn_chk_updates"):
            self.btn_chk_updates.setEnabled(False)
            self.btn_chk_updates.setText("Проверка...")
        if hasattr(self, "lbl_card_upd_status"):
            self.lbl_card_upd_status.setText("Соединение...")
            self.lbl_card_upd_status.setStyleSheet("color: #70707B; border: none; margin-right: 8px;")
        self.lbl_status.setText("Проверка обновлений...")
        self.lbl_status.setStyleSheet("color: #A4A4B0;")

        proxy_val = self.inp_proxy.text().strip() if hasattr(self, "inp_proxy") else ""

        def _worker():
            res = check_github_update(current_version=APP_VERSION, proxy_url=proxy_val, force_refresh=True)
            def _done():
                if hasattr(self, "btn_chk_updates"):
                    self.btn_chk_updates.setEnabled(True)
                    self.btn_chk_updates.setText("Проверить")
                if res.get("has_update"):
                    latest = res.get("latest_version")
                    msg = f"Доступно обновление: v{latest}"
                    if hasattr(self, "lbl_card_upd_status"):
                        self.lbl_card_upd_status.setText(f"Новая версия v{latest}")
                        self.lbl_card_upd_status.setStyleSheet("color: #60A5FA; border: none; margin-right: 8px;")
                    self.lbl_status.setText(msg)
                    self.lbl_status.setStyleSheet("color: #60A5FA;")
                    url = res.get("download_url") or res.get("release_url")
                    open_release_page(url)
                elif res.get("error"):
                    err_msg = str(res.get("error"))
                    if hasattr(self, "lbl_card_upd_status"):
                        self.lbl_card_upd_status.setText("Ошибка сети")
                        self.lbl_card_upd_status.setStyleSheet("color: #F87171; border: none; margin-right: 8px;")
                    self.lbl_status.setText(f"Ошибка: {err_msg}")
                    self.lbl_status.setStyleSheet("color: #F87171;")
                else:
                    msg = "Установлена последняя версия"
                    if hasattr(self, "lbl_card_upd_status"):
                        self.lbl_card_upd_status.setText("Актуально")
                        self.lbl_card_upd_status.setStyleSheet("color: #34D399; border: none; margin-right: 8px;")
                    self.lbl_status.setText(msg)
                    self.lbl_status.setStyleSheet("color: #34D399;")
            QTimer.singleShot(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _load_values(self):
        s = self.settings
        self.inp_api.setText(s.get("groq_api_key", ""))
        self.lbl_current_key.setText(s.get("hotkey", "f8").upper())

        stt_mode = s.get("stt_mode", "auto")
        idx_e = self.cmb_engine.findData(stt_mode)
        if idx_e != -1:
            self.cmb_engine.setCurrentIndex(idx_e)
        self._on_engine_changed()

        self.inp_proxy.setText(s.get("proxy_url", ""))
        self.inp_base_url.setText(s.get("api_base_url", ""))

        mode = s.get("activation_mode", "hold")
        self._set_activation_mode(mode)

        current_theme = s.get("theme", "claude")
        for c in self.theme_cards:
            c.set_active(c.theme_id == current_theme)

        self.cb_sound.setChecked(s.get("sound_enabled", True))
        vol = int(float(s.get("sound_volume", 0.5)) * 100)
        self.slider_vol.setValue(vol)
        self.lbl_vol_val.setText(f"{vol}%")
        self.slider_vol.setEnabled(self.cb_sound.isChecked())

        self.cb_autostart.setChecked(s.get("autostart", False))
        self.cb_stream.setChecked(s.get("stream_preview", True))
        self.cb_updates.setChecked(s.get("check_updates", True))
        self.cb_tray_close.setChecked(s.get("minimize_to_tray", True))
        self.cb_voice_punct.setChecked(s.get("voice_punctuation", True))
        self.cb_trailing_space.setChecked(s.get("trailing_space", False))
        self.cb_block_hotkey.setChecked(s.get("block_hotkey", True))
        self.cb_snow.setChecked(s.get("snow_enabled", True))
        self._update_snow_btn_style()

        lang = s.get("language", "ru")
        idx = self.cmb_lang.findData(lang)
        if idx != -1:
            self.cmb_lang.setCurrentIndex(idx)

        dev_idx = s.get("audio_device", None)
        if dev_idx is not None:
            c_idx = self.cmb_mic.findData(dev_idx)
            if c_idx != -1:
                self.cmb_mic.setCurrentIndex(c_idx)

    def _save_settings(self):
        self.settings["stt_mode"] = self.cmb_engine.currentData() or "auto"
        self.settings["groq_api_key"] = self.inp_api.text().strip()
        self.settings["proxy_url"] = self.inp_proxy.text().strip()
        self.settings["api_base_url"] = self.inp_base_url.text().strip()
        self.settings["sound_enabled"] = self.cb_sound.isChecked()
        self.settings["sound_volume"] = round(self.slider_vol.value() / 100.0, 2)
        self.settings["autostart"] = self.cb_autostart.isChecked()
        self.settings["stream_preview"] = self.cb_stream.isChecked()
        self.settings["check_updates"] = self.cb_updates.isChecked()
        self.settings["minimize_to_tray"] = self.cb_tray_close.isChecked()
        self.settings["voice_punctuation"] = self.cb_voice_punct.isChecked()
        self.settings["trailing_space"] = self.cb_trailing_space.isChecked()
        self.settings["block_hotkey"] = self.cb_block_hotkey.isChecked()
        self.settings["snow_enabled"] = self.cb_snow.isChecked()
        self.settings["language"] = self.cmb_lang.currentData() or "ru"
        self.settings["audio_device"] = self.cmb_mic.currentData()

        set_windows_autostart(self.settings["autostart"])
        save_settings(self.settings)
        self.settings_saved.emit(self.settings)

        self.btn_save.setText("✓ Сохранено")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #064E3B;
                color: #34D399;
                border: 1px solid #059669;
                border-radius: 16px;
            }
        """)
        self.lbl_status.setText("Настройки успешно сохранены")
        self.lbl_status.setStyleSheet("color: #34D399;")

        QTimer.singleShot(2000, self._reset_save_button)

    def _reset_save_button(self):
        if hasattr(self, "btn_save") and hasattr(self, "_btn_save_default_style"):
            self.btn_save.setText("Сохранить")
            self.btn_save.setStyleSheet(self._btn_save_default_style)

    def _save_and_close(self):
        self._save_settings()
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 50:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
