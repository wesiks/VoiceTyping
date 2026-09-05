import sys
from pathlib import Path
from PyQt6.QtGui import QFontDatabase, QFont

_FONT_FAMILY = "Segoe UI Variable Text"
_INITIALIZED = False

def init_custom_fonts() -> str:
    """Loads and registers custom bundled Inter font with graceful fallback."""
    global _FONT_FAMILY, _INITIALIZED
    if _INITIALIZED:
        return _FONT_FAMILY

    # Candidate locations for Inter.ttf across dev and PyInstaller builds
    candidates = [
        Path(__file__).resolve().parent / "fonts" / "Inter.ttf",
        Path(sys.executable).resolve().parent / "fonts" / "Inter.ttf",
        Path(sys.executable).resolve().parent / "_internal" / "fonts" / "Inter.ttf",
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / "fonts" / "Inter.ttf")

    for font_path in candidates:
        if font_path.exists():
            try:
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        _FONT_FAMILY = families[0]
                        break
            except Exception:
                pass

    _INITIALIZED = True
    return _FONT_FAMILY

def get_app_font(size: int = 11, bold: bool = False, demi_bold: bool = False) -> QFont:
    """Returns an antialiased QFont with the custom font family."""
    init_custom_fonts()
    font = QFont(_FONT_FAMILY, size)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    elif demi_bold:
        font.setWeight(QFont.Weight.DemiBold)
    else:
        font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
