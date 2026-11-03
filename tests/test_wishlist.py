"""The public wishlist (house/wishlist.py, /wishlist): anonymous Aozora links through the desk's add,
counted per person, limited per address and per day; on the saved pages of tests/fixtures/aozora/ with
the one model call replayed from fixtures/aozora-add/."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house import acquire, edition, web, wishlist
from house.client import FakeClient
from house.db import connect

PAGES = Path(__file__).parent / "fixtures" / "aozora"
BASE = "https://www.aozora.gr.jp"
KUMO = f"{BASE}/cards/000879/card92.html"
DAZAI = f"{BASE}/cards/000035/card1567.html"  # died 1948: refused
SITE = {KUMO: "card92.html", f"{BASE}/cards/000879/files/92_ruby_164.zip": "92_ruby_164.zip",
        DAZAI: "card1567.html"}


@pytest.fixture
def fetched(monkeypatch):
    asked = []

    def get(url):
        asked.append(url)
        if url not in SITE:
            raise acquire.Refused(acquire.NOT_FOUND)
        return (PAGES / SITE[url]).read_bytes()

    monkeypatch.setattr(acquire, "get", get)
    monkeypatch.setattr(acquire, "make_client", lambda conn: FakeClient(conn))
    return asked


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.setenv("KEIKAKU_TRUST_PROXY", "true")  # the tests stand in for Railway's proxy
    db = tmp_path / "wish.db"
    return db, TestClient(web.create_app(db, screen=False))


def ask(client, url, ip="1.2.3.4"):
    return client.post("/wishlist", data={"url": url}, headers={"x-forwarded-for": ip})


def test_the_page_renders_with_the_form_and_is_linked(site):
    _, client = site
    page = client.get("/wishlist").text
    assert "Works on Aozora Bunko that people would like to read in English." in page
    assert 'action="/wishlist#ask"' in page and "Nobody has asked for anything." in page
    assert 'name="name"' not in page and 'name="email"' not in page
    home = client.get("/").text
    assert 'href="/wishlist">Wishlist</a>' in home and "What should keikaku translate next?" in home


def test_a_link_adds_the_work_and_a_wish_then_counts_up(site, fetched):
    db, client = site
    r = ask(client, KUMO)
    assert r.status_code == 200 and "Added to the list." in r.text
    conn = connect(db)
    assert conn.execute("SELECT status FROM work WHERE id='aozora-000879-92'").fetchone()[0] == "parsed"
    assert conn.execute("SELECT count FROM wish WHERE work_id='aozora-000879-92'").fetchone()[0] == 1
    page = client.get("/wishlist").text
    assert "蜘蛛の糸" in page and "The Spider&#39;s Thread" in page and "Akutagawa Ryūnosuke, 1918" in page
    assert "7.2 sheets" in page and f'href="{KUMO}"' in page and "Walking beside the lotus pond" in page

    fetched.clear()
    r = ask(client, KUMO + "?again", ip="5.6.7.8")  # someone else: one more, and nothing fetched
    assert "Already on the list: that&#39;s 2 people now." in r.text and fetched == []
    r = ask(client, KUMO, ip="5.6.7.8")  # the same person again doesn't count twice
    assert "You&#39;ve asked for this one already." in r.text
    assert conn.execute("SELECT count FROM wish").fetchone()[0] == 2


def test_a_refused_link_says_why_and_counts_against_the_days_reads(site, fetched):
    db, client = site
    r = ask(client, DAZAI)
    assert r.status_code == 400 and "died in 1948" in r.text
    r = ask(client, "https://example.com/x")
    assert r.status_code == 400 and "That isn&#39;t an Aozora Bunko link." in r.text
    conn = connect(db)
    assert wishlist.reads_today(conn) == 1  # the Aozora read counts; a link that isn't Aozora's costs nothing
    assert conn.execute("SELECT COUNT(*) FROM wish").fetchone()[0] == 0
    for i in range(wishlist.READS_PER_DAY - 1):
        ask(client, DAZAI, ip=f"10.0.0.{i}")
    r = ask(client, KUMO, ip="10.0.1.1")
    assert r.status_code == 429 and "ten new links from Aozora today" in r.text
    assert conn.execute("SELECT COUNT(*) FROM work WHERE id LIKE 'aozora-%'").fetchone()[0] == 0


def test_five_links_an_hour_from_one_address(site, fetched):
    _, client = site
    for _ in range(wishlist.ASKS_PER_HOUR):
        assert ask(client, "https://example.com/x").status_code == 400
    r = ask(client, KUMO)
    assert r.status_code == 429 and "a lot of links from one place" in r.text
    assert ask(client, KUMO, ip="9.9.9.9").status_code == 200


def test_a_wished_work_with_an_edition_shows_translated(site, fetched):
    db, client = site
    ask(client, KUMO)
    conn = connect(db)
    ed = conn.execute("INSERT INTO edition (work_id) VALUES ('aozora-000879-92')").lastrowid
    rel = conn.execute("INSERT INTO release (edition_id, version, body) VALUES (?, 'v1', '{}')", (ed,)).lastrowid
    conn.execute("UPDATE edition SET current_release=? WHERE id=?", (rel, ed))
    conn.commit()
    lists = wishlist.entries(conn)
    assert lists["wanted"] == [] and lists["translated"][0]["edition_url"] == "/read/aozora-000879-92"
    page = client.get("/wishlist").text
    assert page.index("Translated</h2>") < page.index("蜘蛛の糸") and 'href="/read/aozora-000879-92"' in page
    r = ask(client, KUMO, ip="4.4.4.4")
    assert "keikaku has translated this one already." in r.text
    assert conn.execute("SELECT count FROM wish").fetchone()[0] == 1


def test_the_form_is_off_under_replay_and_without_a_key(tmp_path, monkeypatch):
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    for app in (web.create_app(tmp_path / "nokey.db", screen=False), web.create_app(replay=True, screen=False)):
        client = TestClient(app)
        page = client.get("/wishlist").text
        assert "Works on Aozora Bunko that people would like" in page
        assert "Adding to the list is off on this copy of the site." in page and 'name="url"' not in page
        assert ask(client, KUMO).status_code == 403


def test_the_command_line_puts_a_work_on_and_takes_it_off(tmp_path, fetched, monkeypatch, capsys):
    from house import cli

    conn = connect(tmp_path / "cli.db")
    monkeypatch.setattr(cli, "connect", lambda db=None: conn)
    assert cli.main(["wish", KUMO, "--summary", "A thread from heaven, and a thief who climbs it."]) == 0
    assert "asked for by 1 person" in capsys.readouterr().out
    assert cli.main(["wish", KUMO, "--count", "4"]) == 0
    assert wishlist.entries(conn)["wanted"][0]["count"] == 4
    assert wishlist.entries(conn)["wanted"][0]["blurb"] == "A thread from heaven, and a thief who climbs it."
    assert cli.main(["wish"]) == 0 and "aozora-000879-92" in capsys.readouterr().out
    assert cli.main(["wish", KUMO, "--count", "0"]) == 0
    assert wishlist.entries(conn) == {"wanted": [], "translated": []}
    assert not edition.shelf(conn)


def test_the_address_is_the_proxys_right_most_value_and_only_behind_a_trusted_proxy(site, fetched, monkeypatch):
    _, client = site
    # A client that makes up a fresh left-hand value each time is still one address: the proxy's own, on the right.
    for i in range(wishlist.ASKS_PER_HOUR):
        assert ask(client, "https://example.com/x", ip=f"10.0.0.{i}, 7.7.7.7").status_code == 400
    assert ask(client, KUMO, ip="10.0.9.9, 7.7.7.7").status_code == 429
    assert ask(client, KUMO, ip="10.0.9.9, 8.8.8.8").status_code == 200
    # Reached directly, the header is ignored: every request is the connection's own address.
    monkeypatch.setenv("KEIKAKU_TRUST_PROXY", "false")
    for i in range(wishlist.ASKS_PER_HOUR):
        assert ask(client, "https://example.com/x", ip=f"11.0.0.{i}").status_code == 400
    assert ask(client, KUMO, ip="12.0.0.1").status_code == 429
