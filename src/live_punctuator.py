import re

COMMA_WORDS = {
    "что", "чтобы", "чтоб", "когда", "если", "потому что", "так как",
    "который", "которая", "которое", "которые", "которого", "которой", "которых",
    "но", "а", "хотя", "хоть", "где", "куда", "откуда", "зачем", "почему",
    "как будто", "будто", "словно", "то есть"
}

VOICE_PUNCTUATION = [
    (r"\b(вопросительный знак|знак вопроса)\b", "?"),
    (r"\b(восклицательный знак)\b", "!"),
    (r"\b(точка с запятой)\b", ";"),
    (r"\b(двоеточие)\b", ":"),
    (r"\b(многоточие)\b", "..."),
    (r"\b(тире|дефис)\b", " —"),
    (r"\b(точка)\b", "."),
    (r"\b(запятая)\b", ","),
    (r"\b(с новой строки|новый абзац)\b", "\n"),
]

def format_live_text(raw_text: str) -> str:
    """
    Transforms raw unpunctuated ASR stream into clean, readable text
    with capital letters, commas, and voice punctuation commands.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    for pattern, replacement in VOICE_PUNCTUATION:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"\s+([,.:;?!])", r"\1", text)
    text = re.sub(r"([,.:;?!])(?=[^\s\d])", r"\1 ", text)

    words = text.split()
    if not words:
        return ""

    formatted_words = []
    for i, w in enumerate(words):
        w_lower = w.lower().strip(",.?!:;")

        if i > 0 and w_lower in COMMA_WORDS:
            prev_word = formatted_words[-1]
            if not prev_word.endswith((",", ".", "!", "?", ":", ";", "—", "\n")):
                formatted_words[-1] = prev_word + ","
        
        formatted_words.append(w)

    text = " ".join(formatted_words)

    if text:
        text = text[0].upper() + text[1:]

    def _cap_after_punct(match):
        return match.group(1) + match.group(2).upper()

    text = re.sub(r"([.!?]\s+)([a-zа-яё])", _cap_after_punct, text)

    return text
