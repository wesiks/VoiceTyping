import re

MULTI_WORD_CONJUNCTIONS = [
    "потому что", "так как", "оттого что", "из-за того что",
    "благодаря тому что", "в то время как", "как будто", "будто бы", "то есть"
]

SINGLE_WORD_CONJUNCTIONS_RU = [
    "что", "чтобы", "чтоб", "когда", "если", "хотя", "хоть",
    "где", "куда", "откуда", "зачем", "почему",
    "который", "которая", "которое", "которые", "которого", "которой", "которых", "которому", "которым",
    "но", "а"
]

SINGLE_WORD_CONJUNCTIONS_EN = [
    "which", "although", "whereas", "while"
]

VOICE_PUNCTUATION = [
    (r"\b(вопросительный знак|знак вопроса|question mark)\b", "?"),
    (r"\b(восклицательный знак|exclamation mark|exclamation point)\b", "!"),
    (r"\b(точка с запятой|semicolon)\b", ";"),
    (r"\b(двоеточие|colon)\b", ":"),
    (r"\b(многоточие|ellipsis)\b", "..."),
    (r"\b(с новой строки|новый абзац|new line|new paragraph)\b", "\n"),
    (r"\b(тире|дефис|dash|hyphen)\b", " —"),
    (r"\b(точка|period|full stop)\b", "."),
    (r"\b(запятая|comma)\b", ","),
]

_MULTI_CONJ_RE = re.compile(
    r"(?<![,.:;?!—\n])\s+\b(" + "|".join(re.escape(w) for w in MULTI_WORD_CONJUNCTIONS) + r")\b",
    re.IGNORECASE
)

_SINGLE_CONJ_RU_RE = re.compile(
    r"(?<![,.:;?!—\n])(?<!\bпотому)(?<!\bоттого)(?<!\bтого)\s+\b(" +
    "|".join(re.escape(w) for w in SINGLE_WORD_CONJUNCTIONS_RU) + r")\b",
    re.IGNORECASE
)

_SINGLE_CONJ_EN_RE = re.compile(
    r"(?<![,.:;?!—\n])\s+\b(" +
    "|".join(re.escape(w) for w in SINGLE_WORD_CONJUNCTIONS_EN) + r")\b",
    re.IGNORECASE
)

def _format_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    line = _MULTI_CONJ_RE.sub(r", \1", line)
    line = _SINGLE_CONJ_RU_RE.sub(r", \1", line)
    line = _SINGLE_CONJ_EN_RE.sub(r", \1", line)

    line = re.sub(r"\s+([,.:;?!])", r"\1", line)
    line = re.sub(r"(?<!\.)([,.:;?!])(?=[^\s\d.])", r"\1 ", line)
    line = re.sub(r"\s*—\s*", " — ", line)
    line = re.sub(r"[ \t]+", " ", line).strip()

    if line:
        line = line[0].upper() + line[1:]

    def _cap_after_punct(match):
        return match.group(1) + match.group(2).upper()

    line = re.sub(r"([.!?]\s+)([a-zа-яё])", _cap_after_punct, line)
    return line

def format_live_text(raw_text: str, apply_voice_punct: bool = True) -> str:
    """
    Transforms raw unpunctuated ASR stream into clean, readable text
    with capital letters, commas, voice punctuation, and paragraph breaks.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    if apply_voice_punct:
        for pattern, replacement in VOICE_PUNCTUATION:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    lines = text.split("\n")
    formatted_lines = [_format_line(line) for line in lines]
    return "\n".join(formatted_lines)

