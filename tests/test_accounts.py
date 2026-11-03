"""Bring your own key: encrypted storage, sign-up, the desk for a key-holder, and the client their runs use.
Nothing here calls a model: the live client is only constructed, and runs are stood in for."""

import sqlite3

import pytest
from cryptography.fernet import InvalidToken
from fastapi.testclient import TestClient

from house import accounts, budget, desk, orchestrator, web
from house.client import FakeClient, ModelClient, make_client
from house.db import connect

KEY = "LLM|1234567890abcdefSECRETKEYwxyz"
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(desk, "_live", set())
    for limit in ("_signups", "_logins", "_resets", "_account_tries"):
        monkeypatch.setattr(accounts, limit, type(accounts._signups)(accounts._signups.default_factory))


@pytest.fixture
def db(tmp_path):
    return tmp_path / "accounts.db"


@pytest.fixture
def conn(db):
    return connect(db)


@pytest.fixture
def held(monkeypatch):
    attempts = []
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: attempts.append(args))
    return attempts


def everything(conn) -> str:
    """Every row of every table, as text: the key must be in none of them."""
    out = []
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out += [repr(tuple(r)) for r in conn.execute(f"SELECT * FROM {t}")]
    return "\n".join(out)


def test_encrypt_round_trips_and_a_wrong_secret_fails():
    token = accounts.encrypt("one", KEY)
    assert KEY not in token and accounts.decrypt("one", token) == KEY
    with pytest.raises(InvalidToken):
        accounts.decrypt("two", token)


def test_signup_makes_a_person_with_a_key_and_a_login(conn):
    pid = accounts.signup(conn, "  Ines   Example ", " Ines@Example.COM ", PASSWORD, KEY)
    person = desk.editor(conn, pid)
    assert person["name"] == "Ines Example" and person["key_tail"] == "wxyz" and person["email"] == "ines@example.com"
    assert accounts.has_key(person) and accounts.key_for(conn, person["id"]) == KEY
    assert desk.allowance(conn, person["id"])["granted"] == 0
    assert KEY not in everything(conn) and PASSWORD not in everything(conn)
    assert accounts.authenticate(conn, "INES@example.com", PASSWORD) == pid
    assert accounts.authenticate(conn, "ines@example.com", PASSWORD + "x") is None
    assert accounts.authenticate(conn, "nobody@example.com", PASSWORD) is None
    state = desk.state(conn, pid)
    assert state["key_tail"] == "wxyz" and state["base"] == "/desk" and state["email"] == "ines@example.com"
    assert all(w["covered"] for w in state["works"] if w["id"] == "bansan")


def test_passwords_are_salted_scrypt_hashes():
    one, two = accounts.hash_password(PASSWORD), accounts.hash_password(PASSWORD)
    assert one != two and one.startswith("scrypt$") and PASSWORD not in one
    assert accounts.check_password(one, PASSWORD) and not accounts.check_password(one, "wrong one")
    assert not accounts.check_password(None, PASSWORD) and not accounts.check_password("junk", PASSWORD)


@pytest.mark.parametrize("name, email, password, key, said", [
    ("Ines", "ines@example.com", PASSWORD, "", "Paste your key"),
    ("Ines", "ines@example.com", PASSWORD, "has space", "spaces"),
    ("Ines", "ines@example.com", PASSWORD, "x" * 201, "longer than any"),
    ("Ines", "ines@example.com", PASSWORD, "abc", "too short to be a Meta key"),
    ("", "ines@example.com", PASSWORD, KEY, "Give a name"),
    ("see www.example.com", "ines@example.com", PASSWORD, KEY, "No links"),
    ("Ines", "", PASSWORD, KEY, "Give an email address"),
    ("Ines", "ines at example", PASSWORD, KEY, "doesn't look like an email address"),
    ("Ines", "ines@example.com", "short", KEY, "at least 8 characters"),
])
def test_signup_refuses_bad_names_emails_passwords_and_keys(conn, name, email, password, key, said):
    with pytest.raises(accounts.Refused, match=said):
        accounts.signup(conn, name, email, password, key)
    assert conn.execute("SELECT COUNT(*) FROM person").fetchone()[0] == 0


def test_one_account_per_email(conn):
    accounts.signup(conn, "Ines", "ines@example.com", PASSWORD, KEY)
    with pytest.raises(accounts.Refused) as e:
        accounts.signup(conn, "Ines again", "INES@example.com", PASSWORD, KEY)
    assert str(e.value) == "There's already an account with that email address. Sign in instead."
    invited = desk.editor(conn, desk.invite(conn, "B"))["id"]
    with pytest.raises(accounts.Refused, match="already an account"):
        accounts.set_login(conn, invited, "ines@example.com", PASSWORD)


