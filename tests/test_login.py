"""Signing in: email and password, sessions, invite links that sign you in, password resets, and the
CSRF guards on everything that changes something. No mail leaves: the send function is stood in for."""

import pytest
from fastapi.testclient import TestClient

from house import accounts, comments, desk, web
from house.db import connect

KEY = "LLM|1234567890abcdefSECRETKEYwxyz"
PASSWORD = "correct horse battery"
DESK = {"X-Requested-With": "fetch"}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(desk, "_live", set())
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: None)
    for limit in ("_signups", "_logins", "_resets"):
        monkeypatch.setattr(accounts, limit, type(accounts._signups)(accounts._signups.default_factory))


@pytest.fixture
def db(tmp_path):
    return tmp_path / "login.db"


@pytest.fixture
def conn(db):
    return connect(db)


@pytest.fixture
def app(db):
    return web.create_app(db, screen=False)


@pytest.fixture
def site(app):
    return TestClient(app, headers=DESK)


@pytest.fixture
def ines(conn):
    return accounts.signup(conn, "Ines", "ines@example.com", PASSWORD, KEY)


@pytest.fixture
def mail(monkeypatch):
    """Mail that would have gone: (to, subject, text)."""
    sent = []
    monkeypatch.setattr(comments, "send", lambda to, subject, text, **kw: sent.append((to, subject, text)))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("KEIKAKU_BASE_URL", "https://fortleben.test")
    return sent


def csrf(client) -> str:
    if "fl_csrf" not in client.cookies:
        client.get("/login")
    return client.cookies["fl_csrf"]


def sign_in(client, email="ines@example.com", password=PASSWORD, **kw):
    return client.post("/login", data={"email": email, "password": password, "csrf": csrf(client)}, **kw)


def everything(conn) -> str:
    out = []
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out += [repr(tuple(r)) for r in conn.execute(f"SELECT * FROM {t}")]
    return "\n".join(out)


