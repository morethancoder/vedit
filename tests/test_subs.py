import json

import pytest

from vedit import llm
from vedit.commands import subs as cmd
from vedit.subs import cues, srt


def w(text, t0, t1):
    return {"t0": t0, "t1": t1, "w": text}


def test_split_on_gap():
    ws = [w("a", 0, 0.5), w("b", 0.5, 1.0), w("c", 1.7, 2.0)]
    out = cues.build(ws)
    assert [c["text"] for c in out] == ["a b", "c"]
    assert [c["id"] for c in out] == [1, 2]


def test_no_split_below_gap():
    ws = [w("a", 0, 0.5), w("b", 1.0, 1.5)]  # gap 0.5 < 0.6
    assert len(cues.build(ws)) == 1


def test_max_chars_and_duration():
    ws = [w("x" * 20, i * 0.5, i * 0.5 + 0.5) for i in range(12)]
    out = cues.build(ws)
    assert all(len(c["text"]) <= 84 for c in out)
    slow = [w("ab", i * 1.0, i * 1.0 + 1.0) for i in range(10)]
    assert all(c["t1"] - c["t0"] <= 6.0 for c in cues.build(slow))
    assert len(cues.build(slow)) > 1


def test_sentence_end_splits_after_30_chars():
    ws = [w("x" * 31 + ".", 0, 1), w("next", 1.0, 1.5)]
    assert len(cues.build(ws)) == 2
    assert len(cues.build([w("short.", 0, 1), w("next", 1.0, 1.5)])) == 1


def test_min_duration_and_no_overlap():
    out = cues.build([w("a", 0, 0.1), w("b", 1.0, 1.1)])
    assert out[0]["t1"] - out[0]["t0"] == pytest.approx(0.8)
    assert out[0]["t1"] < out[1]["t0"]


def test_rtl_marks():
    text = srt.rtl_text("افتح ملف .env ثم شغل --watch و Claude")
    assert text.startswith(srt.RLM)
    assert srt.LRM + ".env" in text
    assert srt.LRM + "--watch" in text
    assert srt.LRM + "Claude" not in text  # Latin names stay as they are
    assert srt.LRM + "ثم" not in text


def test_rtl_mark_on_every_line():
    text = srt.rtl_text("كلمة " * 14)
    assert len(text.split("\n")) == 2
    assert all(ln.startswith(srt.RLM) for ln in text.split("\n"))


def test_srt_render():
    cs = [{"id": 1, "t0": 0.25, "t1": 1.5}]
    assert srt.render(cs, {1: "hi"}, rtl=False) == "1\n00:00:00,250 --> 00:00:01,500\nhi\n"
    assert srt.render(cs, {1: "مرحبا"}, rtl=True).split("\n")[2] == srt.RLM + "مرحبا"


def test_checker_ids_round_trip():
    check = cmd.checker({"1", "2"})
    check({"src": {"1": "a", "2": "b"}, "tr": {"1": "a", "2": "b"}}, "")
    with pytest.raises(llm.Invalid, match="missing"):
        check({"src": {"1": "a"}, "tr": {"1": "a", "2": "b"}}, "")
    with pytest.raises(llm.Invalid, match="extra"):
        check({"src": {"1": "a", "2": "b"}, "tr": {"1": "a", "2": "b", "3": "c"}}, "")


def test_translate_batches_and_cache(tmp_path, monkeypatch):
    cs = [{"id": i, "t0": i, "t1": i + 1, "text": f"t{i}"} for i in range(1, 86)]
    calls = []

    def fake_ask(prompt, text, *, vars=None, model=None, log=None, check=None):
        ids = [ln.split(":")[0] for ln in text.splitlines()]
        value = {"src": {i: f"s{i}" for i in ids}, "tr": {i: f"e{i}" for i in ids}}
        check(value, text)
        calls.append(len(ids))
        return llm.Result([value], ["sonnet"])

    monkeypatch.setattr(llm, "ask", fake_ask)
    prompt = llm.load_prompt("subs")
    vars = {"context": "", "src_lang": "Arabic", "tr_lang": "English"}
    src, tr, use = cmd.translate(cs, prompt, vars, "auto", tmp_path / "c", tmp_path / "l", False)
    assert calls == [40, 40, 5] and use["batches"] == 3 and use["cached"] == 0
    assert src[85] == "s85" and tr[1] == "e1"
    cmd.translate(cs, prompt, vars, "auto", tmp_path / "c", tmp_path / "l", False)
    assert calls == [40, 40, 5]  # second run: all cached
    json.dumps(src)


def test_overlapping_words_never_give_negative_duration():
    out = cues.build([w("a", 5.0, 5.2), w("b", 6.0, 6.1), w("c", 5.1, 5.5)])
    assert all(c["t1"] > c["t0"] for c in out)
