from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import Qt

def create_app_icon(accent_color: str = "#E06A38") -> QIcon:
    """Generates a crisp, vector-rendered microphone tray icon."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QBrush(QColor(accent_color)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)

    painter.setPen(QPen(QColor(255, 255, 255), 3.5, cap=Qt.PenCapStyle.RoundCap))
    painter.setBrush(QBrush(QColor(255, 255, 255)))

    painter.drawRoundedRect(25, 14, 14, 22, 7, 7)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(19, 22, 26, 22, 0, -180 * 16)

    painter.drawLine(32, 44, 32, 51)
    painter.drawLine(23, 51, 41, 51)
    
    painter.end()
    return QIcon(pix)