def test_sign_in_then_the_desk_then_sign_out(site, ines, conn):
    home = site.get("/").text
    assert 'href="/login">Sign in<' in home and "Sign out" not in home
    assert site.get("/desk", follow_redirects=False).headers["location"] == "/login"

    r = sign_in(site, email=" INES@example.com ", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/desk"
    cookie = r.headers["set-cookie"]
    assert "fl_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=7776000" in cookie
    sid = site.cookies["fl_session"]
    assert sid not in everything(conn) and accounts._hash(sid) in everything(conn)

    page = site.get("/desk")
    assert page.status_code == 200 and page.headers["x-robots-tag"] == "noindex"
    assert "Your desk" in page.text and "Sign out" in page.text and 'href="/login"' not in page.text
    assert site.get("/login", follow_redirects=False).headers["location"] == "/desk"

    r = site.post("/logout", data={"csrf": site.cookies["fl_csrf"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert conn.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 0
    assert site.get("/desk", follow_redirects=False).status_code == 303
    # The old cookie is no good either.
    stale = TestClient(site.app, cookies={"fl_session": sid})
    assert stale.get("/desk", follow_redirects=False).status_code == 303


def test_a_wrong_pair_says_only_that_it_doesnt_match(site, ines):
    for email, password in [("ines@example.com", "wrong password"), ("nobody@example.com", PASSWORD)]:
        r = sign_in(site, email=email, password=password)
        assert r.status_code == 400 and "That email and password don&#39;t match." in r.text
        assert "fl_session" not in site.cookies and password not in r.text


def test_sign_in_is_limited_per_address_and_per_email(site, ines, app):
    for _ in range(accounts.LOGINS_PER_HOUR):
        assert sign_in(site, password="wrong password").status_code == 400
    r = sign_in(site)
    assert r.status_code == 429 and "Try again later" in r.text
    # Another address, the same email: still limited.
    other = TestClient(app, headers={"X-Forwarded-For": "8.8.8.8"})
    assert sign_in(other).status_code == 429


def test_logout_and_login_need_the_forms_token(site, ines, conn):
    assert site.post("/login", data={"email": "ines@example.com", "password": PASSWORD}).status_code == 403
    sign_in(site)
    assert site.post("/logout", data={"csrf": "not-the-token-at-all"}).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1


def test_an_invite_link_signs_you_in_and_the_desk_answers_at_both_addresses(site, conn):
    token = desk.invite(conn, "Kenji")
    page = site.get(f"/desk/{token}")
    assert page.status_code == 200 and f'data-base="/desk/{token}"' in page.text
    assert "Add an email and password so you can sign in without the link" in page.text
    assert "fl_session" in site.cookies and token not in everything(conn)
    assert 'data-base="/desk"' in site.get("/desk").text

    r = site.post("/desk/runs", json={"work": "bansan", "agree": True, "credit": ""})
    run_id = r.json()["run_id"]
    assert site.get(f"/desk/runs/{run_id}").json()["status"] == "queued"
    assert site.get(f"/desk/{token}/runs/{run_id}").json()["status"] == "queued"
    # Opening the link again doesn't pile up sessions.
    site.get(f"/desk/{token}")
    assert conn.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1


def test_an_invited_editor_adds_an_email_and_password(site, conn, app, ines):
    token = desk.invite(conn, "Kenji")
    site.get(f"/desk/{token}")
    r = site.post("/desk/account", data={"email": "ines@example.com", "password": PASSWORD, "csrf": csrf(site)})
    assert r.status_code == 400 and "There&#39;s already an account with that email address. Sign in instead." in r.text
    r = site.post("/desk/account", data={"email": "kenji@example.com", "password": "short", "csrf": csrf(site)})
    assert r.status_code == 400 and "at least 8 characters" in r.text and 'value="kenji@example.com"' in r.text
    r = site.post(f"/desk/{token}/account", data={"email": "Kenji@example.com", "password": "kenji's password",
                                                  "csrf": csrf(site)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/desk/{token}"
    page = site.get("/desk").text
    assert "You sign in as kenji@example.com." in page and "Add an email and password" not in page
    assert "drops of ink" in page  # still an invited editor with an allowance

    elsewhere = TestClient(app)
    assert sign_in(elsewhere, "kenji@example.com", "kenji's password", follow_redirects=False).status_code == 303
    assert "Kenji, invited as an editor." in elsewhere.get("/desk").text
    assert site.get(f"/desk/{token}").status_code == 200  # and the link still works


def test_changing_email_or_password_needs_the_current_one_and_signs_out_elsewhere(site, ines, conn, app):
    sign_in(site)
    elsewhere = TestClient(app)
    sign_in(elsewhere)
    page = site.get("/desk").text
    assert "Change your email or password" in page and 'name="current"' in page
    for current in (None, "wrong password"):
        data = {"email": "thief@example.com", "password": "the thief's password", "csrf": csrf(site)}
        if current:
            data["current"] = current
        r = site.post("/desk/account", data=data)
        assert r.status_code == 400 and "That isn&#39;t your current password." in r.text
    assert accounts.authenticate(conn, "ines@example.com", PASSWORD) == ines
    r = site.post("/desk/account", data={"email": "ines@example.com", "current": PASSWORD, "password": "a new password",
                                         "csrf": csrf(site)}, follow_redirects=False)
    assert r.status_code == 303
    assert site.get("/desk").status_code == 200  # still signed in here
    assert elsewhere.get("/desk", follow_redirects=False).status_code == 303  # and nowhere else
    assert accounts.authenticate(conn, "ines@example.com", "a new password") == ines


def test_revoking_an_invite_ends_its_sessions(site, conn):
    token = desk.invite(conn, "Kenji")
    site.get(f"/desk/{token}")
    desk.revoke(conn, token)
    assert site.get("/desk", follow_redirects=False).status_code == 303
    assert site.get(f"/desk/{token}").status_code == 404


def test_desk_changes_need_the_desk_header(app, conn, ines):
    token = desk.invite(conn, "Kenji")
    bare = TestClient(app)
    bare.get(f"/desk/{token}")
    runs = conn.execute("SELECT COUNT(*) FROM run").fetchone()[0]  # the recorded runs the site loads  # signed in, but posting like a form on another site would
    for path in ["/desk/runs", f"/desk/{token}/runs", "/desk/works", "/desk/runs/1/resume", "/desk/runs/1/steer",
                 "/desk/runs/1/approve"]:
        r = bare.post(path, json={"work": "bansan", "agree": True})
        assert r.status_code == 403 and r.json()["error"] == "That request didn't come from the desk page."
    assert conn.execute("SELECT COUNT(*) FROM run").fetchone()[0] == runs
    # The desk's own forms carry the token instead.
    assert bare.post("/desk/key/forget").status_code == 403
    assert bare.post("/desk/account", data={"email": "k@example.com", "password": PASSWORD}).status_code == 403
    # Signed out, the signed-in routes say so.
    r = TestClient(app, headers=DESK).post("/desk/runs", json={"work": "bansan", "agree": True})
    assert r.status_code == 401 and r.json()["error"] == "Sign in first."


def test_reset_by_mail_then_sign_in_with_the_new_password(site, ines, conn, mail, app):
    page = site.get("/login").text
    assert 'href="/reset">Forgotten your password?<' in page
    assert 'name="email"' in site.get("/reset").text
    signed_in = TestClient(app)
    sign_in(signed_in)

    said = []
    for email in ["Ines@example.com", "nobody@example.com"]:
        r = site.post("/reset", data={"email": email, "csrf": csrf(site)})
        assert r.status_code == 200
        said.append(r.text)
    assert said[0] == said[1] and "If there's an account with that address" in said[0]
    assert len(mail) == 1 and mail[0][0] == "ines@example.com" and mail[0][1] == "Reset your Fortleben password"
    link = next(line for line in mail[0][2].splitlines() if "/reset/" in line)
    path = link[link.index("/reset/"):]
    assert path.split("/")[-1] not in everything(conn)

    assert "Choose a new password" in site.get(path).text
    r = site.post(path, data={"password": "short", "csrf": csrf(site)})
    assert r.status_code == 400 and "at least 8 characters" in r.text
    r = site.post(path, data={"password": "a new password", "csrf": csrf(site)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/desk" and "fl_session" in site.cookies
    assert site.get("/desk").status_code == 200
    assert signed_in.get("/desk", follow_redirects=False).status_code == 303  # signed out everywhere else

    # Once only, and the old password is gone.
    r = site.post(path, data={"password": "another password", "csrf": csrf(site)})
    assert r.status_code == 404 and "expired or has been used" in r.text
    assert sign_in(TestClient(app), password=PASSWORD).status_code == 400
    assert sign_in(TestClient(app), password="a new password", follow_redirects=False).status_code == 303


def test_an_expired_reset_is_refused(site, ines, conn, mail):
    site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)})
    path = mail[0][2][mail[0][2].index("/reset/"):].split()[0]
    conn.execute("UPDATE reset SET expires_at=datetime('now', '-1 minute')")
    conn.commit()
    assert site.get(path).status_code == 404
    r = site.post(path, data={"password": "a new password", "csrf": csrf(site)})
    assert r.status_code == 404 and "That reset link has expired or has been used. Ask for a new one." in r.text
    assert accounts.authenticate(conn, "ines@example.com", PASSWORD) == ines


def test_without_mail_the_reset_page_says_so_and_the_link_goes_to_the_log(site, ines, capsys):
    page = site.get("/reset").text
    assert "Password reset mail isn't set up on this server. Ask the person running it." in page
    assert 'name="email"' not in page
    r = site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)})
    assert "isn't set up on this server" in r.text and "on its way" not in r.text
    assert "/reset/" in capsys.readouterr().out


def test_without_mail_the_reset_page_gives_the_contact_address(ines, db, monkeypatch):
    monkeypatch.setenv("KEIKAKU_CONTACT", "help@example.org")
    page = TestClient(web.create_app(db, screen=False)).get("/reset").text
    assert "isn't set up on this server. Email" in page and 'href="mailto:help@example.org' in page
    assert "Ask the person running it" not in page and 'name="email"' not in page


def test_reset_asks_are_limited(site, ines, mail):
    for _ in range(accounts.RESETS_PER_HOUR):
        site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)})
    r = site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)})
    assert r.status_code == 429 and len(mail) == accounts.RESETS_PER_HOUR


