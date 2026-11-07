"""`vedit styles find`: rank packs for a few words by keyword overlap. Plain code, no model.

Words are lowercased, stripped of diacritics, lightly stemmed (-es, -s, -ing, -ed, a final e); a pack scores 3 per query
word that matches one of its `keywords:` and 1 per query word found in its `summary:` (or name).
"""

from __future__ import annotations

import re
import unicodedata

KEYWORD_WEIGHT, SUMMARY_WEIGHT = 3, 1


def norm(word: str) -> str:
    """Lowercase, no diacritics (Arabic marks and Latin accents), light stem."""
    w = unicodedata.normalize("NFKD", word.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w  # doodle / doodles / doodled -> doodl


def words(text: str) -> list[str]:
    return [norm(w) for w in re.findall(r"[^\W_]+", str(text or ""))]


def score(query: str, keywords, summary: str, name: str = "") -> tuple[int, list[str]]:
    """(score, the query words that matched) of one pack."""
    kw = {n for k in keywords or [] for n in words(k)}
    sm = set(words(summary)) | set(words(name))
    total, hit = 0, []
    for q in dict.fromkeys(words(query)):
        if q in kw:
            total += KEYWORD_WEIGHT
        elif q in sm:
            total += SUMMARY_WEIGHT
        else:
            continue
        hit.append(q)
    return total, hit


def rank(query: str, rows: list[dict]) -> list[dict]:
    """Rows (name, keywords, summary, ...) with score and matched words, best first; zero scores dropped."""
    out = []
    for r in rows:
        s, hit = score(query, r.get("keywords"), r.get("summary", ""), r["name"])
        if s:
            out.append({**r, "score": s, "matched": hit})
    return sorted(out, key=lambda r: (-r["score"], r["name"]))
