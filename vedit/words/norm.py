"""Word keys for matching: Arabic-aware, Latin lowercased (ported from T build.py `_AR`/`wnorm`)."""

import re

_AR = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
# Addition to the T port: Studio and cues mix Arabic-Indic (and Persian) digits with ASCII ones.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_MARKS = re.compile(r"[ً-ٰٟـ]")  # diacritics, dagger alef, tatweel
_KEEP = re.compile(r"[^a-z0-9'ء-ي]")


def norm(w: str) -> str:
    """Key for one word: no diacritics/tatweel/punctuation, unified alef/ya/ta-marbuta/hamza seats."""
    w = _MARKS.sub("", w.lower()).translate(_AR).translate(_DIGITS)
    return _KEEP.sub("", w)


def tokens(phrase: str) -> list[str]:
    """Normalised tokens of a phrase; words that normalise to nothing are dropped."""
    return [k for k in (norm(w) for w in phrase.split()) if k]


_AR_LETTER = re.compile(r"[ء-ي]")
_LATIN = re.compile(r"[A-Za-z]")


def mixed_script(word: str) -> bool:
    """True when one token holds both an Arabic and an ASCII letter (an ASR glitch such as "سalam")."""
    return bool(_AR_LETTER.search(word) and _LATIN.search(word))
