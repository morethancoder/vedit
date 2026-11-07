import json
from pathlib import Path

import pytest

from vedit import state
from vedit.commands import draft
from vedit.render import hf
from vedit.report import VeditError
from vedit.versions import HYPERFRAMES


def test_render_cmd_defaults():
    cmd = hf.render_cmd("/p/hf", "/p/out.mp4")
    assert cmd[:5] == ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", "render", "/p/hf"]
    assert cmd[cmd.index("-o") + 1] == "/p/out.mp4"
    assert cmd[cmd.index("-q") + 1] == "draft"
    assert cmd[cmd.index("--resolution") + 1] == "1080p"
    assert "--gpu" in cmd and "--browser-gpu" in cmd and "--quiet" in cmd
    assert "-f" not in cmd and not any(c.startswith("--frames-cache-dir") for c in cmd)


def test_render_cmd_master_options():
    cmd = hf.render_cmd("a", "b", quality="high", resolution="4k", fps=60, frames_cache_dir="/c", quiet=False)
    assert cmd[cmd.index("-q") + 1] == "high"
    assert cmd[cmd.index("--resolution") + 1] == "4k"
    assert cmd[cmd.index("-f") + 1] == "60"
    assert "--frames-cache-dir=/c" in cmd and "--quiet" not in cmd
    assert "--gpu" in cmd and "--browser-gpu" in cmd


def test_render_cmd_rejects_bad_values():
    with pytest.raises(ValueError):
        hf.render_cmd("a", "b", quality="ultra")
    with pytest.raises(ValueError):
        hf.render_cmd("a", "b", resolution="8k")


def test_render_env():
    assert hf.render_env(parallel_stream=True) == {"HF_CAPTURE_PARALLEL_STREAM": "true"}
    assert hf.render_env() == {}


def test_hf_hash_tracks_content_and_ignores_cache(tmp_path):
    (tmp_path / "index.html").write_text("a")
    (tmp_path / ".hyperframes").mkdir()
    (tmp_path / ".hyperframes" / "x").write_text("1")
    h1 = draft.hf_hash(tmp_path)
    (tmp_path / ".hyperframes" / "x").write_text("2")
    assert draft.hf_hash(tmp_path) == h1
    (tmp_path / "index.html").write_text("b")
    assert draft.hf_hash(tmp_path) != h1


def _project(tmp_path):
    root = tmp_path / "p"
    (root / ".vedit" / "hf").mkdir(parents=True)
    (root / ".vedit" / "hf" / "index.html").write_text("<html/>")
    (root / "vedit.yaml").write_text("slug: p\nlang: en\nsources: {}\n")
    return root


class NS:
    def __init__(self, root, force=False, no_open=True):
        self.project, self.force, self.no_open = str(root), force, no_open


@pytest.fixture
def fake(monkeypatch):
    calls = []

    def sh(cmd, timeout, **kw):
        calls.append(list(cmd))
        if cmd[0] == "npx":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 10)

    monkeypatch.setattr(draft, "sh", sh)
    monkeypatch.setattr(
        draft, "ffprobe_json", lambda p: {"format": {"duration": "10"}, "streams": [{"codec_type": "audio"}]}
    )
    monkeypatch.setattr(draft, "ffprobe_duration", lambda p: 10.0)
    return calls


