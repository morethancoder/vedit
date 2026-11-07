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


def test_cap_tilde_and_camera(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "x.cap").mkdir()
    p = Project.load(
        make(tmp_path, "slug: d\nlang: en\nsources:\n  A: { cap: '~/x.cap', camera: raw }\n", media=False)
    )
    assert p.sources["A"].cap == (tmp_path / "x.cap") and p.sources["A"].camera == "raw"


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
