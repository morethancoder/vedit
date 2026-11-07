import numpy as np
import pytest

from vedit.cut import program as pg
from vedit.project import Paths
from vedit.run import run

SR = pg.SR
PROXY = pg.PROFILES["proxy"]


def piece(**kw):
    return {"clip": "A", "in": 1.0, "out": 2.0, "start": 0.0, **kw}


def test_frames_per_piece():
    assert pg.frames_of(piece(), 30) == 30
    assert pg.frames_of(piece(**{"in": 0.0, "out": 4.7}), 30) == 141
    assert pg.frames_of(piece(**{"in": 5.1333, "out": 9.8667}), 60) == 284
    assert pg.frames_of(piece(**{"in": 3.0, "out": 3.0, "hold": 1.8}), 30) == 54
    assert pg.frames_of(piece(**{"in": 3.0, "out": 3.0, "hold": 1.8}), 60) == 108


def test_hash_changes_only_for_the_touched_piece():
    a, b = piece(), piece(**{"in": 5.0, "out": 6.0})
    h = lambda p, prof=PROXY, ident="x": pg.piece_hash(p, prof, ident)
    assert h(a) == h(dict(a, start=9.0))  # program position does not matter
    assert h(a) != h(b)
    assert h(a) != h(dict(a, out=2.1))
    assert h(a) != h(a, ident="y")  # source changed
    assert h(a) != h(a, pg.PROFILES["master"])
    assert h(piece(**{"in": 3.0, "out": 3.0, "hold": 1.8})) != h(
        piece(**{"in": 3.0, "out": 3.0, "hold": 1.0})
    )
    edl1 = [a, b, piece(clip="B")]
    edl2 = [a, dict(b, out=6.5), piece(clip="B")]
    same = [x == y for x, y in zip(map(h, edl1), map(h, edl2))]
    assert same == [True, False, True]


def const_reader(value):
    def read(clip, i0, i1):
        n = max(0, i1 - i0)
        return np.full((n, 2), value, np.float32)

    return read