def test_draft_renders_then_skips(tmp_path, fake, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    r = draft.run(NS(root))
    assert r.data["skipped"] is False and r.data["audio"] is True
    assert sum(c[0] == "npx" for c in fake) == 1
    r2 = draft.run(NS(root))
    assert r2.data["skipped"] is True
    assert sum(c[0] == "npx" for c in fake) == 1
    r3 = draft.run(NS(root, force=True))
    assert r3.data["skipped"] is False
    assert sum(c[0] == "npx" for c in fake) == 2
    (root / ".vedit" / "hf" / "index.html").write_text("<html>new</html>")
    assert draft.run(NS(root)).data["skipped"] is False
    json.dumps(r.to_dict())


def test_draft_open_and_no_open(tmp_path, fake, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    draft.run(NS(root, no_open=False))
    assert ["open", "-a", "QuickTime Player"] == fake[-1][:3]
    assert not any("preview" in c for call in fake for c in call)


def test_draft_wrong_length_fails(tmp_path, fake, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    monkeypatch.setattr(draft, "ffprobe_duration", lambda p: 99.0)
    (root / ".vedit" / "program").mkdir()
    (root / ".vedit" / "program" / "proxy.mp4").write_bytes(b"x")
    with pytest.raises(VeditError):
        draft.run(NS(root))
    assert state.job_state(_P(root).paths) == "failed"


def test_draft_needs_build(tmp_path, monkeypatch):
    root = tmp_path / "q"
    (root / ".vedit").mkdir(parents=True)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    with pytest.raises(VeditError) as e:
        draft.run(NS(root))
    assert e.value.next == "vedit build"


class _P:
    def __init__(self, root):
        from vedit.project import Paths

        self.paths = Paths(root)


def test_hf_hash_ignores_chunk_files(tmp_path):
    (tmp_path / "index.html").write_text("a")
    (tmp_path / "chunks.json").write_text("{}")
    h = draft.hf_hash(tmp_path)
    (tmp_path / "chunks.json").write_text('{"k": 1}')
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks" / "chunk-00.html").write_text("x")
    assert draft.hf_hash(tmp_path) == h


def test_clean_work_removes_scratch(tmp_path):
    (tmp_path / "work-abc").mkdir()
    (tmp_path / ".draft.part.hf-transaction-x").mkdir()
    (tmp_path / "draft.mp4").write_bytes(b"x")
    (tmp_path / "chunks").mkdir()
    draft.clean_work(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["chunks", "draft.mp4"]


def test_failed_render_keeps_old_draft_and_cleans(tmp_path, fake, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    draft.run(NS(root))
    renders = root / ".vedit" / "renders"
    (renders / "work-1").mkdir()
    monkeypatch.setattr(draft, "ffprobe_json", lambda p: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(VeditError):
        draft.run(NS(root, force=True))
    assert (renders / "draft.mp4").read_bytes() == b"x" * 10
    assert not (renders / "work-1").exists() and not (renders / "draft.part.mp4").exists()


def test_render_cmd_always_turns_fast_capture_off_and_takes_a_composition():
    cmd = hf.render_cmd("a", "b", composition="chunks/chunk-00.html")
    assert "--experimental-fast-capture=false" in cmd
    assert cmd[cmd.index("-c") + 1] == "chunks/chunk-00.html"
    assert "-c" not in hf.render_cmd("a", "b")


def _chunked(root, bounds=(0, 4, 10)):
    h = root / ".vedit" / "hf"
    (h / "chunks").mkdir()
    for i in range(len(bounds) - 1):
        (h / "chunks" / f"chunk-{i:02d}.html").write_text(f"<html>{i}</html>")
    (h / "chunks.json").write_text(json.dumps({"bounds": list(bounds), "total": bounds[-1], "mattes": {}}))
    (h / "compositions").mkdir()
    (h / "compositions" / "a.html").write_text("a")
    return h


@pytest.fixture
def chunked(tmp_path, fake, monkeypatch):
    root = _project(tmp_path)
    h = _chunked(root)
    monkeypatch.setattr(draft.Project, "load", classmethod(lambda cls, r: _P(root)))
    monkeypatch.setattr(draft, "find_project", lambda override=None: root)
    lengths = {"chunk-00": 4.0, "chunk-01": 6.0}
    monkeypatch.setattr(draft, "ffprobe_duration", lambda p: lengths.get(Path(p).name.split(".")[0], 10.0))
    joins = []

    def join(parts, secs, out, work, log):
        joins.append(([p.name for p in parts], secs))
        tmp = out.with_name(out.stem + ".tmp.mp4")
        tmp.write_bytes(b"j" * 10)
        return tmp

    monkeypatch.setattr(draft.master, "join", join)
    return root, h, joins


def _chunk_renders(calls):
    return [c[c.index("-c") + 1] for c in calls if c[0] == "npx"]


def test_draft_renders_chunks_and_joins(chunked, fake):
    root, _h, joins = chunked
    r = draft.run(NS(root))
    assert sorted(_chunk_renders(fake)) == ["chunks/chunk-00.html", "chunks/chunk-01.html"]
    assert joins == [(["chunk-00.mp4", "chunk-01.mp4"], [4, 6])]
    assert r.data["chunks"] == {"rendered": 2, "reused": 0}
    assert (root / ".vedit" / "renders" / "draft.mp4").read_bytes() == b"j" * 10


def test_draft_rerenders_only_the_changed_chunk(chunked, fake):
    root, h, _joins = chunked
    draft.run(NS(root))
    (h / "chunks" / "chunk-01.html").write_text("<html>changed</html>")
    (h / "index.html").write_text("<html>changed</html>")
    r = draft.run(NS(root))
    assert sorted(_chunk_renders(fake)) == [
        "chunks/chunk-00.html",
        "chunks/chunk-01.html",
        "chunks/chunk-01.html",
    ]
    assert r.data["chunks"] == {"rendered": 1, "reused": 1}
    (h / "compositions" / "a.html").write_text("b")  # shared file: every chunk again
    assert draft.run(NS(root)).data["chunks"] == {"rendered": 2, "reused": 0}


def test_draft_chunk_of_wrong_length_fails(chunked, fake, monkeypatch):
    root, _h, _joins = chunked
    monkeypatch.setattr(draft, "ffprobe_duration", lambda p: 1.0)
    with pytest.raises(VeditError):
        draft.run(NS(root))
    parts = root / ".vedit" / "renders" / "draft-parts"
    assert not list(parts.glob("*.key")) and not list(parts.glob("*.tmp.mp4"))


def test_draft_chunks_none_without_chunks_json(tmp_path):
    assert draft.draft_chunks(tmp_path) is None
