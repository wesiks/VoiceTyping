import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import (
    QImage, QPainter, QColor, QBrush, QPen, QFont,
    QPainterPath, QLinearGradient, QRadialGradient
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF

def generate_assets():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    assets_dir = Path(__file__).resolve().parent.parent / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)

    w, h = 164, 314
    wizard_img = QImage(w, h, QImage.Format.Format_RGB32)
    painter = QPainter(wizard_img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    bg_grad = QLinearGradient(0, 0, 0, h)
    bg_grad.setColorAt(0.0, QColor('#181820'))
    bg_grad.setColorAt(0.5, QColor('#121216'))
    bg_grad.setColorAt(1.0, QColor('#0C0C0F'))
    painter.fillRect(0, 0, w, h, QBrush(bg_grad))

    glow_grad = QRadialGradient(QPointF(w / 2.0, 95.0), 95.0)
    glow_grad.setColorAt(0.0, QColor(249, 115, 22, 55))
    glow_grad.setColorAt(0.6, QColor(234, 88, 12, 20))
    glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillRect(0, 0, w, 220, QBrush(glow_grad))

    icon_rect = QRectF(46, 38, 72, 72)
    icon_grad = QLinearGradient(icon_rect.topLeft(), icon_rect.bottomRight())
    icon_grad.setColorAt(0.0, QColor('#FF7A29'))
    icon_grad.setColorAt(1.0, QColor('#E5501B'))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
    painter.drawRoundedRect(icon_rect.adjusted(-1, 3, 1, 5), 18.0, 18.0)

    painter.setPen(QPen(QColor(255, 255, 255, 50), 1.2))
    painter.setBrush(QBrush(icon_grad))
    painter.drawRoundedRect(icon_rect, 18.0, 18.0)

    cx = icon_rect.center().x()
    cy = icon_rect.center().y()
    painter.setPen(QPen(QColor(255, 255, 255), 2.6, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    mic_w = 11.0
    mic_h = 18.0
    painter.drawRoundedRect(QRectF(cx - mic_w/2, cy - 13.0, mic_w, mic_h), mic_w/2, mic_w/2)

    p_bracket = QPainterPath()
    p_bracket.arcMoveTo(QRectF(cx - 10.0, cy - 7.5, 20.0, 17.5), 180)
    p_bracket.arcTo(QRectF(cx - 10.0, cy - 7.5, 20.0, 17.5), 180, -180)
    painter.drawPath(p_bracket)

    painter.drawLine(QPoint(int(cx), int(cy + 10.0)), QPoint(int(cx), int(cy + 16.0)))
    painter.drawLine(QPoint(int(cx - 7.0), int(cy + 16.0)), QPoint(int(cx + 7.0), int(cy + 16.0)))

    title_font = QFont('Segoe UI', 12, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.setPen(QColor('#FFFFFF'))
    painter.drawText(QRectF(0, 122, w, 24), Qt.AlignmentFlag.AlignCenter, 'VoiceTyping')

    ver_font = QFont('Segoe UI', 8, QFont.Weight.DemiBold)
    painter.setFont(ver_font)
    painter.setPen(QColor('#FB923C'))
    painter.drawText(QRectF(0, 144, w, 18), Qt.AlignmentFlag.AlignCenter, 'v2.5.0 Release')

    wave_y = 176
    bar_w = 3.5
    spacing = 7.0
    heights = [8, 14, 22, 32, 22, 14, 8]
    start_wave_x = (w - (len(heights) * spacing)) / 2.0 + 1.5

    for i, bar_h in enumerate(heights):
        bx = start_wave_x + i * spacing
        by = wave_y - (bar_h / 2.0)
        grad_bar = QLinearGradient(bx, by, bx, by + bar_h)
        grad_bar.setColorAt(0.0, QColor('#FDBA74'))
        grad_bar.setColorAt(1.0, QColor('#EA580C'))
        painter.setBrush(QBrush(grad_bar))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 1.8, 1.8)

    info_font = QFont('Segoe UI', 7, QFont.Weight.Normal)
    painter.setFont(info_font)
    bullets = [
        '100% Офлайн Vosk',
        'Быстрый ввод речи',
        'Безопасно и приватно'
    ]
    cur_y = 208
    for b in bullets:
        painter.setBrush(QBrush(QColor('#F97316')))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(22, cur_y + 4, 4.0, 4.0))

        painter.setPen(QColor('#CBD5E1'))
        painter.drawText(QRectF(32, cur_y, w - 38, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, b)
        cur_y += 20

    accent_bar = QLinearGradient(0, h - 3, w, h - 3)
    accent_bar.setColorAt(0.0, QColor('#F97316'))
    accent_bar.setColorAt(1.0, QColor('#EA580C'))
    painter.fillRect(0, h - 3, w, 3, QBrush(accent_bar))

    painter.end()
    wizard_path = assets_dir / 'installer_wizard.bmp'
    wizard_img.save(str(wizard_path), 'BMP')
    print('[*] Generated:', wizard_path)

    sw, sh = 55, 55
    small_img = QImage(sw, sh, QImage.Format.Format_RGB32)
    s_painter = QPainter(small_img)
    s_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s_painter.fillRect(0, 0, sw, sh, QColor('#161412'))

    s_rect = QRectF(7, 7, 41, 41)
    s_grad = QLinearGradient(s_rect.topLeft(), s_rect.bottomRight())
    s_grad.setColorAt(0.0, QColor('#FF7A29'))
    s_grad.setColorAt(1.0, QColor('#E5501B'))

    s_painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
    s_painter.setBrush(QBrush(s_grad))
    s_painter.drawRoundedRect(s_rect, 10.0, 10.0)

    scx = s_rect.center().x()
    scy = s_rect.center().y()
    s_painter.setPen(QPen(QColor(255, 255, 255), 1.8, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
    s_painter.setBrush(Qt.BrushStyle.NoBrush)

    smic_w = 6.4
    smic_h = 10.5
    s_painter.drawRoundedRect(QRectF(scx - smic_w/2, scy - 7.5, smic_w, smic_h), smic_w/2, smic_w/2)

    sp_bracket = QPainterPath()
    sp_bracket.arcMoveTo(QRectF(scx - 5.8, scy - 4.5, 11.6, 10.0), 180)
    sp_bracket.arcTo(QRectF(scx - 5.8, scy - 4.5, 11.6, 10.0), 180, -180)
    s_painter.drawPath(sp_bracket)

    s_painter.drawLine(QPoint(int(scx), int(scy + 5.5)), QPoint(int(scx), int(scy + 9.0)))
    s_painter.drawLine(QPoint(int(scx - 4.0), int(scy + 9.0)), QPoint(int(scx + 4.0), int(scy + 9.0)))

    s_painter.end()
    small_path = assets_dir / 'installer_small.bmp'
    small_img.save(str(small_path), 'BMP')
    print('[*] Generated:', small_path)

if __name__ == '__main__':
    generate_assets()
