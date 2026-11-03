"""Adding a work from a link to Aozora Bunko (house/acquire.py, house/lang/ja/aozora_card.py): which links
are taken, what is read off a card, the rights rule applied by code, and a whole add of 「蜘蛛の糸」 on
saved pages, with the network replaced and the one model call replayed from fixtures/aozora-add/.
The pages in tests/fixtures/aozora/ are real, saved from aozora.gr.jp on 3 Nov 2026."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house import acquire, desk, web, works
from house.client import FakeClient
from house.db import connect
from house.lang.ja import aozora_card

DESK = {"X-Requested-With": "fetch"}  # what desk.js sends; desk changes are refused without it

PAGES = Path(__file__).parent / "fixtures" / "aozora"
BASE = "https://www.aozora.gr.jp"
KUMO = f"{BASE}/cards/000879/card92.html"
SITE = {
    KUMO: "card92.html",
    f"{BASE}/cards/000879/files/92_ruby_164.zip": "92_ruby_164.zip",
    f"{BASE}/cards/000012/card223.html": "card223.html",
    f"{BASE}/cards/000879/card127.html": "card127.html",
    f"{BASE}/cards/000035/card1567.html": "card1567.html",
    f"{BASE}/cards/000012/card435.html": "card435.html",
    f"{BASE}/index_pages/person12.html": "person12.html",
}


def page(name: str) -> str:
    return aozora_card.decode((PAGES / name).read_bytes())


class Asked(list):
    site: dict


@pytest.fixture
def fetched(monkeypatch):
    """Aozora, from the saved pages: every URL asked for is kept, and anything not saved is a 404."""
    asked, site = Asked(), dict(SITE)

    def get(url):
        asked.append(url)
        if url not in site:
            raise acquire.Refused(acquire.NOT_FOUND)
        v = site[url]
        return v if isinstance(v, bytes) else (PAGES / v).read_bytes()

    monkeypatch.setattr(acquire, "get", get)
    monkeypatch.setattr(acquire, "make_client", lambda conn: FakeClient(conn))  # fixtures/*/responses, never a key
    asked.site = site
    return asked


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "k.db")


# --- which links ---------------------------------------------------------------------------------

@pytest.mark.parametrize("url, said", [
    ("https://example.com/cards/000879/card92.html", aozora_card.NOT_AOZORA),
    ("https://www.aozora.gr.jp.example.com/cards/000879/card92.html", aozora_card.NOT_AOZORA),
    ("https://someone@www.aozora.gr.jp/cards/000879/card92.html", aozora_card.NOT_AOZORA),
    ("ftp://www.aozora.gr.jp/cards/000879/card92.html", aozora_card.NOT_AOZORA),
    ("http://www.aozora.gr.jp/cards/000879/card92.html", aozora_card.PLAIN_HTTP),
    ("https://www.aozora.gr.jp/index_pages/person879.html", aozora_card.NOT_A_CARD),
    ("https://www.aozora.gr.jp/", aozora_card.NOT_A_CARD),
])
def test_links_that_arent_a_work_on_aozora_are_refused(url, said):
    with pytest.raises(aozora_card.NotAWork, match=said[:30]):
        aozora_card.card(url)


@pytest.mark.parametrize("url", [
    "https://www.aozora.gr.jp/cards/000879/card92.html",
    "https://aozora.gr.jp/cards/000879/card92.html",
    "https://www.aozora.gr.jp/cards/000879/card92.html?utm_source=x&a=1#download",
    "https://www.aozora.gr.jp/cards/000879/files/92_ruby_164.zip",
    "https://www.aozora.gr.jp/cards/000879/files/92_15182.html",
    "  https://www.aozora.gr.jp/cards/000879/card092.html  ",
])
def test_a_card_or_a_file_on_it_resolves_to_the_card(url):
    assert aozora_card.card(url) == ("000879", "92", KUMO)


# --- what a card says ----------------------------------------------------------------------------

def test_the_card_of_bansan():
    c = aozora_card.parse_card(page("card223.html"), f"{BASE}/cards/000012/card223.html")
    assert (c["title"], c["subtitle"], c["author"]) == ("晩餐", None, "素木しづ")
    assert c["first_published"] == "「文章倶楽部」大正6年2月号"  # era years only: 大正6 is 1917
    assert aozora_card.years(c["first_published"]) == [1917]
    assert c["zip_url"] == f"{BASE}/cards/000012/files/223_ruby_2389.zip"
    assert c["people"] == [{"name": "素木しづ", "role": "著者", "romaji": "Shiraki, Shizu", "died": 1918,
                            "page": f"{BASE}/index_pages/person12.html"}]


def test_the_card_of_rashomon():
    c = aozora_card.parse_card(page("card127.html"), f"{BASE}/cards/000879/card127.html")
    assert (c["title"], c["author"]) == ("羅生門", "芥川竜之介")
    assert c["first_published"] == "「帝国文学」1915（大正4）年11月号"
    assert aozora_card.years(c["first_published"]) == [1915, 1915]
    assert c["people"][0]["died"] == 1927 and c["people"][0]["page"] == f"{BASE}/index_pages/person879.html"
    assert c["zip_url"] == f"{BASE}/cards/000879/files/127_ruby_150.zip"
    assert not aozora_card.is_split(c)


def test_the_author_page_and_a_shift_jis_page():
    assert aozora_card.parse_person(page("person12.html")) == 1918
    sjis = (PAGES / "card223.html").read_text(encoding="utf-8").replace('charset="utf-8"', 'charset="Shift_JIS"') \
        .replace("charset=utf-8", "charset=Shift_JIS").encode("cp932")
    assert aozora_card.parse_card(aozora_card.decode(sjis), KUMO)["title"] == "晩餐"


@pytest.mark.parametrize("note, years", [
    ("「赤い鳥」1918（大正7）年7月", [1918, 1918]),
    ("「新小説」明治四十五年一月号", [1912]),
    ("「中央公論」大正元年十月", [1912]),
    ("「都新聞」1913（大正2）年9月12日～1932（昭和7）年3月", [1913, 1913, 1932, 1932]),
    ("「文章世界」第14巻第3号", []),
    ("不明", []),
])
def test_years_in_a_first_publication_note(note, years):
    assert aozora_card.years(note) == years


@pytest.mark.parametrize("subtitle, split", [("01 桐壺", True), ("上", True), ("後編", True), ("第二部", True),
                                             ("――室生犀星氏――", False), (None, False)])
def test_a_work_split_across_cards(subtitle, split):
    assert aozora_card.is_split({"title": "某", "subtitle": subtitle}) is split


# --- the rights rule -------------------------------------------------------------------------------

def test_an_author_who_died_after_1931_is_refused(conn, fetched):
    with pytest.raises(acquire.Refused, match="太宰治 died in 1948. keikaku only translates works by people who died in 1931"):
        acquire.add(conn, f"{BASE}/cards/000035/card1567.html")
    assert f"{BASE}/cards/000035/files/1567_ruby_4948.zip" not in fetched  # nothing is fetched past the card
    assert conn.execute("SELECT COUNT(*) FROM work").fetchone()[0] == 0
    assert conn.execute("SELECT type FROM event").fetchone()[0] == "work.refused"


def test_a_card_with_no_first_publication_is_refused(conn, fetched):
    with pytest.raises(acquire.Refused) as e:
        acquire.add(conn, f"{BASE}/cards/000012/card435.html")
    assert str(e.value) == ("keikaku couldn't tell when this was first published (or when the author died), "
                            "so it can't translate it.")


def test_a_note_naming_a_year_after_1930_is_refused():
    info = {"people": [{"name": "某", "role": "著者", "died": 1920}], "first_published": "「某」1925（大正14）年～1932（昭和7）年"}
    with pytest.raises(acquire.Refused, match="appeared in 1932 as well as 1925"):
        acquire.rights(info, "2026-11-03")
    later = {**info, "first_published": "「某」1931（昭和6）年"}
    with pytest.raises(acquire.Refused, match="first published in 1931"):
        acquire.rights(later, "2026-11-03")


def test_a_missing_death_year_is_read_from_the_author_page_or_refused(conn, fetched):
    card = (PAGES / "card223.html").read_text(encoding="utf-8").replace(
        '<tr><td class="header">没年：</td><td>1918-01-29</td></tr>', "")
    url = f"{BASE}/cards/000012/card9223.html"
    fetched.site[url] = card.encode("utf-8")
    fetched.site[f"{BASE}/cards/000012/files/223_ruby_2389.zip"] = (PAGES / "92_ruby_164.zip").read_bytes()
    work_id, _ = acquire.add(conn, url)
    assert f"{BASE}/index_pages/person12.html" in fetched
    rights = works.info(work_id, conn)["rights"]
    assert rights["author_died"] == 1918 and rights["basis"].startswith("Aozora card and author page, read on")

    fetched.site[f"{BASE}/index_pages/person12.html"] = b"<html><meta charset=utf-8><table summary=\"x\"></table></html>"
    fetched.site[f"{BASE}/cards/000012/card9224.html"] = card.encode("utf-8")
    with pytest.raises(acquire.Refused, match="couldn't tell"):
        acquire.add(conn, f"{BASE}/cards/000012/card9224.html")


def test_a_card_without_the_ruby_text_is_refused(conn, fetched):
    card = (PAGES / "card92.html").read_text(encoding="utf-8").replace("92_ruby_164.zip", "92_15182.html")
    fetched.site[f"{BASE}/cards/000879/card9092.html"] = card.encode("utf-8")
    with pytest.raises(acquire.Refused) as e:
        acquire.add(conn, f"{BASE}/cards/000879/card9092.html")
    assert str(e.value) == "keikaku needs Aozora's ruby text file for this work, and this card has none."


def test_a_zip_the_parser_cant_read_is_refused(conn, fetched):
    fetched.site[f"{BASE}/cards/000879/files/92_ruby_164.zip"] = b"not a zip"
    with pytest.raises(acquire.Refused, match="can't read the text file"):
        acquire.add(conn, KUMO)


# --- a whole add -----------------------------------------------------------------------------------

def test_a_whole_add_of_the_spiders_thread(conn, fetched):
    work_id, new = acquire.add(conn, f"{BASE}/cards/000879/files/92_ruby_164.zip", today="2026-11-03")
    assert (work_id, new) == ("aozora-000879-92", True)
    assert fetched == [KUMO, f"{BASE}/cards/000879/files/92_ruby_164.zip"]  # the card has the 没年: no author page
    w = works.info(work_id, conn)
    assert (w["title"], w["title_en"], w["author"], w["author_en"]) == ("蜘蛛の糸", "The Spider's Thread", "芥川竜之介",
                                                                      "Akutagawa Ryūnosuke")
    assert w["blurb"].startswith("Walking beside the lotus pond")
    assert w["card_url"] == KUMO and w["zip_url"] == f"{BASE}/cards/000879/files/92_ruby_164.zip"
    assert w["rights"] == {"author_died": 1927, "first_published": "「赤い鳥」1918（大正7）年7月", "first_published_year": 1918,
                           "people": [{"name": "芥川竜之介", "role": "著者", "died": 1927}],
                           "basis": "Aozora card, read on 2026-11-03",
                           "verdict": "public domain (author died 1927, published 1918)"}
    assert works.eligible(w["rights"])
    # the text is in the data folder, never in the repo; the pages aren't kept
    path = works.source_path(work_id)
    assert path.parent.parent == Path(__import__("os").environ["KEIKAKU_DATA_DIR"]) and path.exists()
    assert sorted(p.name for p in path.parent.iterdir()) == [f"{work_id}.txt"]
    parsed = works.parse(work_id, conn)
    assert parsed.title == "蜘蛛の糸" and parsed.meta["aozora_id"] == "000092" and parsed.colophon.startswith("底本：")
    row = next(x for x in desk.eligible_works(conn) if x["id"] == work_id)
    assert row["added"] and row["chars"] == 2871 and row["estimate"] > 0
    assert work_id not in {x["id"] for x in desk.eligible_works()}  # without a connection, the repo's list only
    assert conn.execute("SELECT colophon FROM work WHERE id=?", (work_id,)).fetchone()[0] == parsed.colophon

    # the same link again, in any of its forms, finds it without fetching anything
    fetched.clear()
    assert acquire.add(conn, KUMO + "?again=1") == (work_id, False)
    assert fetched == []
    # and a card already in fixtures/works.json is that work
    assert acquire.add(conn, f"{BASE}/cards/000012/card223.html") == ("bansan", False) and fetched == []


def test_the_add_keeps_the_work_when_the_model_call_fails(conn, fetched, monkeypatch):
    monkeypatch.setattr(acquire, "make_client", lambda conn: FakeClient(conn, cache_dirs=[]))
    work_id, _ = acquire.add(conn, KUMO)
    w = works.info(work_id, conn)
    assert (w["title_en"], w["author_en"], w["blurb"]) == ("蜘蛛の糸", "芥川竜之介", None)


def test_an_added_work_parses_and_runs_from_the_command_line(conn, fetched, tmp_path, capsys, monkeypatch):
    from house import cli

    monkeypatch.setattr(cli, "connect", lambda db=None: conn)
    assert cli.main(["add", KUMO]) == 0
    out = capsys.readouterr().out
    assert out.startswith("aozora-000879-92: 蜘蛛の糸 (The Spider's Thread), Akutagawa Ryūnosuke, first published 1918.")
    assert "7.2 sheets" in out
    assert cli.main(["add", "https://example.com/x"]) == 1
    assert "Not added: That isn't an Aozora Bunko link." in capsys.readouterr().out
    # the parse stage needs no model: the work's record and paragraphs go into the database
    assert cli.main(["--replay", "run", "aozora-000879-92", "--to", "parse"]) == 0
    assert conn.execute("SELECT COUNT(*) FROM segment WHERE work_id='aozora-000879-92'").fetchone()[0] == 18


# --- the desk --------------------------------------------------------------------------------------

@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    db = tmp_path / "desk.db"
    return db, TestClient(web.create_app(db, screen=False), headers=DESK)


def test_the_desk_adds_a_work_and_lists_it(site, fetched):
    db, client = site
    conn = connect(db)
    token = desk.invite(conn, "Ines Example", drops=4000)
    r = client.post(f"/desk/{token}/works", json={"url": KUMO})
    assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex"
    row = r.json()
    assert row["id"] == "aozora-000879-92" and row["title_en"] == "The Spider's Thread" and row["added"] is True
    assert row["covered"] is True and row["sheets"] == 7.2 and row["estimate"] > 0
    assert set(row) == set(desk.state(conn, token)["works"][0])  # the same shape as the desk's list
    page = client.get(f"/desk/{token}").text
    assert "Or paste a link to any work on Aozora Bunko" in page and "Added from Aozora" in page
    assert "The Spider&#39;s Thread" in page

    r = client.post(f"/desk/{token}/works", json={"url": "http://www.aozora.gr.jp/cards/000879/card92.html"})
    assert r.status_code == 400 and r.json()["error"] == aozora_card.PLAIN_HTTP
    r = client.post(f"/desk/{token}/works", json={"url": f"{BASE}/cards/000035/card1567.html"})
    assert r.status_code == 400 and "died in 1948" in r.json()["error"]
    assert client.post("/desk/nope/works", json={"url": KUMO}).status_code == 404


def test_adds_are_limited_to_ten_a_day_per_person(site, fetched):
    db, client = site
    conn = connect(db)
    a, b = desk.invite(conn, "A"), desk.invite(conn, "B")
    for _ in range(desk.ADDS_PER_DAY):  # refused links count: each one was read from Aozora
        assert client.post(f"/desk/{a}/works", json={"url": f"{BASE}/cards/000035/card1567.html"}).status_code == 400
    r = client.post(f"/desk/{a}/works", json={"url": KUMO})
    assert r.status_code == 429 and r.json()["error"] == "You've added ten works from Aozora today. Add more tomorrow."
    assert client.post(f"/desk/{b}/works", json={"url": KUMO}).status_code == 200  # someone else's day is their own
    # a work that's already here costs Aozora nothing, so it's never limited
    assert client.post(f"/desk/{a}/works", json={"url": KUMO}).json()["id"] == "aozora-000879-92"
    assert client.post(f"/desk/{a}/works", json={"url": f"{BASE}/cards/000012/card223.html"}).json()["id"] == "bansan"


def test_an_added_work_can_be_started_from_the_desk(site, fetched, monkeypatch):
    db, client = site
    conn = connect(db)
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: None)
    token = desk.invite(conn, "Ines Example", drops=4000)
    work_id = client.post(f"/desk/{token}/works", json={"url": KUMO}).json()["id"]
    r = client.post(f"/desk/{token}/runs", json={"work": work_id, "agree": True, "credit": ""})
    assert r.status_code == 200
    assert desk.run_state(conn, token, r.json()["run_id"])["title_en"] == "The Spider's Thread"


def test_desk_html_draws_the_add_field_only_where_runs_can_start(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    db = tmp_path / "closed.db"
    token = desk.invite(connect(db), "C")
    page = TestClient(web.create_app(db, screen=False), headers=DESK).get(f"/desk/{token}").text
    assert "Or paste a link" not in page



def test_the_edition_page_reads_an_added_works_card_and_colophon(conn, fetched):
    from house import edition

    work_id, _ = acquire.add(conn, KUMO)
    meta = edition._meta(conn, work_id)
    assert meta["card_url"] == KUMO and meta["colophon"].startswith("底本：")
    assert meta["title_en"] == "The Spider's Thread" and meta["author_en"] == "Akutagawa Ryūnosuke"
    assert meta["rights"]["author_died"] == 1927 and meta["rights"]["first_published"].startswith("「赤い鳥」")
    assert meta["blurb"].startswith("Walking beside")
