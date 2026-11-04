"""The editors' desk: invite links stored hashed, refusals before anything is reserved, the whole
estimate reserved then settled, a whole run of 「晩餐」 credited to its editor, the routes, and the
checkpoint (notes and approval, against stand-ins for house/steer.py). Every run here is on
FakeClient from fixtures/; nothing needs a key."""

import json
import math

import jinja2
import pytest
from fastapi.testclient import TestClient

from house import budget, desk, orchestrator, web
from house.client import FIXTURES, FakeClient
from house.comments import digest
from house.db import connect

DESK = {"X-Requested-With": "fetch"}  # what desk.js sends; desk changes are refused without it

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
    assert w["estimate"] == math.ceil(desk.sheets(w["chars"]) * desk.FALLBACK_DROPS_PER_SHEET)
    assert w["chars"] > 0 and w["first_published_year"] == 1917


def test_the_rate_follows_finished_runs_in_the_ledger(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    conn.execute("UPDATE run SET status='done' WHERE id=?", (run_id,))
    conn.execute("INSERT INTO call (run_id, prompt, model, list_cost_usd, prompt_hash, input_hash, response_key) "
                 "VALUES (?, 'x', 'm', 1.2, 'p', 'i', 'k')", (run_id,))  # 2,000 drops for 8.5 sheets
    conn.commit()
    rate = desk.drops_per_sheet(conn)
    assert rate == pytest.approx(desk.drops(1.2) / desk.sheets(desk.eligible_works()[0]["chars"]) * 1.1, rel=0.2)
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
    for _ in range(desk.CAPACITY):  # the house is full, here with runs from the command line
        conn.execute("INSERT INTO run (work_id, label, status) VALUES ('sumiyaki', 'cli', 'running')")
    conn.commit()
    with pytest.raises(desk.Refused, match="Fortleben is full at the moment") as e:
        desk.start(db, token, "bansan", True, "")
    assert e.value.code == 409
    assert held == [] and conn.execute("SELECT SUM(drops_reserved) FROM allowance").fetchone()[0] == 0


def test_the_estimate_is_reserved_then_settled(conn, db, held, monkeypatch):
    token = desk.invite(conn, "Ines", drops=4000)
    run_id = desk.start(db, token, "bansan", True, "Ines")
    est = estimate()
    s = desk.state(conn, token)
    assert s["allowance"] == {"granted": 4000, "reserved": est, "spent": 0, "available": 4000 - est}
    assert s["going"] and not s["busy"] and s["runs"][0]["status"] == "queued" and s["runs"][0]["reserved"] == est
    opts = json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])
    assert opts["editor_id"] and opts["credit"] == "Ines" and opts["reserved_drops"] == est
    assert conn.execute("SELECT label, cap_usd FROM run WHERE id=?", (run_id,)).fetchone()[1] == pytest.approx(
        est * desk.DROP_USD * 1.2)

    usd = 123.4 * desk.DROP_USD  # the run spends a little over 123 drops

    def fake_run(c, client, work_id, *, run_id, from_):
        assert client.budget.run_cap == pytest.approx(est * desk.DROP_USD * 1.2)
        spend(c, run_id, usd)
        c.execute("UPDATE run SET status='done', stage='release' WHERE id=?", (run_id,))
        c.commit()
        return run_id

    monkeypatch.setattr(orchestrator, "run", fake_run)
    desk.go(*held[0])
    s = desk.state(conn, token)
    assert s["allowance"] == {"granted": 4000, "reserved": 0, "spent": 124, "available": 4000 - 124}
    assert s["runs"][0]["spent"] == 124 and s["runs"][0]["status"] == "done" and not s["busy"] and not s["going"]


