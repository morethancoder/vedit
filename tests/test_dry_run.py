"""--dry-run on new, cut, build and subs: reports the plan and leaves the project tree byte-identical."""

import json
import shutil
from types import SimpleNamespace

from tests.test_cut_cmd import make_project
from tests.test_new import CLIP
from vedit import llm
from vedit.cli import main
from vedit.commands import build as buildcmd
from vedit.graphics import cutouts, pages
from vedit.project import Paths
from vedit.report import Report


def tree(root):
    """Every file and link with its size and modification time: equal means nothing was written."""
    if not root.exists():
        return None
    return sorted(
        (str(p.relative_to(root)), p.lstat().st_size, p.lstat().st_mtime_ns) for p in root.rglob("*")
    )


def data(capsys):
    return json.loads(capsys.readouterr().out)["data"]


def test_new_dry_run_creates_nothing_then_reports_reuse(tmp_path, capsys):
    f = tmp_path / "talk.mp4"
    shutil.copy(CLIP, f)
    out = tmp_path / "out"
    assert main(["new", str(f), "--dir", str(out), "--lang", "en", "--dry-run", "--json"]) == 0
    d = data(capsys)
    assert not out.exists() and d["created"] and d["model_calls"] == 0
    assert d["build"] == ["proxy/A.mp4", "A-48k.wav", "sheet/A.jpg"] and "src/A.mp4" in d["writes"]
    assert main(["new", str(f), "--dir", str(out), "--lang", "en"]) == 0
    capsys.readouterr()
    before = tree(out)
    assert main(["new", str(f), "--dir", str(out), "--lang", "en", "--dry-run", "--json"]) == 0
    d = data(capsys)
    assert d["build"] == [] and len(d["reuse"]) == 3 and not d["created"]
    assert tree(out) == before


def test_cut_dry_run_matches_the_real_edl_and_writes_nothing(tmp_path, capsys):
    root = make_project(tmp_path, "cuts:\n  - {near: A 1.0, say: two}\nend: last-word\n")
    before = tree(root)
    args = ["cut", "--edl-only", "--no-listen", "--project", str(root), "--json"]
    assert main([*args, "--dry-run"]) == 0
    d = data(capsys)
    assert tree(root) == before and d["dry_run"] and d["cuts"] == 1 and d["renders"] == {}
    assert main([*args, "--wait"]) == 0
    capsys.readouterr()
    real = json.loads((root / ".vedit/edl/edl.json").read_text())
    assert d["total"] == real["total"] and d["pieces"] == len(real["pieces"])


def test_subs_dry_run_counts_batches_without_asking(tmp_path, capsys, monkeypatch):
    root = tmp_path / "p"
    (root / ".vedit/program").mkdir(parents=True)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    (root / "project.yaml").write_text(f"slug: p\nlang: en\nsources:\n  A: {{ file: {src} }}\n")
    words = [{"t0": i * 0.5, "t1": i * 0.5 + 0.4, "w": f"word{i}."} for i in range(400)]
    (root / ".vedit/program/P.words.json").write_text(json.dumps(words))
    monkeypatch.setattr(llm, "ask", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model asked")))
    before = tree(root)
    assert main(["subs", "--dry-run", "--json", "--project", str(root)]) == 0
    d = data(capsys)
    assert (
        d["batches"] >= 2 and d["to_ask"] == d["batches"] and d["model_calls"]["llm_batches"] == d["batches"]
    )
    assert tree(root) == before


def test_build_dry_run_compares_page_keys_and_cutouts(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    comp = paths.hf / "compositions"
    comp.mkdir(parents=True)
    for i in ("same", "changed", "gone"):
        (comp / f"{i}.html").write_text("<b/>")
    (paths.hf / "manifest.json").write_text(
        json.dumps({"comps": {i: {"key": f"k-{i}"} for i in ("same", "changed", "gone")}})
    )
    item = lambda pid, typ="label": SimpleNamespace(id=pid, cue=SimpleNamespace(type=typ), start=1.0, dur=2.0)
    plan = SimpleNamespace(items=[item("same"), item("changed"), item("big", "big-number")], problems=list)
    monkeypatch.setattr(pages, "key", lambda p, pk, env: "k-same" if p.id == "same" else "new")
    monkeypatch.setattr(cutouts, "stale", lambda paths, ranges: list(ranges))
    before = tree(tmp_path)
    project = SimpleNamespace(slug="p", outputs=[SimpleNamespace(id="reel", aspect="9:16")])
    ns = SimpleNamespace(output=None, no_check=False)
    r = buildcmd._dry_run(Report("build"), paths, plan, lambda c: None, None, project, ns)
    assert r.data["write"] == ["changed", "big"] and r.data["unchanged"] == 1 and r.data["remove"] == ["gone"]
    assert r.data["cutouts"] == {"make": ["mt-big"], "reused": 0} and r.data["outputs"] == ["reel"]
    assert tree(tmp_path) == before