def test_nothing_secret_is_rendered_or_stored(site, conn, mail):
    site.get("/signup")
    site.post("/signup", data={"name": "Ines", "email": "ines@example.com", "password": PASSWORD, "key": KEY,
                               "csrf": csrf(site)})
    sid = site.cookies["fl_session"]
    site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)})
    reset = mail[0][2][mail[0][2].index("/reset/") + 7:].split()[0]
    pages = [site.get(p).text for p in ["/", "/desk", "/signup", "/login", "/reset", f"/reset/{reset}"]]
    stored = everything(conn)
    hash_ = conn.execute("SELECT password_hash FROM person").fetchone()[0]
    for secret in [PASSWORD, KEY, sid, hash_]:
        assert not any(secret in p for p in pages)
    for secret in [PASSWORD, KEY, sid, reset]:
        assert secret not in stored


def test_reset_mail_needs_the_sites_own_address(site, ines, monkeypatch):
    sent = []
    monkeypatch.setattr(comments, "send", lambda to, subject, text, **kw: sent.append((to, text)))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.delenv("KEIKAKU_BASE_URL", raising=False)
    r = site.post("/reset", data={"email": "ines@example.com", "csrf": csrf(site)}, headers={"Host": "evil.example"})
    # No address of its own: the link goes to the log, never by mail with the asker's Host in it.
    assert sent and sent[0][0] is None and "set up on this server" in r.text


