"""Comments in the margin: free checks first, then a background screen; only the writer sees a comment
until it passes; reports hide a comment; the editor gets one email a day with signed links to hide or restore."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from house import comments, edition
from house.db import connect
from house.web import create_app


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "site.db"
    edition.load_fixtures(connect(path))
    return path


@pytest.fixture
def site(db, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    return TestClient(create_app(db, screen=False))


def fake_screen(monkeypatch, verdict, reason=""):
    client = SimpleNamespace(call=lambda call: SimpleNamespace(data={"verdict": verdict, "reason": reason}))
    monkeypatch.setattr(comments, "make_client", lambda conn: client)


def post(site, body="This is the turn of the story.", name="Ines", segment="p11"):
    site.get("/read/bansan")  # sets the writer's cookie
    return site.post("/read/bansan/comments", json={"segment": segment, "body": body, "name": name})


def test_a_new_comment_is_seen_only_by_its_writer_until_it_passes(site, db, monkeypatch):
    r = post(site)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    cid = r.json()["id"]
    assert "This is the turn of the story." in site.get("/read/bansan").text
    stranger = TestClient(site.app)
    assert "This is the turn of the story." not in stranger.get("/read/bansan").text

    fake_screen(monkeypatch, "pass")
    comments.screen(db, cid)
    assert site.get(f"/comments/{cid}").json()["status"] == "published"
    assert "This is the turn of the story." in stranger.get("/read/bansan").text


def test_a_comment_whose_screen_didnt_run_is_screened_again_later(site, db, monkeypatch):
    cid = post(site).json()["id"]

    def closed(call):
        raise RuntimeError("daily cap reached")

    monkeypatch.setattr(comments, "make_client", lambda conn: SimpleNamespace(call=closed))
    comments.screen(db, cid)
    assert site.get(f"/comments/{cid}").json()["status"] == "pending"
    assert comments.screen_pending(db) == 0  # a fresh one is left to the screen its post started
    fake_screen(monkeypatch, "pass")
    assert comments.screen_pending(db, older_than="+1 minute") == 1
    assert site.get(f"/comments/{cid}").json()["status"] == "published"


def test_a_failed_comment_tells_its_writer_why(site, db, monkeypatch):
    cid = post(site, body="Buy cheap watches").json()["id"]
    fake_screen(monkeypatch, "fail", "Advertising.")
    comments.screen(db, cid)
    assert site.get(f"/comments/{cid}").json() == {"status": "failed", "reason": "Advertising."}
    assert "Not posted: Advertising." in site.get("/read/bansan").text


def test_free_checks_refuse_before_any_model_call(site):
    assert post(site, body="").status_code == 400
    assert post(site, body="x" * (comments.MAX_BODY + 1)).status_code == 400
    assert post(site, body="see https://a.example and https://b.example").status_code == 400
    assert post(site, name="www.spam.example").status_code == 400


def test_a_malformed_comment_is_refused_not_an_error(site):
    site.get("/read/bansan")
    for raw in ("nope", "[1]", '"text"', '{"segment": ["p11"], "body": "x"}'):
        r = site.post("/read/bansan/comments", content=raw, headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 404), raw
    r = site.post("/read/bansan/comments", json={"segment": "p11", "body": None})
    assert r.status_code == 400 and r.json()["error"] == "Write something first."


def test_ids_past_sqlites_range_are_not_found(site):
    big = "99999999999999999999"
    assert site.get(f"/read/bansan?edition={big}").status_code == 404
    assert site.get(f"/comments/{big}").status_code == 404
    assert site.post(f"/comments/{big}/report").status_code == 404


def test_a_moderation_link_with_a_strange_signature_is_just_invalid(site, monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "s")
    assert site.get("/moderate/hide/1?sig=%C3%A9").status_code == 404
    assert site.post("/moderate/hide/1?sig=%C3%A9").status_code == 404


def test_rate_limit_per_writer(site):
    mine, _ = comments.LIMITS["hour"]
    for _ in range(mine):
        assert post(site).status_code == 200
    r = post(site)
    assert r.status_code == 429 and "a lot of comments" in r.json()["error"]


def test_unknown_paragraph_is_refused(site):
    assert post(site, segment="p999").status_code == 404


def test_comments_are_closed_without_a_key(db, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    site = TestClient(create_app(db, screen=False))
    assert 'class="cmp"' not in site.get("/read/bansan").text
    assert site.post("/read/bansan/comments", json={"segment": "p11", "body": "hi"}).status_code == 403


def test_reports_from_two_addresses_hide_a_comment_and_email_nobody(site, db, monkeypatch):
    monkeypatch.setenv("KEIKAKU_TRUST_PROXY", "true")  # the second address comes through the proxy
    cid = post(site).json()["id"]
    fake_screen(monkeypatch, "pass")
    comments.screen(db, cid)
    sent = []
    monkeypatch.setattr(comments, "email", lambda subject, text: sent.append(subject))
    one, two = TestClient(site.app), TestClient(site.app, headers={"X-Forwarded-For": "8.8.8.8"})
    assert one.post(f"/comments/{cid}/report").json() == {"ok": True}
    assert one.post(f"/comments/{cid}/report").json() == {"ok": True}  # the same address twice counts once
    assert "This is the turn" in one.get("/read/bansan").text
    assert two.post(f"/comments/{cid}/report").json() == {"ok": True}
    assert "This is the turn" not in site.get("/read/bansan").text  # hidden, from its writer too
    row = connect(db).execute("SELECT status, reason FROM comment WHERE id=?", (cid,)).fetchone()
    assert tuple(row) == ("hidden", "reported by 2 readers") and sent == []
    assert one.post("/comments/99999/report").status_code == 404


def test_a_signed_link_asks_first_and_the_button_hides_or_restores(site, db, monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "s3cret")
    cid = post(site).json()["id"]
    fake_screen(monkeypatch, "pass")
    comments.screen(db, cid)
    sig = comments.sign("hide", cid)
    page = site.get(f"/moderate/hide/{cid}?sig={sig}")
    assert page.status_code == 200 and "Hide this comment?" in page.text and page.headers["x-robots-tag"] == "noindex"
    assert "This is the turn" in site.get("/read/bansan").text  # opening the link changed nothing
    assert site.get(f"/moderate/hide/{cid}?sig=forged").status_code == 404
    assert site.get(f"/moderate/restore/{cid}?sig={sig}").status_code == 404  # a hide signature can't restore
    assert "is hidden" in site.post(f"/moderate/hide/{cid}?sig={sig}").text
    assert "This is the turn" not in site.get("/read/bansan").text
    assert "is published" in site.post(f"/moderate/restore/{cid}?sig={comments.sign('restore', cid)}").text
    assert "This is the turn" in site.get("/read/bansan").text


def test_links_dont_work_without_a_secret(site, db, monkeypatch):
    monkeypatch.delenv("KEIKAKU_SECRET", raising=False)
    assert site.get(f"/moderate/hide/1?sig={comments.sign('hide', 1)}").status_code == 404


def test_the_daily_email_goes_once_a_day_after_the_hour_and_only_with_news(db, monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "s3cret")
    sent = []
    monkeypatch.setattr(comments, "email", lambda subject, text: sent.append((subject, text)))
    conn = connect(db)
    for body, status, reason in [("Lovely line.", "published", None), ("BUY NOW", "failed", "spam"),
                                 ("Rude.", "hidden", "reported by 2 readers")]:
        conn.execute("INSERT INTO comment (work_id, segment_id, body, status, reason, author, ip, created_at) "
                     "VALUES ('bansan','p11',?,?,?,'a','b','2026-11-02 12:00:00')", (body, status, reason))
    conn.commit()
    morning = datetime(2026, 11, 3, 7, 0, tzinfo=comments.UK)
    assert not comments.send_digest(db, morning) and sent == []  # before the hour
    assert comments.send_digest(db, morning.replace(hour=9))
    subject, text = sent[0]
    assert subject == "Fortleben comments: 1 published, 1 stopped, 1 hidden after reports"
    assert "Lovely line." in text and "/moderate/hide/" in text and "BUY NOW" in text and "(spam)" in text
    assert "/moderate/restore/" in text
    assert not comments.send_digest(db, morning.replace(hour=15))  # once a day
    assert not comments.send_digest(db, morning.replace(day=4, hour=9)) and len(sent) == 1  # nothing new, no email


def test_reports_are_rate_limited_per_address(db, monkeypatch):
    monkeypatch.setitem(comments.REPORT_LIMITS, "hour", 2)
    conn = connect(db)
    ids = []
    for i in range(3):
        conn.execute("INSERT INTO comment (work_id, segment_id, body, status, author, ip) VALUES ('bansan','p11',?, 'published','a','b')",
                     (f"c{i}",))
        ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.commit()
    assert [comments.report(conn, i, "9.9.9.9") for i in ids] == ["sent", "sent", "limited"]


def test_keikaku_comments_lists_hides_and_restores(db, capsys):
    from house import cli

    conn = connect(db)
    conn.execute("INSERT INTO comment (work_id, segment_id, body, status, author, ip) VALUES ('bansan','p11','Lovely line.','published','a','b')")
    conn.commit()
    cid = conn.execute("SELECT MAX(id) FROM comment").fetchone()[0]
    assert cli.main(["--db", str(db), "comments"]) == 0 and "Lovely line." in capsys.readouterr().out
    assert cli.main(["--db", str(db), "comments", "--hide", str(cid)]) == 0
    assert cli.main(["--db", str(db), "comments", "--status", "hidden"]) == 0 and "hidden by the editor" in capsys.readouterr().out
    assert cli.main(["--db", str(db), "comments", "--restore", str(cid)]) == 0
    assert cli.main(["--db", str(db), "comments", "--email"]) == 0 and "1 published" in capsys.readouterr().out
