import sys
from pathlib import Path
from PyQt6.QtGui import QFontDatabase, QFont, QGuiApplication

_TITLE_FAMILY = "Segoe UI"
_BODY_FAMILY = "Segoe UI Variable Text"
_MONO_FAMILY = "Consolas"
_INITIALIZED = False
_APP_INSTANCE = None

def _resolve_font(filename: str) -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "fonts" / filename,
        Path(__file__).resolve().parent.parent / "fonts" / filename,
        Path(sys.executable).resolve().parent / "fonts" / filename,
        Path(sys.executable).resolve().parent / "_internal" / "fonts" / filename,
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / "fonts" / filename)

    for p in candidates:
        if p.exists():
            return p
    return None

def init_custom_fonts():
    """Loads and registers Inter for UI, unifying titles and body for smooth, pleasant typography."""
    global _TITLE_FAMILY, _BODY_FAMILY, _MONO_FAMILY, _INITIALIZED, _APP_INSTANCE
    if _INITIALIZED:
        return

    if QGuiApplication.instance() is None:
        _APP_INSTANCE = QGuiApplication(sys.argv)

    p_body = _resolve_font("Inter.ttf")
    if p_body:
        try:
            fid = QFontDatabase.addApplicationFont(str(p_body))
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    _BODY_FAMILY = families[0]
                    _TITLE_FAMILY = families[0]
        except Exception:
            pass

    p_mono = _resolve_font("JetBrainsMono.ttf")
    if p_mono:
        try:
            fid = QFontDatabase.addApplicationFont(str(p_mono))
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    _MONO_FAMILY = families[0]
        except Exception:
            pass

    _INITIALIZED = True

def _apply_quality_hints(font: QFont) -> QFont:
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font

def get_title_font(size: int = 13, bold: bool = True) -> QFont:
    """Modern, clean title font matching sidebar style."""
    init_custom_fonts()
    font = QFont(_TITLE_FAMILY, int(round(size)))
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.DemiBold)
    return _apply_quality_hints(font)

def get_subtitle_font(size: int = 11, demi_bold: bool = True) -> QFont:
    """Semi-bold modern subtitle font matching sidebar style."""
    init_custom_fonts()
    font = QFont(_TITLE_FAMILY, int(round(size)))
    font.setWeight(QFont.Weight.DemiBold if demi_bold else QFont.Weight.Medium)
    return _apply_quality_hints(font)

def get_body_font(size: int = 10, bold: bool = False, demi_bold: bool = False) -> QFont:
    """Clean, high-legibility interface font (Inter) for labels, explanations, and controls."""
    init_custom_fonts()
    font = QFont(_BODY_FAMILY, int(round(size)))
    if bold:
        font.setWeight(QFont.Weight.Bold)
    elif demi_bold:
        font.setWeight(QFont.Weight.DemiBold)
    else:
        font.setWeight(QFont.Weight.Normal)
    return _apply_quality_hints(font)

def get_mono_font(size: int = 10, bold: bool = False) -> QFont:
    """Clean monospaced font for hotkeys, code, and key display."""
    init_custom_fonts()
    font = QFont(_MONO_FAMILY, int(round(size)))
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return _apply_quality_hints(font)

def get_app_font(size: int = 11, bold: bool = False, demi_bold: bool = False) -> QFont:
    """Backwards-compatible alias for body/UI font."""
    return get_body_font(size=size, bold=bold, demi_bold=demi_bold)

def get_font_families() -> dict:
    """Returns the names of all resolved font families for use in CSS/QSS."""
    init_custom_fonts()
    return {
        "title": _TITLE_FAMILY,
        "body": _BODY_FAMILY,
        "mono": _MONO_FAMILY,
    }
