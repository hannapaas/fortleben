"""Comments in the margin: free checks first, then a background screen; only the writer sees a comment
until it passes; a report emails the editor."""

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


def test_a_failed_comment_tells_its_writer_why(site, db, monkeypatch):
    cid = post(site, body="Buy cheap watches").json()["id"]
    fake_screen(monkeypatch, "fail", "Advertising.")
    comments.screen(db, cid)
    assert site.get(f"/comments/{cid}").json() == {"status": "failed", "reason": "Advertising."}
    assert "Not posted: Advertising." in site.get("/read/bansan").text


def test_free_checks_refuse_before_any_model_call(site):
    assert post(site, body="").status_code == 429
    assert post(site, body="x" * (comments.MAX_BODY + 1)).status_code == 429
    assert post(site, body="see https://a.example and https://b.example").status_code == 429
    assert post(site, name="www.spam.example").status_code == 429


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


def test_a_report_emails_the_editor_once_per_address(site, db, monkeypatch):
    cid = post(site).json()["id"]
    fake_screen(monkeypatch, "pass")
    comments.screen(db, cid)
    sent = []
    monkeypatch.setattr(comments, "email", lambda subject, text: sent.append(subject))
    other = TestClient(site.app)
    assert other.post(f"/comments/{cid}/report").json() == {"ok": True}
    assert other.post(f"/comments/{cid}/report").json() == {"ok": True}
    assert len(sent) == 1 and f"comment {cid} reported" in sent[0]
    assert other.post("/comments/99999/report").status_code == 404


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