def test_mix_crossfade_sums_to_one_at_a_join():
    edl = {"total": 2.0, "fade_start": 10.0,
           "pieces": [piece(**{"in": 0.5, "out": 1.5, "start": 0.0}), piece(**{"in": 4.0, "out": 5.0, "start": 1.0})]}  # fmt: skip
    out = pg.mix(edl, const_reader(1.0))
    h = int(pg.HANDLE * SR)
    cut = SR  # join at 1.0 s
    # equal-power ramps of a constant: sin + cos around the join, never a dip to zero
    seam = out[cut - h : cut + h, 0]
    t = np.linspace(0, np.pi / 2, 2 * h)
    assert np.allclose(seam, np.sin(t[::-1]) + np.sin(t), atol=1e-4)
    assert seam.min() > 0.99
    assert np.allclose(out[SR // 2], 1.0)
    assert out.shape == (2 * SR, 2)


def test_mix_hold_is_silent_and_end_fades_to_zero():
    edl = {"total": 4.0, "fade_start": 1.0,
           "pieces": [piece(**{"in": 0.0, "out": 1.0, "start": 0.0}),
                      piece(**{"in": 3.0, "out": 3.0, "hold": 1.8, "start": 1.0}),
                      piece(**{"in": 6.0, "out": 7.2, "start": 2.8})]}  # fmt: skip
    out = pg.mix(edl, const_reader(0.5))
    assert np.abs(out[int(1.1 * SR) : int(2.7 * SR)]).max() < 0.5  # inside the end fade
    # fade runs 1.0 .. 2.6 s, quadratic, then true silence
    assert out[int(2.7 * SR) :].max() == 0
    mid = out[int(1.8 * SR), 0]
    assert mid == pytest.approx(0.0, abs=1e-3)  # the hold is silent
    solo = {"total": 3.0, "fade_start": 0.5, "pieces": [piece(**{"in": 0.0, "out": 3.0, "start": 0.0})]}
    o = pg.mix(solo, const_reader(1.0))
    f0 = int(0.5 * SR)
    k = int(0.8 * SR)  # halfway through the 1.6 s fade: (1 - 0.5)^2
    assert o[f0 + k, 0] == pytest.approx(0.25, abs=0.01)
    assert o[f0 - 5, 0] == pytest.approx(1.0, abs=1e-3)
    assert o[-5, 0] == 0


def test_mix_reads_past_the_source_end_as_silence():
    edl = {"total": 1.0, "fade_start": 5.0, "pieces": [piece(**{"in": 0.0, "out": 1.0})]}
    short = lambda c, i0, i1: np.ones((max(0, min(i1, SR // 2) - i0), 2), np.float32)
    out = pg.mix(edl, short)
    assert out[SR // 4, 0] == 1.0 and out[-100, 0] == 0.0


def test_plan_names_pieces_by_hash_and_dedupes(tmp_path):
    paths = Paths(tmp_path)
    (paths.media / "proxy").mkdir(parents=True)
    (paths.media / "proxy" / "A.mp4").write_bytes(b"x" * 100)
    edl = {"pieces": [piece(), piece(**{"in": 2.0, "out": 3.0})]}
    items = pg.plan(edl, paths, "proxy")
    assert len({d for _, _, d in items}) == 2 and items[0][2].parent == paths.program / "pieces"


def test_render_real_clip_frame_exact(tmp_path):
    """Two pieces and a hold from the 10 s fixture: exact frame counts, a concat that copies, audio mux."""
    import shutil
    from pathlib import Path

    fx = Path(__file__).parent / "fixtures"
    paths = Paths(tmp_path)
    (paths.media / "proxy").mkdir(parents=True)
    shutil.copy(fx / "clip-ar-10s.mp4", paths.media / "proxy" / "A.mp4")
    shutil.copy(fx / "clip-ar-10s.wav", paths.media / "A-48k.wav")
    edl = {"total": 3.8, "fade_start": 3.0, "pieces": [
        {"clip": "A", "in": 1.0, "out": 2.0, "start": 0.0},
        {"clip": "A", "in": 4.0, "out": 4.0, "hold": 1.8, "start": 1.0},
        {"clip": "A", "in": 6.0, "out": 7.0, "start": 2.8}]}  # fmt: skip
    res = pg.render(edl, paths, "proxy")
    assert res["rendered"] == 3 and res["frames"] == round(3.8 * 30) and res["ok"], res
    again = pg.render(edl, paths, "proxy")
    assert again["rendered"] == 0 and again["reused"] == 3
    edl["pieces"][2]["in"], edl["pieces"][2]["out"] = 6.5, 7.5
    assert pg.render(edl, paths, "proxy")["rendered"] == 1
    n = run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets", "-show_entries",
             "stream=nb_read_packets", "-of", "csv=p=0", next((paths.program / "pieces").glob("*.mp4"))], 30)  # fmt: skip
    assert int(n.stdout.strip()) in (30, 54)


def test_master_profile_on_a_short_edl(tmp_path):
    import shutil
    from pathlib import Path

    fx = Path(__file__).parent / "fixtures"
    paths = Paths(tmp_path)
    paths.media.mkdir(parents=True)
    shutil.copy(fx / "clip-ar-10s.mp4", paths.media / "A-cam.mp4")
    shutil.copy(fx / "clip-ar-10s.wav", paths.media / "A-48k.wav")
    edl = {"total": 1.5, "fade_start": 1.0, "pieces": [{"clip": "A", "in": 2.0, "out": 3.0, "start": 0.0},
           {"clip": "A", "in": 5.0, "out": 5.0, "hold": 0.5, "start": 1.0}]}  # fmt: skip
    res = pg.render(edl, paths, "master")
    assert res["frames"] == 90 and res["ok"] and res["path"].endswith("master.mp4"), res
    info = run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_name,width,height",
                "-of", "csv=p=0", res["path"]], 30).stdout.strip()  # fmt: skip
    assert info == "hevc,3840,2160"


def test_piece_past_the_video_end_holds_its_last_frame(tmp_path):
    """The fixture camera's audio outlasts its video (928.44 vs 928.36 s): the last piece must still give
    round(len * fps) frames, or the 4K program comes out short. Only that piece gets the pad."""
    import shutil
    from pathlib import Path

    fx = Path(__file__).parent / "fixtures"
    paths = Paths(tmp_path)
    paths.media.mkdir(parents=True)
    shutil.copy(fx / "clip-ar-10s.mp4", paths.media / "A-cam.mp4")
    shutil.copy(fx / "clip-ar-10s.wav", paths.media / "A-48k.wav")
    end = pg.video_end(paths.media / "A-cam.mp4")
    edl = {"total": 1.5, "fade_start": 1.4, "pieces": [{"clip": "A", "in": 2.0, "out": 2.5, "start": 0.0},
           {"clip": "A", "in": end - 0.9, "out": end + 0.1, "start": 0.5}]}  # fmt: skip
    items = pg.plan(edl, paths, "master")
    assert [bool(p.get("pad")) for p, _, _ in items] == [False, True]
    assert pg.piece_hash(edl["pieces"][0], pg.PROFILES["master"], "x") == pg.piece_hash(
        items[0][0], pg.PROFILES["master"], "x"
    )
    res = pg.render(edl, paths, "master")
    assert res["frames"] == 90 and res["ok"], res
