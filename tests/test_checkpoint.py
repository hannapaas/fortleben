"""The checkpoint and steering (docs/STEERING.md), on 「晩餐」 from the committed fixture, with no key."""

import json

import pytest

from house import orchestrator, steer
from house.cli import main
from house.client import FIXTURES, FakeClient
from house.db import connect
from house.stages import Ctx, checkpoint

NOTE = "Keep the mother colder: her lines shorter, with nothing added to soften them."


def options(**more) -> dict:
    recorded = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
    return {**{k: v for k, v in recorded["run"]["options"].items() if k != "pipeline"}, **more}


@pytest.fixture
def waiting(tmp_path, monkeypatch):
    """A run of bansan stopped at the checkpoint."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    db = tmp_path / "k.db"
    conn = connect(db)
    client = FakeClient(conn, cache_dirs=[FIXTURES / "bansan" / "responses"], run_cap=0.0)
    run_id = orchestrator.run(conn, client, "bansan", options=options(checkpoint=True))
    return conn, client, run_id, db


def status(conn, run_id):
    return conn.execute("SELECT status, stage FROM run WHERE id=?", (run_id,)).fetchone()


def test_the_checkpoint_does_nothing_unless_asked(tmp_path):
    conn = connect(tmp_path / "k.db")
    assert checkpoint.run(Ctx(conn, None, None, 1, {})) == {"skipped": True}


def test_a_run_waits_at_the_checkpoint_and_goes_on_once_approved(waiting):
    conn, client, run_id, _ = waiting
    assert tuple(status(conn, run_id)) == ("waiting", "checkpoint")
    doc, _ = checkpoint.document(conn, run_id)
    reading = json.loads(conn.execute("SELECT body FROM bible WHERE kind='reading' ORDER BY version DESC").fetchone()[0])
    assert [t["label"] for t in doc["takes"]] == [t["label"] for t in reading["voice_takes"]]
    assert all(t["english"] and all(pid and en for pid, en in t["english"]) for t in doc["takes"])
    assert doc["rounds"] == []
    assert conn.execute("SELECT COUNT(*) FROM revision WHERE run_id=?", (run_id,)).fetchone()[0] == 0  # nothing drafted yet
    types = [r[0] for r in conn.execute("SELECT type FROM event WHERE run_id=? ORDER BY seq", (run_id,))]
    assert "checkpoint.waiting" in types and types[-1] == "run.paused"

    with pytest.raises(ValueError):
        steer.approve(conn, run_id, 7)
    steer.approve(conn, run_id, 0)
    assert status(conn, run_id)["status"] == "queued"
    with pytest.raises(steer.NotWaiting):
        steer.approve(conn, run_id, 0)
    orchestrator.run(conn, client, "bansan", run_id=run_id, from_="draft")
    assert status(conn, run_id)["status"] == "done"
    assert client.budget.spent(run_id) == 0
    first = doc["takes"][0]["english"]
    en = dict(conn.execute("SELECT json_extract(segment_ids, '$[0]'), english FROM revision WHERE run_id=? AND version=1",
                           (run_id,)).fetchall())
    assert en[first[0][0]] == first[0][1]  # the approved take is the draft's own first page


def test_a_note_amends_the_bible_and_redrafts_page_one(waiting):
    conn, client, run_id, _ = waiting

    def versions(kind):
        return conn.execute("SELECT MAX(version) FROM bible WHERE kind=?", (kind,)).fetchone()[0]

    def body(kind, v):
        return json.loads(conn.execute("SELECT body FROM bible WHERE kind=? AND version=?", (kind, v)).fetchone()[0])

    before = versions("bible")
    rnd = steer.steer(conn, client, run_id, NOTE)
    assert rnd["reply"].strip() and "editor" not in rnd["reply"].lower()
    assert rnd["english"] and rnd["voice"] == 0
    after = versions("bible")
    old, new = body("bible", before), (body("bible", after) if after > before else None)
    if new is not None:  # a new version only where the bible changed
        assert rnd["bible_version"] == after and {k: v for k, v in new.items() if k != "say"} != {k: v for k, v in old.items() if k != "say"}
        assert "editor" not in json.dumps(new["cast"]).lower()
    else:
        assert rnd["bible_version"] == before
    doc, _ = checkpoint.document(conn, run_id)
    assert doc["rounds"] == [rnd]
    assert status(conn, run_id)["status"] == "waiting"
    assert client.budget.spent(run_id) == 0
    types = [r[0] for r in conn.execute("SELECT type FROM event WHERE run_id=? ORDER BY seq", (run_id,))]
    assert types[-1] == "checkpoint.steered"


def test_the_checkpoint_command_writes_three_files(waiting, data_dir, capsys):
    conn, _, run_id, db = waiting
    assert main(["--db", str(db), "checkpoint", "bansan"]) == 0
    out, printed = data_dir / "checkpoints" / "bansan", capsys.readouterr().out
    for name in ("reading.md", "bible.md", "voices.md"):
        assert str(out / name) in printed
        assert (out / name).read_text(encoding="utf-8").strip()
    voices = (out / "voices.md").read_text(encoding="utf-8")
    assert "## Voice 0" in voices and "## Voice 2" in voices

    steer.approve(conn, run_id, 1)
    assert main(["--db", str(db), "--replay", "steer", "bansan", NOTE]) == 1
    assert "isn't waiting" in capsys.readouterr().out
    assert main(["--db", str(db), "approve", "bansan", "--voice", "0"]) == 1
    assert main(["--db", str(db), "checkpoint", "nosuchwork"]) == 1


def test_a_steered_run_finishes_from_the_recording(waiting):
    """The whole steered flow replays keyless: note, approve, then the draft under the amended bible."""
    conn, client, run_id, _ = waiting
    steer.steer(conn, client, run_id, NOTE)
    steer.approve(conn, run_id, 0)
    orchestrator.run(conn, client, "bansan", run_id=run_id, from_="draft")
    assert status(conn, run_id)["status"] == "done"
    assert client.budget.spent(run_id) == 0
