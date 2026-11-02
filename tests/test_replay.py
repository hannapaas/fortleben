"""The orchestrator runs 「晩餐」 end to end on FakeClient, from the committed fixture, with no key,
in under a minute, and reproduces the recorded run."""

import json
import time

import pytest

from house import orchestrator
from house.client import FIXTURES, FakeClient
from house.db import connect


def test_bansan_replays_end_to_end_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    recorded = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
    if recorded["run"]["options"].get("pipeline") != orchestrator.PIPELINE:
        pytest.skip("the fixture was recorded by an earlier pipeline; re-record it with keikaku fixture")
    options = {k: v for k, v in recorded["run"]["options"].items() if k != "pipeline"}
    conn = connect(tmp_path / "replay.db")
    client = FakeClient(conn, cache_dirs=[FIXTURES / "bansan" / "responses"], run_cap=0.0)
    t0 = time.monotonic()
    run_id = orchestrator.run(conn, client, "bansan", options=options)
    assert time.monotonic() - t0 < 60
    assert conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "done"
    assert client.budget.spent(run_id) == 0  # every call served from the fixture

    def count(table):
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run_id,)).fetchone()[0]

    assert count("query") == len(recorded["query"])
    assert count("note") == len(recorded["note"])
    assert count("revision") == len(recorded["revision"])
    release = json.loads(conn.execute("SELECT body FROM release WHERE run_id=?", (run_id,)).fetchone()[0])
    assert release["views"] == recorded["release"]["views"]