def test_forget_key_nulls_both_columns(conn, db, held):
    pid = accounts.signup(conn, "Ines", "ines@example.com", PASSWORD, KEY)
    run_id = desk.start(db, pid, "bansan", True, "")
    accounts.forget_key(conn, pid)
    row = conn.execute("SELECT api_key, key_tail FROM person WHERE id=?", (pid,)).fetchone()
    assert tuple(row) == (None, None) and accounts.key_for(conn, pid) is None
    conn.execute("UPDATE run SET status='failed' WHERE id=?", (run_id,))
    conn.commit()
    desk._live.clear()
    with pytest.raises(desk.Refused, match="no key any more"):  # never falls back on the site's key
        desk.resume(db, pid, run_id)


def test_make_client_takes_an_editors_key_without_a_site_key(conn):
    client = make_client(conn, run_cap=1.0, api_key=KEY)  # constructed only: nothing is sent
    assert isinstance(client, ModelClient) and client.api.api_key == KEY
    assert isinstance(make_client(conn), FakeClient)
    assert isinstance(make_client(conn, replay=True, api_key=KEY), FakeClient)


def test_a_key_holders_run_spends_their_key_and_reserves_nothing(conn, db, held, monkeypatch):
    pid = accounts.signup(conn, "Ines", "ines@example.com", PASSWORD, KEY)
    run_id = desk.start(db, pid, "bansan", True, "Ines")
    opts = desk._options(conn, run_id)
    assert opts["own_key"] is True and "reserved_drops" not in opts and "allowance_id" not in opts
    assert conn.execute("SELECT cap_usd FROM run WHERE id=?", (run_id,)).fetchone()[0] == budget.Budget(conn).run_cap
    assert conn.execute("SELECT COUNT(*) FROM allowance").fetchone()[0] == 0

    seen = {}

    def fake_make_client(c, run_cap=None, api_key=None, replay=False):
        seen.update(api_key=api_key, run_cap=run_cap)
        return FakeClient(c, run_cap=run_cap)

    def fake_run(c, client, work_id, *, run_id, from_):
        c.execute("INSERT INTO call (run_id, prompt, model, input_tokens, output_tokens, cost_usd, prompt_hash, "
                  "input_hash, response_key) VALUES (?, 'x', 'muse-spark-1.3', 9000, 3000, 0.01, '', '', '')", (run_id,))
        c.execute("UPDATE run SET status='done', stage='release' WHERE id=?", (run_id,))
        c.commit()

    monkeypatch.setattr(desk, "make_client", fake_make_client)
    monkeypatch.setattr(orchestrator, "run", fake_run)
    desk.go(*held[0])
    assert seen == {"api_key": KEY, "run_cap": budget.Budget(conn).run_cap}
    run = desk.state(conn, pid)["runs"][0]
    assert run["status"] == "done" and run["spent_words"] == "Spent about 12 thousand tokens of your key, in 1 model call."
    assert conn.execute("SELECT COUNT(*) FROM allowance").fetchone()[0] == 0
    assert KEY not in everything(conn)


def test_an_invited_editors_run_still_uses_the_sites_key(conn, db, held, monkeypatch):
    token = desk.invite(conn, "Ines")
    desk.start(db, token, "bansan", True, "")
    seen = {}
    monkeypatch.setattr(desk, "make_client", lambda c, **kw: seen.update(kw) or FakeClient(c))
    monkeypatch.setattr(orchestrator, "run", lambda *a, **k: None)
    desk.go(*held[0])
    assert "api_key" not in seen


@pytest.fixture
def site(db):
    return TestClient(web.create_app(db, screen=False), headers={"X-Requested-With": "fetch"})


def csrf(client) -> str:
    """The token a form on the site carries: the fl_csrf cookie, set on the first page."""
    client.get("/signup")
    return client.cookies["fl_csrf"]


def sign_up(client, name="Ines Example", email="ines@example.com", password=PASSWORD, **kw):
    return client.post("/signup", data={"name": name, "email": email, "password": password,
                                        "csrf": csrf(client)}, **kw)


