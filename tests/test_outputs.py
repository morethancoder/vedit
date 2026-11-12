import json

import pytest

from vedit import cli
from vedit import outputs as om
from vedit.project import Project, ProjectError, parse_outputs

WORDS = [
    {"t0": i * 0.5, "t1": i * 0.5 + 0.4, "w": w}
    for i, w in enumerate(
        [
            "hello",
            "there",
            "today",
            "we",
            "talk",
            "about",
            "bots",
            "and",
            "how",
            "they",
            "scale",
            "to",
            "many",
            "users",
            "at",
            "once",
            "thanks",
        ]
    )
]


def make(tmp_path, extra=""):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    root = tmp_path / "p"
    (root / ".vedit" / "words").mkdir(parents=True)
    (root / ".vedit" / "words" / "A.json").write_text(json.dumps(WORDS))
    (root / "project.yaml").write_text(
        f"# my project\nslug: p\nlang: en\nsources:\n  A: {{ file: {src} }}  # the camera\n{extra}"
    )
    return root


def test_no_outputs_means_one_youtube_master(tmp_path):
    p = Project.load(make(tmp_path))
    assert [(o.id, o.kind, o.aspect, o.platforms, o.captions) for o in p.outputs] == [
        ("youtube", "master", "16:9", ["youtube"], "srt")
    ]


def test_defaults_by_kind():
    outs = parse_outputs(
        [
            {"id": "yt"},
            {"id": "s", "kind": "short"},
            {"id": "st", "kind": "story"},
            {"id": "p", "kind": "post"},
        ],
        "f",
    )
    assert [(o.aspect, o.captions) for o in outs] == [("16:9", "srt"), ("9:16", "burned"), ("9:16", "burned"),
                                                       ("4:5", "burned")]  # fmt: skip
    assert outs[1].platforms == ["instagram-reels", "tiktok", "youtube-shorts"]


@pytest.mark.parametrize(
    "spec, why",
    [
        ({"id": "Bad Id"}, "lowercase"),
        ({"id": "a", "kind": "reel"}, "kind"),
        ({"id": "a", "aspect": "5:7"}, "aspect"),
        ({"id": "a", "kind": "short", "platforms": ["youtube"]}, "Drop youtube"),
        ({"id": "a", "kind": "clip"}, "range"),
        ({"id": "a", "kind": "short", "range": {"from": "x", "to": "y"}}, "only for clips and stories"),
        ({"id": "a", "colour": 1}, "unknown key"),
        ({"id": "a", "platforms": ["myspace"]}, "unknown"),
        ({"id": "a", "kind": "short", "fill": "gradient"}, "fill"),
    ],
)
def test_bad_outputs_are_refused(spec, why):
    with pytest.raises(ProjectError) as e:
        parse_outputs([spec], "f")
    assert why in str(e.value)


def test_clip_range_resolves_to_words(tmp_path):
    root = make(tmp_path)
    p = Project.load(root)
    (o,) = parse_outputs([{"id": "c", "kind": "clip", "range": {"from": "we talk", "to": "many users"}}], "f")
    r = om.resolve_range(p, o)
    assert (r.clip, r.t0, r.t1) == ("A", 1.5, 6.9)


def test_write_keeps_other_lines_and_round_trips(tmp_path):
    root = make(tmp_path)
    f = root / "project.yaml"
    before = f.read_text()
    outs = parse_outputs([{"id": "youtube"}, {"id": "s", "kind": "short"}], f)
    om.write(f, outs)
    assert f.read_text().startswith(before)
    assert [o.id for o in Project.load(root).outputs] == ["youtube", "s"]
    om.write(f, outs[:1])
    assert f.read_text().count("outputs:") == 1 and [o.id for o in Project.load(root).outputs] == ["youtube"]
    om.write(f, None)
    assert f.read_text() == before


def test_output_command_add_list_rm(tmp_path, capsys):
    root = make(tmp_path)
    a = ["--project", str(root), "--json"]
    assert cli.main(["output", "add", "c1", "--from", "we talk", "--to", "many users", *a]) == 0
    capsys.readouterr()
    assert cli.main(["output", "add", "c2", "--from", "we talk", "--to", "nowhere", *a]) == 4
    capsys.readouterr()
    assert cli.main(["output", "list", *a]) == 0
    d = json.loads(capsys.readouterr().out)["data"]
    assert [o["id"] for o in d["outputs"]] == ["youtube", "c1"] and d["explicit"]
    assert d["outputs"][1]["resolved"]["t0"] == 1.5 and d["outputs"][1]["safe_box"]["x"] == 120
    assert cli.main(["output", "rm", "c1", *a]) == 0
    assert cli.main(["output", "rm", "youtube", *a]) == 4  # the last output stays


def test_fill_is_plain_unless_asked():
    outs = parse_outputs([{"id": "s", "kind": "short"}, {"id": "b", "kind": "short", "fill": "blur"}], "f")
    assert [o.fill for o in outs] == ["plain", "blur"]
    assert "fill" not in outs[0].as_dict() and outs[1].as_dict()["fill"] == "blur"