def test_a_revoked_invite_cant_reset_its_way_back(conn):
    token = desk.invite(conn, "Kenji")
    pid = desk.editor(conn, token)["id"]
    accounts.set_login(conn, pid, "kenji@example.com", PASSWORD)
    early = accounts.new_reset(conn, "kenji@example.com")
    desk.revoke(conn, token)
    assert accounts.new_reset(conn, "kenji@example.com") is None
    assert accounts.reset_person(conn, early) is None


def test_a_password_change_cancels_reset_links(conn, ines):
    link = accounts.new_reset(conn, "ines@example.com")
    accounts.set_login(conn, ines, "ines@example.com", "another password", PASSWORD)
    assert accounts.reset_person(conn, link) is None


def test_a_chunked_body_is_capped(site):
    def chunks():
        for _ in range(web.MAX_BODY // 65536 + 2):
            yield b"u" * 65536
    r = site.post("/wishlist", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413
    assert r.headers["x-frame-options"] == "DENY"


def test_a_lone_surrogate_is_refused_not_a_crash(site, ines):
    sign_in(site)
    r = site.post("/desk/runs", content=b'{"work": "bansan", "agree": true, "credit": "\\ud800"}',
                  headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_credits_the_site_uses_are_refused(site, ines):
    sign_in(site)
    for credit in ("the house", "Keikaku", {"a": 1}):
        r = site.post("/desk/runs", json={"work": "bansan", "agree": True, "credit": credit})
        assert r.status_code == 400, credit


def test_a_missing_page_is_a_page_in_a_browser(site):
    html = {"Accept": "text/html"}
    for path in ("/read/nope", "/read/bansan?edition=abc", "/nothere"):
        r = site.get(path, headers=html)
        assert r.status_code == 404 and "Back to the library" in r.text, path
    assert site.get("/read/nope").json()["detail"] == "No edition of that work yet."
