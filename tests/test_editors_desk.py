"""The editors' desk: invite links stored hashed, refusals before anything is reserved, the whole
estimate reserved then settled, a whole run of 「晩餐」 credited to its editor, and the routes.
Every run here is on FakeClient from fixtures/; nothing needs a key."""

import json
import math

import jinja2
import pytest
from fastapi.testclient import TestClient

from house import budget, desk, orchestrator, web
from house.client import FIXTURES, FakeClient
from house.comments import digest
from house.db import connect

RECORDED = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
MODELS = {k: v for k, v in RECORDED["run"]["options"].items() if k.endswith("_model")}


@pytest.fixture(autouse=True)
def keyless(monkeypatch):
    """No live client, ever: the desk's client serves the recorded 「晩餐」 responses only."""
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.setattr(desk, "make_client", lambda conn, run_cap=None: FakeClient(
        conn, cache_dirs=[FIXTURES / "bansan" / "responses"], run_cap=run_cap))
    monkeypatch.setattr(desk, "DEFAULT_OPTIONS", MODELS)
    monkeypatch.setattr(desk, "_live", set())


@pytest.fixture
def db(tmp_path):
    return tmp_path / "desk.db"


@pytest.fixture
def conn(db):
    return connect(db)


@pytest.fixture
def held(monkeypatch):
    """Start runs without running them: the attempts are kept to run by hand."""
    attempts = []
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: attempts.append(args))
    return attempts


@pytest.fixture
def in_place(monkeypatch):
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: fn(*args))


def spend(conn, run_id, usd):
    conn.execute("INSERT INTO call (run_id, prompt, model, cost_usd, prompt_hash, input_hash, response_key) "
                 "VALUES (?, 'x', 'muse-spark-1.3', ?, '', '', '')", (run_id, usd))
    conn.commit()


def estimate(work_id="bansan"):
    return next(w for w in desk.eligible_works() if w["id"] == work_id)["estimate"]


def test_the_token_is_stored_only_as_a_salted_hash(conn):
    token = desk.invite(conn, "Ines Example", drops=4000, work="bansan")
    row = dict(conn.execute("SELECT * FROM invite").fetchone())
    assert token not in json.dumps(row)
    assert row["token_hash"] == digest(token) and row["suggested_work"] == "bansan"
    assert desk.editor(conn, token)["name"] == "Ines Example"
    assert conn.execute("SELECT last_used_at FROM invite").fetchone()[0] is not None


def test_unknown_and_revoked_tokens_are_refused(conn, db):
    assert desk.editor(conn, "not-a-token") is None
    a, b = desk.invite(conn, "A"), desk.invite(conn, "B")
    assert desk.revoke(conn, a)
    assert desk.editor(conn, a) is None and desk.state(conn, a) is None
    b_id = conn.execute("SELECT id FROM invite WHERE token_hash=?", (digest(b),)).fetchone()[0]
    assert desk.revoke(conn, b_id) and desk.editor(conn, b) is None
    assert not desk.revoke(conn, "999")
    with pytest.raises(desk.Refused) as e:
        desk.start(db, a, "bansan", True, "")
    assert e.value.code == 404


def test_the_estimate_comes_from_the_sheets(conn):
    w = next(w for w in desk.eligible_works() if w["id"] == "bansan")
    assert w["estimate"] == math.ceil(budget.sheets(w["chars"]) * desk.FALLBACK_DROPS_PER_SHEET)
    assert w["chars"] > 0 and w["first_published_year"] == 1917


