import json
import os

from vedit import state
from vedit.cli import main
from vedit.project import Project


def make(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x" * 10)
    (tmp_path / "project.yaml").write_text(f"slug: t\nlang: ar\nsources:\n  A: {{ file: {src} }}\n")
    return Project.load(tmp_path)


def record_chain(proj):
    p = proj.paths
    cur = state.current_inputs(proj, p, {})
    state.record_stage(p, "ingest", cur["ingest"])
    cur = state.current_inputs(proj, p, state.load(p)["stages"])
    state.record_stage(p, "transcribe", cur["transcribe"])
    return p


def test_missing_then_done_then_stale(tmp_path):
    proj = make(tmp_path)
    p = proj.paths
    assert set(state.stage_status(proj, p).values()) == {"missing"}
    record_chain(proj)
    st = state.stage_status(proj, p)
    assert st["ingest"] == st["transcribe"] == "done" and st["cut"] == "missing"
    (tmp_path / "cuts.yaml").write_text("a: 1")
    state.record_stage(p, "cut", state.current_inputs(proj, p, state.load(p)["stages"])["cut"])
    assert state.stage_status(proj, p)["cut"] == "done"
    (tmp_path / "cuts.yaml").write_text("a: 2")
    assert state.stage_status(proj, p)["cut"] == "stale"


def test_status_cli_walkup_and_next(tmp_path, capsys):
    make(tmp_path)
    sub = tmp_path / "x" / "y"
    sub.mkdir(parents=True)
    os.chdir(sub)
    assert main(["status", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["stages"]["ingest"] == "missing" and d["next"] == "vedit new"


def test_dead_pid_shows_failed_with_tail(tmp_path, capsys):
    proj = make(tmp_path)
    record_chain(proj)
    log = tmp_path / "render.log"
    log.write_text("one\nboom: out of memory\n")
    state.start_job(proj.paths, "render", 2**22 + 999, log, chunk=3, chunks=8, frame=40, frames=900)
    assert main(["status", "--project", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "failed job" in out and "boom: out of memory" in out and "chunk 3/8" in out
    assert "next: vedit render" in out


def test_live_job_progress(tmp_path, capsys):
    proj = make(tmp_path)
    state.start_job(
        proj.paths, "render", os.getpid(), tmp_path / "l.log", chunk=2, chunks=8, frame=5, frames=90
    )
    assert main(["status", "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "chunk 2/8" in out and "frame 5/90" in out and "next: vedit status" in out


def test_outside_project(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["status"]) == 1
    err = capsys.readouterr().err
    assert "project.yaml" in err and "next:" in err


def test_sample_hash(tmp_path):
    from vedit.run import SAMPLE, sample_hash

    f = tmp_path / "m.bin"
    data = bytearray(b"a" * (5 * SAMPLE))
    f.write_bytes(bytes(data))
    base = sample_hash(f)
    mid = bytearray(data)
    mid[2 * SAMPLE + 7] = ord("z")  # middle: not sampled
    f.write_bytes(bytes(mid))
    assert sample_hash(f) == base
    for i in (5, len(data) - 5):  # first and last MiB are sampled
        d = bytearray(data)
        d[i] = ord("z")
        f.write_bytes(bytes(d))
        assert sample_hash(f) != base
    f.write_bytes(bytes(data) + b"a")  # size
    assert sample_hash(f) != base
    assert sample_hash(tmp_path / "nope") is None
    small = tmp_path / "s.bin"
    small.write_bytes(b"hello")
    assert sample_hash(small) is not None


def test_ingest_hash_follows_cap_media_not_the_folder(tmp_path):
    cap = tmp_path / "X.cap"
    cap.mkdir()
    real = tmp_path / "real"
    real.mkdir()
    (real / "result.mp4").write_bytes(b"export")
    (real / "camera.mp4").write_bytes(b"camera")
    (tmp_path / "project.yaml").write_text(
        f"slug: t\nlang: ar\nsources:\n  A: {{ cap: {cap}, camera: raw }}\n"
    )
    proj = Project.load(tmp_path)
    p = proj.paths
    assert state.current_inputs(proj, p, {})["ingest"] is None  # nothing linked yet
    p.src.mkdir()
    (p.src / "A.mp4").symlink_to(real / "result.mp4")
    (p.src / "A-camera.mp4").symlink_to(real / "camera.mp4")
    h = state.current_inputs(proj, p, {})["ingest"]
    assert h
    (cap / "junk").write_text("folder changes do not matter")
    assert state.current_inputs(proj, p, {})["ingest"] == h
    (real / "camera.mp4").write_bytes(b"camerb")
    assert state.current_inputs(proj, p, {})["ingest"] != h
    (real / "camera.mp4").unlink()
    assert state.current_inputs(proj, p, {})["ingest"] is None


def test_build_and_render_chain_on_what_build_made(tmp_path):
    """build records the status key (so it reads done) plus `made`; render chains on `made`, so a rebuild that
    writes different compositions makes the master stale even when cues/cut/style did not change."""
    proj = make(tmp_path)
    p = record_chain(proj)
    (tmp_path / "cuts.yaml").write_text("a: 1")
    state.record_stage(p, "cut", state.current_inputs(proj, p, state.load(p)["stages"])["cut"])
    (tmp_path / "cues.yaml").write_text("cues: []")
    cur = lambda: state.current_inputs(proj, p, state.load(p)["stages"])
    state.record_stage(p, "build", cur()["build"], made="m1")
    state.record_stage(p, "render", cur()["render"])
    st = state.stage_status(proj, p)
    assert st["build"] == "done" and st["render"] == "done"
    state.record_stage(p, "build", cur()["build"], made="m2")  # same inputs, different output
    st = state.stage_status(proj, p)
    assert st["build"] == "done" and st["render"] == "stale"
    (tmp_path / "cues.yaml").write_text("cues: [x]")
    assert state.stage_status(proj, p)["build"] == "stale"


def test_build_and_cut_refuse_while_a_render_runs(tmp_path, capsys):
    proj = make(tmp_path)
    p = record_chain(proj)
    state.start_job(p, "render", os.getpid(), tmp_path / "render.log", step="chunks")
    for cmd in ("build", "cut"):
        assert main([cmd, "--project", str(tmp_path)]) == 3  # busy
        c = capsys.readouterr()
        out = c.out + c.err
        assert "4K render is running" in out and "vedit wait" in out
