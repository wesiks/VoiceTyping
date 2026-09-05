THEMES = {
    "claude": {
        "id": "claude",
        "name": "Claude Warm",
        "accent": "#E06A38",
        "border": (224, 106, 56, 190),
        "glow": (224, 106, 56, 45),
        "card_bg": (20, 20, 24, 248),
        "bar_colors": [
            (224, 106, 56),  # Terracotta
            (234, 88, 12),   # Amber-Orange
            (245, 158, 11),  # Golden Amber
            (234, 88, 12),
            (224, 106, 56)
        ],
        "text": (250, 248, 244)
    },
    "cyan": {
        "id": "cyan",
        "name": "Cyber Cyan",
        "accent": "#06B6D4",
        "border": (6, 182, 212, 190),
        "glow": (6, 182, 212, 45),
        "card_bg": (12, 18, 28, 248),
        "bar_colors": [
            (6, 182, 212),
            (59, 130, 246),
            (96, 165, 250),
            (59, 130, 246),
            (6, 182, 212)
        ],
        "text": (241, 245, 249)
    },
    "emerald": {
        "id": "emerald",
        "name": "Emerald Mint",
        "accent": "#10B981",
        "border": (16, 185, 129, 190),
        "glow": (16, 185, 129, 45),
        "card_bg": (12, 22, 18, 248),
        "bar_colors": [
            (16, 185, 129),
            (5, 150, 105),
            (52, 211, 153),
            (5, 150, 105),
            (16, 185, 129)
        ],
        "text": (240, 253, 244)
    },
    "purple": {
        "id": "purple",
        "name": "Neon Violet",
        "accent": "#8B5CF6",
        "border": (139, 92, 246, 190),
        "glow": (139, 92, 246, 45),
        "card_bg": (18, 14, 28, 248),
        "bar_colors": [
            (139, 92, 246),
            (168, 85, 247),
            (192, 132, 252),
            (168, 85, 247),
            (139, 92, 246)
        ],
        "text": (245, 243, 255)
    },
    "crimson": {
        "id": "crimson",
        "name": "Ruby Crimson",
        "accent": "#EF4444",
        "border": (239, 68, 68, 190),
        "glow": (239, 68, 68, 45),
        "card_bg": (24, 12, 16, 248),
        "bar_colors": [
            (239, 68, 68),
            (244, 63, 94),
            (251, 113, 133),
            (244, 63, 94),
            (239, 68, 68)
        ],
        "text": (255, 241, 242)
    }
}

def get_theme(theme_id: str) -> dict:
    return THEMES.get(theme_id, THEMES["claude"])