def test_the_rate_follows_finished_runs_in_the_ledger(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    conn.execute("UPDATE run SET status='done' WHERE id=?", (run_id,))
    conn.execute("INSERT INTO call (run_id, prompt, model, list_cost_usd, prompt_hash, input_hash, response_key) "
                 "VALUES (?, 'x', 'm', 1.2, 'p', 'i', 'k')", (run_id,))  # 2,000 drops for 8.5 sheets
    conn.commit()
    rate = desk.drops_per_sheet(conn)
    assert rate == pytest.approx(budget.drops(1.2) / budget.sheets(desk.eligible_works()[0]["chars"]) * 1.1, rel=0.2)
    assert rate > desk.FALLBACK_DROPS_PER_SHEET


def test_a_run_stopped_at_its_cap_resumes_with_a_top_up(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    reserved = desk._options(conn, run_id)["reserved_drops"]
    o = desk._options(conn, run_id)
    o.update(charged_drops=reserved, held_drops=0)
    conn.execute("UPDATE allowance SET drops_reserved=0, drops_spent=?", (reserved,))
    conn.execute("UPDATE run SET status='failed', stage='copy-desk', options=? WHERE id=?", (json.dumps(o), run_id))
    conn.commit()
    desk._live.clear()  # that attempt has ended
    desk.resume(db, token, run_id)
    o = desk._options(conn, run_id)
    assert o["reserved_drops"] == reserved + math.ceil(reserved / 4) and o["held_drops"] == math.ceil(reserved / 4)
    assert conn.execute("SELECT cap_usd FROM run WHERE id=?", (run_id,)).fetchone()[0] > 0


def test_refusals_reserve_nothing(conn, db, held):
    token = desk.invite(conn, "Ines")
    cases = [(dict(work_id="bansan", agree=False), "Agree to publication"),
             (dict(work_id="nosuch", agree=True), "isn't one a run can start on")]
    for kwargs, said in cases:
        with pytest.raises(desk.Refused, match=said):
            desk.start(db, token, credit="", **kwargs)
    poor = desk.invite(conn, "Poor", drops=10)
    with pytest.raises(desk.Refused, match=f"needs {estimate():,} drops and you have 10 left"):
        desk.start(db, poor, "bansan", True, "")
    conn.execute("INSERT INTO work (id, title, author) VALUES ('sumiyaki', '炭燒のむすめ', '長塚節')")
    conn.execute("INSERT INTO run (work_id, label, status) VALUES ('sumiyaki', 'cli', 'running')")
    conn.commit()
    with pytest.raises(desk.Refused, match="Another run is going") as e:
        desk.start(db, token, "bansan", True, "")
    assert e.value.code == 409
    assert held == [] and conn.execute("SELECT SUM(drops_reserved) FROM allowance").fetchone()[0] == 0


def test_the_estimate_is_reserved_then_settled(conn, db, held, monkeypatch):
    token = desk.invite(conn, "Ines", drops=4000)
    run_id = desk.start(db, token, "bansan", True, "Ines")
    est = estimate()
    s = desk.state(conn, token)
    assert s["allowance"] == {"granted": 4000, "reserved": est, "spent": 0, "available": 4000 - est}
    assert s["busy"] and s["runs"][0]["status"] == "queued" and s["runs"][0]["reserved"] == est
    opts = json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])
    assert opts["editor_id"] and opts["credit"] == "Ines" and opts["reserved_drops"] == est
    assert conn.execute("SELECT label, cap_usd FROM run WHERE id=?", (run_id,)).fetchone()[1] == pytest.approx(
        est * budget.DROP_USD * 1.2)

    usd = 123.4 * budget.DROP_USD  # the run spends a little over 123 drops

    def fake_run(c, client, work_id, *, run_id, from_):
        assert client.budget.run_cap == pytest.approx(est * budget.DROP_USD * 1.2)
        spend(c, run_id, usd)
        c.execute("UPDATE run SET status='done', stage='release' WHERE id=?", (run_id,))
        c.commit()
        return run_id

    monkeypatch.setattr(orchestrator, "run", fake_run)
    desk.go(*held[0])
    s = desk.state(conn, token)
    assert s["allowance"] == {"granted": 4000, "reserved": 0, "spent": 124, "available": 4000 - 124}
    assert s["runs"][0]["spent"] == 124 and s["runs"][0]["status"] == "done" and not s["busy"]


def test_an_overrun_is_the_houses_and_a_failure_is_recorded(conn, db, held, monkeypatch):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    est = estimate()

    def overrun(c, client, work_id, *, run_id, from_):
        spend(c, run_id, est * 1.1 * budget.DROP_USD)
        c.commit()
        raise budget.CapExceeded("run cap")

    monkeypatch.setattr(orchestrator, "run", overrun)
    desk.go(*held[0])
    run = desk.state(conn, token)["runs"][0]
    assert run["status"] == "failed" and run["spent"] == est
    assert desk.allowance(conn, 1) == {"granted": 4000, "reserved": 0, "spent": est, "available": 4000 - est}
    assert "CapExceeded" in json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])["error"]


