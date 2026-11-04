"""Where the checkpoint, the desk, accounts and the edition meet: the cases each module's own tests
couldn't see. Nothing here calls a model."""

import json

import pytest
from fastapi.testclient import TestClient

from house import accounts, budget, cli, desk, events, web
from house.db import connect
from house.stages import latest_document

KEY = "LLM|1234567890abcdefSECRETKEYwxyz"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(desk, "_live", set())
    monkeypatch.setattr(desk, "_steering", set())


@pytest.fixture
def db(tmp_path):
    return tmp_path / "seams.db"


@pytest.fixture
def conn(db):
    return connect(db)


@pytest.fixture
def held(monkeypatch):
    attempts = []
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: attempts.append(args))
    return attempts


TAKES = [{"label": "a", "line": "plain"}, {"label": "b", "line": "warm"}]


def put(conn, run_id, kind, body):
    """A document saved by a run, as the engine saves it: with an event of that run."""
    kinds = {"reading": "reading.written", "bible": "bible.written", "checkpoint": "checkpoint.waiting"}
    eid = events.emit(conn, run_id, "house", kinds[kind], {})
    v = conn.execute("SELECT COALESCE(MAX(version), 0) FROM bible WHERE work_id='bansan' AND kind=?", (kind,)).fetchone()[0]
    conn.execute("INSERT INTO bible (work_id, version, kind, body, event_id) VALUES ('bansan', ?, ?, ?, ?)",
                 (v + 1, kind, json.dumps(body), eid))
    conn.commit()


def wait_at_checkpoint(conn, run_id, english):
    put(conn, run_id, "reading", {"voice_takes": TAKES, "crux": [], "reading": ""})
    put(conn, run_id, "bible", {"style_sheet": {"register": f"register of run {run_id}", "standing_rules": []},
                                "narration": {}, "cast": [], "motifs": [], "hard_spots": []})
    put(conn, run_id, "checkpoint", {"run_id": run_id, "rounds": [],
                                     "takes": [{**t, "english": [["p1", f"{english} {t['label']}"]]} for t in TAKES]})
    conn.execute("UPDATE run SET status='waiting', stage='checkpoint' WHERE id=?", (run_id,))
    conn.commit()
    desk._live.discard(run_id)  # the attempt that reached the checkpoint has ended


def test_two_runs_of_one_work_keep_their_own_checkpoint_reading_and_bible(conn, db, held):
    a = desk.start(db, desk.invite(conn, "A"), "bansan", True, "")
    b_token = desk.invite(conn, "B")
    b = desk.start(db, b_token, "bansan", True, "")
    wait_at_checkpoint(conn, b, "B's page")
    wait_at_checkpoint(conn, a, "A's page")  # saved last, so the work's latest is A's
    cp = desk.state(conn, b_token)["checkpoints"][0]
    assert cp["voices"][0]["english"] == ["B's page a"]
    files = {f["name"]: f["text"] for f in cp["files"]}
    assert f"register of run {b}" in files["bible"] and f"register of run {a}" not in files["bible"]
    assert latest_document(conn, "bansan", "bible", b)["style_sheet"]["register"] == f"register of run {b}"
    assert latest_document(conn, "bansan", "bible")["style_sheet"]["register"] == f"register of run {a}"


