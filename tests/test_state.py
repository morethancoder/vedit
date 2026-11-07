import json
import os

from vedit import state
from vedit.project import Paths


def test_roundtrip_and_atomic(tmp_path):
    p = Paths(tmp_path)
    state.start_job(p, "render", os.getpid(), tmp_path / "r.log", command="render", chunk=0, chunks=4)
    state.update_progress(p, chunk=2, frame=10, frames=100)
    d = json.loads(p.state.read_text())
    assert d["job"]["progress"] == {"chunk": 2, "chunks": 4, "frame": 10, "frames": 100}
    assert not list(p.vedit.glob(".state-*"))
    state.record_stage(p, "cut", "abc", ["x.mp4"])
    assert state.load(p)["stages"]["cut"]["inputs"] == "abc"
    assert state.load(p)["job"] is not None  # record_stage keeps the job


def test_job_states(tmp_path):
    p = Paths(tmp_path)
    assert state.job_state(p) == "none"
    state.start_job(p, "render", os.getpid(), tmp_path / "r.log")
    assert state.job_state(p) == "running"
    state.finish_job(p, True)
    assert state.job_state(p) == "done"
    state.start_job(p, "render", 2**22 + 12345, tmp_path / "r.log")  # no such pid
    assert state.job_state(p) == "failed"
    state.finish_job(p, False)
    assert state.job_state(p) == "failed"


def test_log_tail(tmp_path):
    log = tmp_path / "r.log"
    log.write_text("\n".join(f"l{i}" for i in range(30)))
    assert state.log_tail({"log": str(log)})[-1] == "l29"
    assert len(state.log_tail({"log": str(log)})) == 10
    assert state.log_tail({"log": "/nonexistent"}) == []
