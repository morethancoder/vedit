import numpy as np

from vedit.cut.signal import envelope_of, minima, quietest, silences


def _db():
    sr = 1000
    a = np.full(sr * 2, 0.5)
    a[700:900] = 0.0  # 0.7-0.9 s silent
    a[1500] = 0.0
    return envelope_of(a, sr)


def test_quietest_and_silences():
    db = _db()
    assert 0.7 <= quietest(db, 0.75, 0.12) < 0.9
    assert silences(db) == [(0.7, 0.9)]


def test_minima_spacing():
    pts = minima(_db(), 0.5, 1.2, 3)
    assert len(pts) == 3 and all(abs(a - b) >= 0.08 for i, a in enumerate(pts) for b in pts[i + 1 :])
