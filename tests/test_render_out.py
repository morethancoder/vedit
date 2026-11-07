from vedit.formats import render_out


def words(gaps_at, total):
    """Words every 0.5 s with a 0.6 s pause starting at each time in gaps_at."""
    out, t = [], 0.0
    while t < total:
        out.append({"w": "x", "t0": t, "t1": t + 0.4})
        t += 1.0 if any(abs(t - g) < 0.25 for g in gaps_at) else 0.5
    return out


def test_story_cuts_land_in_pauses_under_the_limit():
    w = words([50.0, 55.0, 110.0], 130)
    cuts = render_out.cut_points(w, 0, 130, 60)
    assert cuts == [55.7, 110.7]  # the last pause before each 60 s limit


def test_story_without_pauses_cuts_at_the_limit():
    assert render_out.cut_points(words([], 130), 0, 130, 60) == [60.0, 120.0]


def test_short_story_is_one_segment():
    assert render_out.cut_points(words([10.0], 40), 0, 40, 60) == []


def test_cuts_are_local_to_the_output_span():
    w = words([150.0], 300)
    assert render_out.cut_points(w, 100, 200, 60) == [50.7]
