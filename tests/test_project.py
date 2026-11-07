import pytest

from vedit.project import Project, ProjectError, find_project

GOOD = "slug: demo\nlang: ar\ndialect: iq\nsources:\n  A: { file: src/a.mov }\n"


def make(tmp_path, text=GOOD, media=True):
    (tmp_path / "project.yaml").write_text(text)
    if media:
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "a.mov").write_bytes(b"")
    return tmp_path


def test_valid_load_and_defaults(tmp_path):
    p = Project.load(make(tmp_path))
    assert (p.slug, p.lang, p.dialect, p.style, p.logos) == ("demo", "ar", "iq", None, [])
    assert p.sources["A"].path == (tmp_path / "src/a.mov").resolve()
    assert not (tmp_path / ".vedit").exists()


def test_camera_source_tilde_trims(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for n in ("e.mp4", "c0.mov", "c1.mov"):
        (tmp_path / n).write_bytes(b"x")
    p = Project.load(make(tmp_path, (
        "slug: d\nlang: en\nsources:\n  A: { file: '~/e.mp4', camera: ['~/c0.mov', '~/c1.mov'],"
        " trims: [[0, 0, 1.5], [1, 2, 3]], fps: 25, mirror: true, origin: '~/gone.rec', importer: x }\n"), media=False))  # fmt: skip
    s = p.sources["A"]
    assert s.file == tmp_path / "e.mp4" and s.camera == [tmp_path / "c0.mov", tmp_path / "c1.mov"]
    assert [(t.track, t.start, t.end) for t in s.trims] == [(0, 0.0, 1.5), (1, 2.0, 3.0)]
    assert s.fps == 25 and s.mirror and s.origin == tmp_path / "gone.rec" and s.importer == "x" and s.punch_in


@pytest.mark.parametrize(
    "spec,frag",
    [
        ("{ camera: src/a.mov }", "needs 'file'"),
        ("{ file: src/a.mov, trims: [[0, 0, 1]] }", "needs a camera"),
        ("{ file: src/a.mov, camera: src/a.mov, trims: [[1, 0, 1]] }", "no camera file"),
        ("{ file: src/a.mov, camera: src/a.mov, trims: [[0, 2, 1]] }", "end > start"),
        ("{ file: src/a.mov, fps: 0 }", "whole number"),
        ("{ file: src/a.mov, mirror: yes please }", "true or false"),
        ("{ file: src/a.mov, recorder: x }", "unknown key 'recorder'"),
    ],
)
def test_bad_sources(tmp_path, spec, frag):
    with pytest.raises(ProjectError, match=frag):
        Project.load(make(tmp_path, f"slug: d\nlang: en\nsources:\n  A: {spec}\n"))


@pytest.mark.parametrize(
    "text,frag",
    [
        (GOOD + "stlye: x\n", "Did you mean 'style'"),
        ("slug: d\nlang: ar\n", "missing required key 'sources'"),
        ("lang: ar\nsources:\n  A: { file: src/a.mov }\n", "missing required key 'slug'"),
        ("slug: d\nlang: fr\nsources:\n  A: { file: src/a.mov }\n", "use one of: ar, en"),
        ("slug: 5\nlang: ar\nsources:\n  A: { file: src/a.mov }\n", "must be a string"),
        ("slug: d\nlang: ar\nsources: [a]\n", "must be a mapping"),
        ("slug: d\nlang: ar\nsources:\n  A: { file: src/gone.mov }\n", "does not exist"),
        ("slug: d\nlang: ar\nsources:\n  A: { fil: src/a.mov }\n", "Did you mean 'file'"),
        ("slug: [\n", "not valid YAML"),
    ],
)
def test_errors(tmp_path, text, frag):
    make(tmp_path, text)
    with pytest.raises(ProjectError, match=frag) as e:
        Project.load(tmp_path)
    assert "project.yaml" in str(e.value)


def test_walk_up_and_override(tmp_path):
    make(tmp_path)
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find_project(deep) == tmp_path.resolve()
    other = tmp_path / "other"
    other.mkdir()
    (other / "project.yaml").write_text(GOOD)
    assert find_project(deep, str(other)) == other.resolve()
    with pytest.raises(ProjectError, match="not found"):
        find_project(deep, str(deep))


def test_no_project(tmp_path):
    with pytest.raises(ProjectError, match="no project.yaml found from .* up — run vedit new"):
        find_project(tmp_path)


def test_paths_and_ensure(tmp_path):
    p = Project.load(make(tmp_path)).paths
    r = tmp_path.resolve()
    assert (p.src, p.summary, p.cuts, p.cues, p.custom) == (
        r / "src",
        r / "summary.md",
        r / "cuts.yaml",
        r / "cues.yaml",
        r / "custom",
    )
    assert p.state == r / ".vedit/state.json"
    assert [d.name for d in p.vedit_dirs()] == [
        "media",
        "studio",
        "words",
        "edl",
        "program",
        "mattes",
        "hf",
        "renders",
        "logs",
    ]
    p.ensure()
    assert all(d.is_dir() for d in p.vedit_dirs())