def test_signup_signs_you_in_to_your_desk(site, conn, held):
    r = site.get("/signup")
    assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex"
    assert 'type="password"' in r.text and 'type="email"' in r.text and 'name="key"' not in r.text
    r = sign_up(site, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/desk" and "fl_session" in r.cookies

    # The desk asks for the key, and explains it, once they're in.
    page = site.get("/desk")
    assert "Your Meta key?" in page.text and "Turn off automatic top-up" in page.text and "Add a key" in page.text
    assert site.post("/desk/key", data={"key": KEY, "csrf": site.cookies["fl_csrf"]}, follow_redirects=False).status_code == 303

    # The site has no key of its own, but this person brings one, so their desk is open.
    page = site.get("/desk")
    assert page.status_code == 200 and page.headers["x-robots-tag"] == "noindex" and KEY not in page.text
    assert "Runs spend your own key, ending ····wxyz." in page.text and "Forget this key" in page.text
    assert "You sign in as ines@example.com." in page.text and 'data-base="/desk"' in page.text
    assert "no model key" not in page.text and "Your desk" in page.text and "Sign out" in page.text
    r = site.post("/desk/runs", json={"work": "bansan", "agree": True, "credit": "Ines"})
    assert r.status_code == 200 and r.json()["run_id"]
    assert KEY not in everything(conn)

    r = site.post("/desk/key/forget", data={"csrf": site.cookies["fl_csrf"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/desk"
    assert conn.execute("SELECT api_key FROM person").fetchone()[0] is None
    page = site.get("/desk")
    assert "wxyz" not in page.text and "no model key" in page.text and "Add a key" in page.text
    assert "sign up" not in page.text.lower().replace("signed up", "")

    # A new key from the desk, not a new account.
    r = site.post("/desk/key", data={"key": "two words", "csrf": site.cookies["fl_csrf"]})
    assert r.status_code == 400 and "spaces" in r.text
    r = site.post("/desk/key", data={"key": KEY[:-4] + "abcd", "csrf": site.cookies["fl_csrf"]}, follow_redirects=False)
    assert r.status_code == 303
    assert "ending ····abcd" in site.get("/desk").text
    assert conn.execute("SELECT COUNT(*) FROM person").fetchone()[0] == 1
    assert site.post("/desk/nope/key/forget", data={"csrf": site.cookies["fl_csrf"]}).status_code == 404


def test_signup_refusals_and_the_limit(site, conn):
    r = sign_up(site, name="Ines", password="short")
    assert r.status_code == 400 and 'value="Ines"' in r.text and 'value="ines@example.com"' in r.text
    assert PASSWORD not in r.text
    assert sign_up(site, follow_redirects=False).status_code == 303
    r = sign_up(TestClient(site.app), name="Ines again")
    assert r.status_code == 400 and "There&#39;s already an account with that email address. Sign in instead." in r.text
    for _ in range(accounts.SIGNUPS_PER_HOUR):  # a typo sent back doesn't count against the address
        assert sign_up(TestClient(site.app), email="typo@", follow_redirects=False).status_code == 400
    for i in range(accounts.SIGNUPS_PER_HOUR - 2):  # the sign-up and the taken address did
        assert sign_up(TestClient(site.app), email=f"ines{i}@example.com", follow_redirects=False).status_code == 303
    r = sign_up(site, email="last@example.com")
    assert r.status_code == 429 and "Try again later" in r.text


def test_signup_needs_the_forms_token(site, conn):
    r = site.post("/signup", data={"name": "Ines", "email": "ines@example.com", "password": PASSWORD, "key": KEY})
    assert r.status_code == 403 and "out of date" in r.text
    r = site.post("/signup", data={"name": "Ines", "email": "ines@example.com", "password": PASSWORD, "key": KEY,
                                   "csrf": "forged-forged-forged"})
    assert r.status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM person").fetchone()[0] == 0


def test_signup_is_closed_in_replay(monkeypatch):
    site = TestClient(web.create_app(replay=True, screen=False))
    r = site.post("/signup", data={"name": "Ines", "email": "ines@example.com", "password": PASSWORD, "key": KEY})
    assert r.status_code == 403 and "recorded runs only" in r.text


def test_the_home_page_links_to_signup(site):
    assert 'href="/signup"' in site.get("/").text


def test_old_databases_gain_the_key_columns(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE person (id INTEGER PRIMARY KEY, name TEXT NOT NULL, trust TEXT NOT NULL DEFAULT 'reader', credit_as TEXT)")
    old.commit()
    old.close()
    cols = {r[1] for r in connect(path).execute("PRAGMA table_info(person)")}
    assert {"api_key", "key_tail", "email", "password_hash", "created_at"} <= cols
    connect(path)  # and again, with nothing to add
