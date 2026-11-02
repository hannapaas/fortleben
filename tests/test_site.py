"""The site serves the recorded 「晩餐」 run from fixtures/ with no key: the shelf, the reader, and
each paragraph's margin built from the record."""

import json

import pytest
from fastapi.testclient import TestClient

from house import edition
from house.client import FIXTURES
from house.db import connect
from house.web import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(replay=True))


@pytest.fixture(scope="module")
def recorded():
    return json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))


def test_shelf_lists_the_recorded_work(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "/read/bansan" in r.text and "Supper" in r.text


def test_reader_shows_every_paragraph_once(client, recorded):
    r = client.get("/read/bansan")
    assert r.status_code == 200
    casual = recorded["release"]["views"]["casual"]
    leads = [p["id"] for p in casual if not p["grouped_with"]]
    assert r.text.count('class="unit ') == len(leads)
    for pid in leads:
        assert f'id="{pid}"' in r.text


def test_margin_accounts_for_every_reader_note(tmp_path, recorded):
    conn = connect(tmp_path / "site.db")
    edition.load_fixtures(conn)
    ed = edition.edition(conn, "bansan")
    shown = [q for u in ed["units"] for q in u["queries"]]
    assert len(shown) == len(recorded["query"])
    assert all(q["outcome"] for q in shown)
    assert all(q["desk"] for q in shown if q["status"] in ("taken", "declined"))


def test_aozora_editorial_notes_are_not_shown(client):
    assert "［＃" not in client.get("/read/bansan").text
    page = client.get("/read/shuchu").text
    assert "［＃" not in page and '<em class="bouten">つぶつぶ</em>' in page


def test_a_bare_section_number_is_a_heading(client):
    assert '<h2 class="secnum" id="p1">' in client.get("/read/shuchu").text


def test_loading_fixtures_twice_adds_nothing(tmp_path):
    conn = connect(tmp_path / "site.db")
    assert sorted(edition.load_fixtures(conn)) == ["bansan", "shuchu"]
    assert edition.load_fixtures(conn) == []


def test_unknown_work_is_a_404(client):
    assert client.get("/read/nope").status_code == 404


def test_a_work_opens_keikakus_edition_and_links_a_commissioned_one(tmp_path):
    conn = connect(tmp_path / "site.db")
    edition.load_fixtures(conn)
    rel = conn.execute("SELECT run_id, body, created_at FROM release WHERE body LIKE '%\"work\": \"bansan\"%'").fetchone()
    ed = conn.execute("INSERT INTO edition (work_id, editor) VALUES ('bansan', 'Ines Moreau')").lastrowid
    r = conn.execute("INSERT INTO release (edition_id, run_id, version, body, created_at) VALUES (?,?,?,?,?)",
                     (ed, rel["run_id"], "v0.1", rel["body"], rel["created_at"])).lastrowid
    conn.execute("UPDATE edition SET current_release=? WHERE id=?", (r, ed))
    conn.commit()
    site = TestClient(create_app(tmp_path / "site.db"))
    page = site.get("/read/bansan").text
    assert "English by keikaku." in page and f'href="/read/bansan?edition={ed}"' in page
    assert "English by keikaku, commissioned by Ines Moreau." in site.get(f"/read/bansan?edition={ed}").text
    assert site.get("/").text.count('class="ttl"') == 2  # one row per work, not per edition


def test_a_translation_marked_not_shown_is_never_named(client):
    assert "Skeels" not in client.get("/").text + client.get("/read/bansan").text


def test_a_freely_published_translation_is_credited_and_linked(client):
    page = client.get("/read/shuchu").text
    assert "Glenn W. Shaw, 1930" in page and 'href="https://www.gutenberg.org/ebooks/78105"' in page
