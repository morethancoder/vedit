import json

import pytest

from vedit import llm


def prompt(model="haiku", batch=0, schema=None):
    schema = schema or {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    }
    return llm.Prompt(name="t", model=model, schema=schema, body="{{context}}\n{{input}}", batch=batch)


@pytest.fixture
def calls(monkeypatch):
    """Scripted backends: queue replies (text, or an exception) per model id; record every call."""
    script: dict[str, list] = {}
    seen: list[tuple[str, str]] = []

    def fake(mid, text, effort, timeout):
        seen.append((mid, text))
        nxt = script[mid].pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return llm.Reply(nxt, mid, 10, 5, 0.001)

    monkeypatch.setitem(llm.BACKENDS, "claude", fake)
    monkeypatch.setitem(llm.BACKENDS, "ollama", fake)
    return script, seen


def test_shipped_prompts_load():
    names = llm.prompt_names()
    assert {"summary", "cuts"} <= set(names)
    for n in names:
        p = llm.load_prompt(n)
        assert p.model in llm.MODELS and p.schema.get("type") == "object"
        assert "{{input}}" in p.body and "{{context}}" in p.body


def test_chain_starts_at_preferred_model():
    assert llm.chain(prompt("haiku")) == ["haiku", "sonnet", "gemma"]
    assert llm.chain(prompt("sonnet")) == ["sonnet", "gemma"]
    assert llm.chain(prompt("sonnet"), "haiku") == ["haiku"]


def test_parse_json_tolerates_fences_and_prose():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Here it is: {"a": [1]} done') == {"a": [1]}
    with pytest.raises(llm.Invalid):
        llm.parse_json("no json here")


def test_validate():
    s = prompt().schema
    llm.validate({"items": ["x"]}, s)
    with pytest.raises(llm.Invalid, match="missing"):
        llm.validate({}, s)
    with pytest.raises(llm.Invalid, match=r"\$\.items\[0\]"):
        llm.validate({"items": [1]}, s)
    with pytest.raises(llm.Invalid, match="not in"):
        llm.validate("z", {"enum": ["a"]})
    with pytest.raises(llm.Invalid):
        llm.validate(True, {"type": "number"})


def test_ok_first_try_logs(calls, tmp_path):
    script, seen = calls
    script["claude-haiku-5-5"] = ['{"items": ["a"]}']
    log = tmp_path / "llm.jsonl"
    res = llm.ask(prompt(), "hello", vars={"context": "ctx"}, log=log)
    assert res.values == [{"items": ["a"]}] and res.models == ["haiku"] and not res.fallbacks
    assert seen[0][1] == "ctx\nhello"
    entry = json.loads(log.read_text())
    assert entry["ok"] and entry["model"] == "haiku" and entry["tokens_in"] == 10


def test_invalid_retries_three_times_then_falls_back(calls, tmp_path):
    script, seen = calls
    script["claude-haiku-5-5"] = ["nope", '{"items": [1]}', "{}"]
    script["claude-sonnet-5-5"] = ['{"items": ["ok"]}']
    log = tmp_path / "llm.jsonl"
    res = llm.ask(prompt(), "x", vars={"context": ""}, log=log)
    assert [m for m, _ in seen] == ["claude-haiku-5-5"] * 3 + ["claude-sonnet-5-5"]
    assert res.models == ["sonnet"] and "invalid output" in res.fallbacks[0]
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert [e["ok"] for e in lines] == [False, False, False, True]
    assert lines[-1]["fallback"].startswith("haiku: invalid output")


def test_limit_moves_on_at_once(calls):
    script, seen = calls
    script["claude-haiku-5-5"] = [llm.Unavailable("limit: weekly limit reached")]
    script["claude-sonnet-5-5"] = [llm.Unavailable("limit: usage limit")]
    script["gemma4:31b-cloud"] = ['{"items": []}']
    res = llm.ask(prompt(), "x", vars={"context": ""})
    assert [m for m, _ in seen] == ["claude-haiku-5-5", "claude-sonnet-5-5", "gemma4:31b-cloud"]
    assert res.models == ["gemma"]


def test_forced_model_has_no_fallback(calls):
    script, _ = calls
    script["claude-sonnet-5-5"] = [llm.Unavailable("error: boom")]
    with pytest.raises(llm.LlmError, match="every model failed"):
        llm.ask(prompt(), "x", vars={"context": ""}, model="sonnet")


def test_batches_and_check(calls):
    script, seen = calls
    script["claude-haiku-5-5"] = ['{"items": ["a"]}', '{"items": ["bad"]}', '{"items": ["c"]}']

    def check(value, text):
        if value["items"][0] == "bad":
            raise llm.Invalid("bad item")

    res = llm.ask(prompt(batch=2), "1\n2\n3\n", vars={"context": ""}, check=check)
    assert res.values == [{"items": ["a"]}, {"items": ["c"]}]
    assert seen[0][1].endswith("1\n2\n") and seen[1][1].endswith("3\n")
    assert "REJECTED: bad item" in seen[2][1] and "\n3\n" in seen[2][1]  # the retry says what was wrong


def test_missing_var_is_an_error():
    with pytest.raises(llm.VeditError, match="context"):
        prompt().render(input="x")


def test_claude_command_switches_off_claude_code_extras(monkeypatch):
    got = {}

    class P:
        returncode, stderr = 0, ""
        stdout = json.dumps(
            {
                "result": '{"a": 1}',
                "is_error": False,
                "usage": {"input_tokens": 3, "cache_creation_input_tokens": 800, "output_tokens": 4},
                "modelUsage": {"claude-haiku-5-5": {}},
                "total_cost_usd": 0.0002,
            }
        )

    def fake_run(cmd, timeout, check=True, **kw):
        got["cmd"] = cmd
        return P()

    monkeypatch.setattr(llm, "run", fake_run)
    rep = llm.call_claude("claude-haiku-5-5", "PROMPT", "low", 60)
    cmd = got["cmd"]
    assert cmd[-1] == "PROMPT" and cmd[cmd.index("--tools") + 1] == ""
    for flag in ("--system-prompt", "--strict-mcp-config", "--setting-sources", "--no-session-persistence"):
        assert flag in cmd
    assert rep.tokens_in == 803 and rep.tokens_out == 4 and rep.text == '{"a": 1}'


def test_claude_limit_is_unavailable(monkeypatch):
    class P:
        returncode, stderr = 1, ""
        stdout = json.dumps({"is_error": True, "result": "Claude AI usage limit reached"})

    monkeypatch.setattr(llm, "run", lambda *a, **k: P())
    with pytest.raises(llm.Unavailable, match="^limit"):
        llm.call_claude("claude-haiku-5-5", "x", None, 60)