def test_a_whole_desk_run_of_bansan_is_published_under_the_editors_name(conn, db, in_place, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    token = desk.invite(conn, "Ines Example", work="bansan")
    run_id = desk.start(db, token, "bansan", True, "Ines Example")
    run = desk.state(conn, token)["runs"][0]
    assert run["id"] == run_id and run["status"] == "done", run
    assert run["stage"] == "release" and run["stage_label"] == "published" and run["edition_url"] == "/read/bansan"
    ed = conn.execute("SELECT e.editor FROM edition e JOIN release r ON r.id = e.current_release WHERE r.run_id=?",
                      (run_id,)).fetchone()
    assert ed["editor"] == "Ines Example"
    body = json.loads(conn.execute("SELECT body FROM release WHERE run_id=?", (run_id,)).fetchone()[0])
    assert body["views"] == RECORDED["release"]["views"]
    assert desk.allowance(conn, 1) == {"granted": 4000, "reserved": 0, "spent": 0, "available": 4000}  # all cached

    other = desk.invite(conn, "Someone")
    second = desk.start(db, other, "bansan", True, "")
    assert conn.execute("SELECT e.editor FROM edition e JOIN release r ON r.id = e.current_release WHERE r.run_id=?",
                        (second,)).fetchone()[0] == "an editor"
    assert conn.execute("SELECT COUNT(*) FROM edition WHERE work_id='bansan'").fetchone()[0] == 2


def test_startup_marks_an_orphaned_run_interrupted_and_it_resumes(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    conn.execute("UPDATE run SET status='running', stage='draft' WHERE id=?", (run_id,))
    conn.commit()
    desk._live.clear()  # the process that ran it has gone
    assert desk.recover(conn) == [run_id]
    s = desk.state(conn, token)
    assert s["runs"][0]["status"] == "interrupted" and s["runs"][0]["stage_label"] == "checking against the Japanese"
    assert s["allowance"]["reserved"] == 0 and not s["busy"]

    desk.resume(db, token, run_id)
    assert held[-1] == (db, run_id, "readers")
    assert desk.state(conn, token)["allowance"]["reserved"] == estimate()
    with pytest.raises(desk.Refused, match="still going"):
        desk.resume(db, token, run_id)


@pytest.fixture
def site(db, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    # The routes are tested against a tiny stand-in for the page; the real template has its own tests.
    stand_in = jinja2.DictLoader({"desk.html": "<p>{{ desk.editor.name }}</p><p>{{ closed or '' }}</p>"})
    monkeypatch.setattr(web.templates.env, "loader", jinja2.ChoiceLoader([stand_in, web.templates.env.loader]))
    return TestClient(web.create_app(db, screen=False))


def test_the_desk_page_and_its_routes(site, conn, held, monkeypatch):
    token = desk.invite(conn, "Ines Example")
    r = site.get(f"/desk/{token}")
    assert r.status_code == 200 and "Ines Example" in r.text and r.headers["x-robots-tag"] == "noindex"
    assert site.get("/desk/nope").status_code == 404

    r = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": False, "credit": ""})
    assert r.status_code == 400 and "Agree to publication" in r.json()["error"]
    r = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": True, "credit": "Ines"})
    run_id = r.json()["run_id"]
    assert site.get(f"/desk/{token}/runs/{run_id}").json()["status"] == "queued"
    assert site.get(f"/desk/{desk.invite(conn, 'B')}/runs/{run_id}").status_code == 404
    r = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": True, "credit": ""})
    assert r.status_code == 409

    conn.execute("UPDATE run SET status='interrupted' WHERE id=?", (run_id,))
    conn.commit()
    desk._live.clear()
    assert site.post(f"/desk/{token}/runs/{run_id}/resume").json() == {"ok": True}


def test_runs_cant_start_without_a_key_or_in_replay(db, conn, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    stand_in = jinja2.DictLoader({"desk.html": "<p>{{ closed }}</p>"})
    monkeypatch.setattr(web.templates.env, "loader", jinja2.ChoiceLoader([stand_in, web.templates.env.loader]))
    token = desk.invite(conn, "Ines")
    site = TestClient(web.create_app(db, screen=False))
    assert "start here: this copy of the site has no model key" in site.get(f"/desk/{token}").text
    r = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": True, "credit": ""})
    assert r.status_code == 403 and "no model key" in r.json()["error"]

    replay = TestClient(web.create_app(replay=True))
    r = replay.get(f"/desk/{token}")
    assert "start here" in r.text and r.headers["x-robots-tag"] == "noindex"


def test_keikaku_invite_prints_a_working_link_and_never_the_hash(db, capsys, monkeypatch):
    from house import cli

    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)  # keep the real .env out of the tests
    assert cli.main(["--db", str(db), "invite", "Ines Example", "--drops", "2000", "--base-url", "https://x.test/"]) == 0
    link = capsys.readouterr().out.strip()
    assert link.startswith("https://x.test/desk/")
    token = link.rsplit("/", 1)[1]
    conn = connect(db)
    assert desk.state(conn, token)["allowance"]["granted"] == 2000
    assert cli.main(["--db", str(db), "invite", "--list"]) == 0
    listed = capsys.readouterr().out
    assert "Ines Example" in listed and "2,000 drops left" in listed and digest(token) not in listed
    assert cli.main(["--db", str(db), "invite", "--revoke", token]) == 0
    assert desk.editor(conn, token) is None


def test_startup_leaves_a_command_line_run_alone(conn):
    conn.execute("INSERT INTO work (id, title, author) VALUES ('bansan', '晩餐', '素木しづ')")
    run_id = orchestrator.new_run(conn, "bansan", "dev-1", 1.0, {})
    conn.execute("UPDATE run SET status='running' WHERE id=?", (run_id,))
    conn.commit()
    assert desk.recover(conn) == []
    assert conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "running"