def test_a_waiting_run_holds_nothing_and_the_desk_says_so(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    assert desk.state(conn, token)["runs"][0]["held"] == desk._options(conn, run_id)["reserved_drops"]
    wait_at_checkpoint(conn, run_id, "page")
    desk.settle(conn, run_id)
    run = desk.state(conn, token)["runs"][0]
    assert run["held"] == 0 and desk.allowance(conn, 1)["reserved"] == 0
    html = TestClient(web.create_app(db, screen=False)).get(f"/desk/{token}").text
    assert "still held" not in html


def test_a_key_holder_approves_without_an_allowance(conn, db, held, monkeypatch):
    token = accounts.signup(conn, "Ines", "ines@example.com", "a long password", KEY)
    run_id = desk.start(db, token, "bansan", True, "")
    wait_at_checkpoint(conn, run_id, "page")
    monkeypatch.setattr(desk, "approve_run", lambda c, rid, voice: c.execute(
        "UPDATE run SET status='queued' WHERE id=?", (rid,)))
    desk.approve(db, token, run_id, 1)
    assert held[-1] == (db, run_id, "draft")
    assert conn.execute("SELECT COUNT(*) FROM allowance").fetchone()[0] == 0


def test_a_key_holder_who_forgot_their_key_is_told_plainly(conn, db, held, monkeypatch):
    token = accounts.signup(conn, "Ines", "ines@example.com", "a long password", KEY)
    run_id = desk.start(db, token, "bansan", True, "")
    wait_at_checkpoint(conn, run_id, "page")
    accounts.forget_key(conn, 1)
    approved = []
    monkeypatch.setattr(desk, "approve_run", lambda *a: approved.append(a))
    with pytest.raises(desk.Refused, match="no key any more"):
        desk.approve(db, token, run_id, 0)
    assert not approved and conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "waiting"
    with pytest.raises(desk.Refused, match="no key any more"):
        desk.start(db, token, "bansan", True, "")
    s = desk.state(conn, token)
    assert s["keyless"] and not s["key_tail"]
    site = TestClient(web.create_app(db, screen=False))
    site.get("/login")
    site.post("/login", data={"email": "ines@example.com", "password": "a long password", "csrf": site.cookies["fl_csrf"]})
    html = site.get("/desk").text
    assert "signed up." in html and "Your Meta key?" in html and "Add a key" in html
    assert "drops of ink" not in html


def test_a_key_turned_down_on_someones_own_key_says_what_to_do():
    said = desk.failure("RunFailed: AuthenticationError: Error code: 401", own_key=True)
    assert "your key was turned down" in said and "resume" not in said
    assert "once the key works again" in desk.failure("RunFailed: AuthenticationError: Error code: 401")


def test_own_key_spend_is_left_out_of_the_house_caps_but_calls_outside_runs_are_not(conn, db, held, monkeypatch):
    token = accounts.signup(conn, "Ines", "ines@example.com", "a long password", KEY)
    own = desk.start(db, token, "bansan", True, "")
    house = desk.start(db, desk.invite(conn, "B"), "bansan", True, "")
    for run_id, usd in ((own, 2.0), (house, 0.5), (None, 0.25)):  # None: a comment screened, outside any run
        conn.execute("INSERT INTO call (run_id, prompt, model, cost_usd, prompt_hash, input_hash, response_key) "
                     "VALUES (?, 'x', 'muse-spark-1.3', ?, '', '', '')", (run_id, usd))
    conn.commit()
    b = budget.Budget(conn)
    assert b.spent() == pytest.approx(0.75) and b.spent(today=True) == pytest.approx(0.75)
    monkeypatch.setenv("KEIKAKU_CAP_DAILY", "0.5")
    with pytest.raises(budget.CapExceeded, match="daily"):
        budget.Budget(conn).check(0.01, house)
    budget.Budget(conn, own_key=True).check(0.01, own)  # their run cap only
    with pytest.raises(budget.CapExceeded, match="run"):
        budget.Budget(conn, run_cap=2.0, own_key=True).check(0.01, own)


def test_the_house_caps_work_on_a_database_with_no_own_key_runs(conn):
    conn.execute("INSERT INTO work (id, aozora_id, title, author) VALUES ('bansan', '1', 't', 'a')")
    conn.execute("INSERT INTO run (work_id, options) VALUES ('bansan', NULL)")
    conn.execute("INSERT INTO run (work_id, options) VALUES ('bansan', '{}')")
    conn.execute("INSERT INTO call (run_id, prompt, model, cost_usd, prompt_hash, input_hash, response_key) "
                 "VALUES (1, 'x', 'muse-spark-1.3', 0.3, '', '', ''), (NULL, 'x', 'muse-spark-1.3', 0.2, '', '', '')")
    conn.commit()
    assert budget.Budget(conn).spent() == pytest.approx(0.5)


def test_signup_says_why_it_is_closed_before_anyone_fills_it_in(db, monkeypatch):
    page = TestClient(web.create_app(replay=True, screen=False)).get("/signup").text
    assert "Sign-up is closed here: this copy of the site serves recorded runs only." in page
    monkeypatch.delenv("KEIKAKU_SECRET")  # sign-up holds no key, so it stays open without one
    page = TestClient(web.create_app(db, screen=False)).get("/signup").text
    assert "Sign-up is closed" not in page


def test_the_command_line_refuses_a_negative_voice(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("KEIKAKU_DATA_DIR", str(tmp_path))
    assert cli.main(["--replay", "run", "bansan", "--voice", "-1", "--to", "parse"]) == 1
    assert "numbered from 0" in capsys.readouterr().out