def test_a_start_holds_no_more_than_the_page_showed(conn, db, held):
    est = estimate()
    # The figure moved up a little since the page was drawn: the page's figure is held.
    token = desk.invite(conn, "Ines", drops=4000)
    run_id = desk.start(db, token, "bansan", True, "Ines", shown=est - est // 10)
    assert json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])["reserved_drops"] == est - est // 10
    assert desk.state(conn, token)["allowance"]["reserved"] == est - est // 10
    # It went down: the fresh, smaller one is held.
    other = desk.invite(conn, "Kenji", drops=4000)
    run_id = desk.start(db, other, "bansan", True, "Kenji", shown=est + 50)
    assert json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])["reserved_drops"] == est
    # The page is far out of date: refused, nothing held.
    third = desk.invite(conn, "Aiko", drops=4000)
    with pytest.raises(desk.Refused, match="changed since the page loaded") as e:
        desk.start(db, third, "bansan", True, "Aiko", shown=est // 2)
    assert e.value.code == 409 and desk.state(conn, third)["allowance"]["reserved"] == 0


def test_an_overrun_is_the_houses_and_a_failure_is_recorded(conn, db, held, monkeypatch):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    est = estimate()

    def overrun(c, client, work_id, *, run_id, from_):
        spend(c, run_id, est * 1.1 * desk.DROP_USD)
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
    assert run["id"] == run_id and run["status"] == "waiting", run  # at the checkpoint, with page 1 in each voice
    assert len(desk.state(conn, token)["checkpoints"][0]["voices"]) >= 2
    desk.approve(db, token, run_id, 0)  # the first voice: the recorded run's, so every call replays
    run = desk.state(conn, token)["runs"][0]
    assert run["id"] == run_id and run["status"] == "done", run
    assert run["stage"] == "release" and run["stage_label"] == "published"
    ed = conn.execute("SELECT e.id, e.editor FROM edition e JOIN release r ON r.id = e.current_release WHERE r.run_id=?",
                      (run_id,)).fetchone()
    assert ed["editor"] == "Ines Example"
    assert run["edition_url"] == f"/read/bansan?edition={ed['id']}"  # the editor's edition, not the house's
    body = json.loads(conn.execute("SELECT body FROM release WHERE run_id=?", (run_id,)).fetchone()[0])
    assert body["views"] == RECORDED["release"]["views"]
    assert desk.allowance(conn, 1) == {"granted": 4000, "reserved": 0, "spent": 0, "available": 4000}  # all cached

    other = desk.invite(conn, "Someone")
    second = desk.start(db, other, "bansan", True, "", checkpoint=False)
    assert conn.execute("SELECT e.editor FROM edition e JOIN release r ON r.id = e.current_release WHERE r.run_id=?",
                        (second,)).fetchone()[0] == "an editor"
    assert conn.execute("SELECT COUNT(*) FROM edition WHERE work_id='bansan'").fetchone()[0] == 2
    # Another editor giving the same name gets an edition of their own; Ines's stays hers.
    namesake = desk.start(db, desk.invite(conn, "Namesake"), "bansan", True, "Ines Example", checkpoint=False)
    assert conn.execute("SELECT e.id FROM edition e JOIN release r ON r.id = e.current_release WHERE r.run_id=?",
                        (namesake,)).fetchone()[0] != ed["id"]
    assert conn.execute("SELECT current_release FROM edition WHERE id=?", (ed["id"],)).fetchone()[0] == \
        conn.execute("SELECT id FROM release WHERE run_id=?", (run_id,)).fetchone()[0]


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
    return TestClient(web.create_app(db, screen=False), headers=DESK)


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
    assert r.status_code == 409 and "You have a translation going already" in r.json()["error"]

    conn.execute("UPDATE run SET status='interrupted' WHERE id=?", (run_id,))
    conn.commit()
    desk._live.clear()
    assert site.post(f"/desk/{token}/runs/{run_id}/resume").json() == {"ok": True}


def test_bad_run_ids_and_bodies_are_refused_in_the_desks_words(site, conn, held):
    token = desk.invite(conn, "Ines")
    for rid in ("abc", "0", "99999999999999999999999", "-1"):
        r = site.get(f"/desk/{token}/runs/{rid}")
        assert r.status_code == 404 and r.json()["error"] == "There's no such run on this desk.", rid
        for action in ("resume", "steer", "approve"):
            r = site.post(f"/desk/{token}/runs/{rid}/{action}", json={"note": "x", "voice": 0})
            assert r.status_code == 404 and "no such run" in r.json()["error"], (rid, action)
    r = site.post(f"/desk/{token}/runs", content="[" * 200000, headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    r = site.post(f"/desk/{token}/runs", content="x" * (web.MAX_BODY + 1))
    assert r.status_code == 413


def test_a_note_that_isnt_text_is_no_note(site, conn, held):
    token = desk.invite(conn, "Ines")
    run_id = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": True, "credit": ""}).json()["run_id"]
    conn.execute("UPDATE run SET status='waiting', stage='checkpoint' WHERE id=?", (run_id,))
    conn.commit()
    r = site.post(f"/desk/{token}/runs/{run_id}/steer", json={"note": 5, "voice": 0})
    assert r.status_code == 400 and r.json()["error"] == "Write a note first."


def test_a_run_whose_own_key_was_turned_down_offers_no_resume(conn, db, held):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    o = desk._options(conn, run_id)
    o.update(own_key=True, error="RunFailed: AuthenticationError: Error code: 401")
    conn.execute("UPDATE run SET status='failed', stage='bible', options=? WHERE id=?", (json.dumps(o), run_id))
    conn.commit()
    desk._live.clear()
    assert desk.run_state(conn, token, run_id)["resumable"] is False
    with pytest.raises(desk.Refused, match="can't go on"):
        desk.resume(db, token, run_id)


def test_runs_cant_start_without_a_key_or_in_replay(db, conn, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    stand_in = jinja2.DictLoader({"desk.html": "<p>{{ closed }}</p>"})
    monkeypatch.setattr(web.templates.env, "loader", jinja2.ChoiceLoader([stand_in, web.templates.env.loader]))
    token = desk.invite(conn, "Ines")
    site = TestClient(web.create_app(db, screen=False), headers=DESK)
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


# --- the checkpoint ------------------------------------------------------------------------------
# The engine in this checkout has no checkpoint stage, so a stand-in for the orchestrator takes a run
# to it as the contract says (docs/STEERING.md): the fixture's reading and bible, a checkpoint
# document with page 1 in each voice take, status `waiting`, stage `checkpoint`.

DOCS = {b["kind"]: b["body"] for b in RECORDED["bible"] if b["kind"] in ("reading", "bible")}
DOCS = {k: json.loads(v) if isinstance(v, str) else v for k, v in DOCS.items()}
PAGE_1 = [[r["segment_ids"][0], r["english"]] for r in RECORDED["revision"]
          if r["version"] == 1 and r["segment_ids"][0] in ("p1", "p2", "p3")]


def put_doc(conn, kind, body):
    v = conn.execute("SELECT COALESCE(MAX(version), 0) FROM bible WHERE work_id='bansan' AND kind=?", (kind,)).fetchone()[0]
    conn.execute("INSERT INTO bible (work_id, version, kind, body) VALUES ('bansan', ?, ?, ?)", (v + 1, kind, json.dumps(body)))


def doc(conn, kind):
    return json.loads(conn.execute("SELECT body FROM bible WHERE work_id='bansan' AND kind=? ORDER BY version DESC LIMIT 1",
                                   (kind,)).fetchone()[0])


def to_the_checkpoint(c, client, work_id, *, run_id, from_):
    """What the engine's checkpoint stage leaves behind."""
    assert desk._options(c, run_id)["checkpoint"] is True
    spend(c, run_id, 300 * desk.DROP_USD)
    for kind, body in DOCS.items():
        put_doc(c, kind, body)
    takes = [{"label": t["label"], "line": t["line"],
              "english": [[pid, e if i == 0 else f"[{t['label']}] {e}"] for pid, e in PAGE_1]}
             for i, t in enumerate(DOCS["reading"]["voice_takes"])]
    put_doc(c, "checkpoint", {"run_id": run_id, "takes": takes, "rounds": []})
    c.execute("UPDATE run SET status='waiting', stage='checkpoint' WHERE id=?", (run_id,))
    c.commit()
    return run_id


@pytest.fixture
def waiting(conn, db, held, monkeypatch):
    """An editor's run of 「晩餐」, waiting at the checkpoint. Returns (token, run_id)."""
    monkeypatch.setattr(orchestrator, "run", to_the_checkpoint)
    token = desk.invite(conn, "Ines Example", work="bansan")
    run_id = desk.start(db, token, "bansan", True, "")
    desk.go(*held.pop())
    assert conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "waiting"
    return token, run_id


def a_round(conn, client, run_id, note):
    """A stand-in for house.steer.steer: the house's reply, an amended bible, page 1 again."""
    assert client.budget.run_cap > 0
    bible = doc(conn, "bible")
    bible["style_sheet"]["register"] = "Plainer and older: the period's own plainness, nothing modern."
    put_doc(conn, "bible", bible)
    cp = doc(conn, "checkpoint")
    voice = desk._options(conn, run_id).get("voice", 0)
    r = {"note": note, "reply": "The register now keeps the period's plainness.", "changed": ["Style sheet: register"],
         "question": "Should the baby's babble stay as sound, or be put into words?", "reading_version": 1,
         "bible_version": 2, "voice": voice, "english": [[pid, f"Redrafted in voice {voice}: {e}"] for pid, e in PAGE_1]}
    cp["rounds"].append(r)
    put_doc(conn, "checkpoint", cp)
    spend(conn, run_id, 10 * desk.DROP_USD)
    conn.commit()
    return r


def test_desk_runs_start_with_the_checkpoint_on_unless_asked(conn, db, held, site):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    assert desk._options(conn, run_id)["checkpoint"] is True
    conn.execute("UPDATE run SET status='done' WHERE id=?", (run_id,))
    conn.commit()
    r = site.post(f"/desk/{token}/runs", json={"work": "bansan", "agree": True, "credit": "", "checkpoint": False})
    assert desk._options(conn, r.json()["run_id"])["checkpoint"] is False


def test_a_waiting_run_shows_the_checkpoint(conn, db, waiting, monkeypatch):
    token, run_id = waiting
    s = desk.state(conn, token)
    assert s["runs"][0]["status"] == "waiting" and s["runs"][0]["stage_label"] == "waiting for the editor"
    assert s["allowance"]["reserved"] == 0 and s["allowance"]["spent"] == 300  # settled while it waits
    assert not s["going"]  # a waiting run doesn't stop its editor starting another

    monkeypatch.setenv("MODEL_API_KEY", "test")
    html = TestClient(web.create_app(db, screen=False), headers=DESK).get(f"/desk/{token}").text  # the real template
    assert "Waiting for you." in html and f'href="#checkpoint-{run_id}"' in html
    assert "keikaku has read the story. These are the three files" in html
    assert DOCS["reading"]["crux"][0]["point"][:60] in html.replace("&#34;", '"').replace("&#39;", "'")
    for i, t in enumerate(DOCS["reading"]["voice_takes"]):
        assert f'name="voice-{run_id}" value="{i}"' in html and f"Voice {t['label']}" in html
    assert 'value="0" checked' in html
    assert PAGE_1[0][1][:50] in html and f"[{DOCS['reading']['voice_takes'][1]['label']}] {PAGE_1[0][1][:40]}" in html
    assert "### Style sheet" in html and "### Cast" in html and "### Hard spots" in html  # the analysis, as its file
    assert DOCS["bible"]["cast"][0]["handle"] in html
    assert "Send note" in html and "Approve and translate" in html and "$" not in html


def test_a_note_is_read_and_its_round_appears(conn, db, waiting, monkeypatch):
    token, run_id = waiting
    monkeypatch.setattr(desk, "steer_round", a_round)
    with pytest.raises(desk.Refused, match="Write a note first"):
        desk.steer(db, token, run_id, "   ")

    spawned = []
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: spawned.append((fn, args)))
    desk.steer(db, token, run_id, "This sounds too modern; I want the period to show more.", voice=1)
    assert "voice" not in desk._options(conn, run_id)  # kept only once the note is read
    assert desk.run_state(conn, token, run_id)["steering"]  # the page says "Reading your note"
    with pytest.raises(desk.Refused, match="still reading your last note"):
        desk.steer(db, token, run_id, "And another.")
    fn, args = spawned.pop()
    fn(*args)
    assert desk._options(conn, run_id)["voice"] == 1

    r = desk.run_state(conn, token, run_id)
    assert r["status"] == "waiting" and r["rounds"] == 1 and not r["steering"] and r["steer_error"] is None
    assert desk.allowance(conn, 1)["spent"] == 310  # the round's calls are charged like the rest
    cp = desk.state(conn, token)["checkpoints"][0]
    assert cp["voice"] == 1 and cp["rounds"][0]["note"].startswith("This sounds too modern")
    assert cp["voices"][1]["redrafted"] and cp["voices"][1]["english"][0].startswith("Redrafted in voice 1")
    assert not cp["voices"][0]["redrafted"]
    assert "Plainer and older" in next(f["text"] for f in cp["files"] if f["name"] == "bible")

    monkeypatch.setenv("MODEL_API_KEY", "test")
    site = TestClient(web.create_app(db, screen=False), headers=DESK)
    assert site.get(f"/desk/{token}/runs/{run_id}").json()["rounds"] == 1
    html = site.get(f"/desk/{token}").text
    assert "The register now keeps the period" in html and "Should the baby" in html and "redrafted after your note" in html

    monkeypatch.setattr(desk, "spawn", lambda fn, *args: fn(*args))

    def broken(*a):
        raise RuntimeError("the model said no")

    monkeypatch.setattr(desk, "steer_round", broken)
    assert site.post(f"/desk/{token}/runs/{run_id}/steer", json={"note": "Colder mother.", "voice": 2}).json() == {"ok": True}
    r = site.get(f"/desk/{token}/runs/{run_id}").json()
    assert r["rounds"] == 1 and r["steer_error"] and "the model said no" not in r["steer_error"]
    assert desk._options(conn, run_id)["voice"] == 1  # a note that failed leaves the voice as it was


def test_approve_queues_the_run_and_carries_on_from_the_draft(conn, db, waiting, held, monkeypatch, site):
    token, run_id = waiting
    approved = []

    def stub_approve(c, rid, voice):  # what house.steer.approve does, by the contract
        o = desk._options(c, rid)
        o["voice"] = voice
        c.execute("UPDATE run SET status='queued', options=? WHERE id=?", (json.dumps(o), rid))
        c.commit()
        approved.append((rid, voice))

    monkeypatch.setattr(desk, "approve_run", stub_approve)
    with pytest.raises(desk.Refused, match="waiting for you"):
        desk.resume(db, token, run_id)
    r = site.post(f"/desk/{token}/runs/{run_id}/approve", json={"voice": 7})
    assert r.status_code == 400 and "Pick one of the voices" in r.json()["error"]
    assert site.post(f"/desk/{token}/runs/{run_id}/approve", json={"voice": 2}).json() == {"ok": True}
    assert approved == [(run_id, 2)] and held[-1] == (db, run_id, "draft")
    row = conn.execute("SELECT status, options FROM run WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "queued" and json.loads(row["options"])["voice"] == 2
    assert desk.allowance(conn, 1)["reserved"] == estimate() - 300  # what's left of the reservation, held again

    r = site.post(f"/desk/{token}/runs/{run_id}/approve", json={"voice": 0})
    assert r.status_code == 409 and "isn't" in r.json()["error"]
    r = site.post(f"/desk/{token}/runs/{run_id}/steer", json={"note": "Too late?"})
    assert r.status_code == 409 and "before the draft starts" in r.json()["error"]

    # The site restarts before the draft begins: the run resumes from the draft, not the checkpoint.
    desk._live.clear()
    assert desk.recover(conn) == [run_id]
    desk.resume(db, token, run_id)
    assert held[-1] == (db, run_id, "draft")


def test_one_run_per_person_and_three_across_the_site(conn, db, held, monkeypatch):
    a, b = desk.invite(conn, "A"), desk.invite(conn, "B")
    first = desk.start(db, a, "bansan", True, "")
    second = desk.start(db, b, "bansan", True, "")  # another person's run doesn't stop B
    with pytest.raises(desk.Refused, match="You have a translation going already"):
        desk.start(db, a, "bansan", True, "")
    conn.execute("UPDATE run SET status='waiting', stage='checkpoint' WHERE id=?", (first,))
    conn.commit()
    third = desk.start(db, a, "bansan", True, "")  # A's run waits at the checkpoint, so A can start another
    c = desk.invite(conn, "C")
    desk.start(db, c, "bansan", True, "")
    s = desk.state(conn, desk.invite(conn, "D"))
    assert s["busy"] and not s["going"]
    with pytest.raises(desk.Refused, match="Fortleben is full at the moment: three translations are going") as e:
        desk.start(db, desk.invite(conn, "D2"), "bansan", True, "")
    assert e.value.code == 409
    assert {second, third} < {r["id"] for r in conn.execute("SELECT id FROM run WHERE status='queued'")}


@pytest.mark.parametrize("error, said", [
    ("CapExceeded: budget ran out during the draft stage of run 3. Nothing was released.",
     "It stopped when its budget ran out. Everything it finished is kept; resume it and it carries on from there."),
    ("RunFailed: run 401 failed during the draft stage: RateLimitError: Error code: 429 - insufficient_quota",
     "It stopped when the key ran out of credit."),
    ("RunFailed: run 4 failed during the draft stage: AuthenticationError: Error code: 401", "It stopped because the site's model key was turned down."),
    ("RunFailed: run 401 failed during the draft stage: SchemaError: output failed twice", "It stopped on an error."),
])
def test_a_failed_run_says_what_happened_in_plain_words(conn, db, held, error, said):
    token = desk.invite(conn, "Ines")
    run_id = desk.start(db, token, "bansan", True, "")
    o = desk._options(conn, run_id)
    o["error"] = error
    conn.execute("UPDATE run SET status='failed', stage='bible', options=? WHERE id=?", (json.dumps(o), run_id))
    conn.commit()
    run = desk.state(conn, token)["runs"][0]
    assert run["failure"].startswith(said) and "Everything it finished is kept;" in run["failure"]
    assert run["failure"].endswith("resume it and it carries on from there.")
    assert "$" not in run["failure"]


def test_an_editor_picks_the_editions_colour(conn, db, held):
    token = desk.invite(conn, "A")
    with pytest.raises(desk.Refused, match="colours shown"):
        desk.start(db, token, "bansan", True, "", accent="mauve")
    run_id = desk.start(db, token, "bansan", True, "", accent="lime")
    assert json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()[0])["accent"] == "lime"
