"""The site serves the recorded 「晩餐」 run from fixtures/ with no key: the shelf, the reader, and
each paragraph's margin built from the record."""

import json

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

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


def test_the_edition_links_to_the_analysis_on_its_own_page(client, recorded):
    page = client.get("/read/bansan").text
    assert 'href="/read/bansan/analysis' in page and "story bible" not in page and "the house" not in page
    page = client.get("/read/bansan/analysis").text
    reading, bible = (_body(next(b["body"] for b in reversed(recorded["bible"]) if b["kind"] == k)) for k in ("reading", "bible"))
    assert "How keikaku read" in page and "story bible" not in page and "the house" not in page
    assert escape(reading["crux"][0]["point"]) in page
    for c in bible["cast"]:
        assert escape(c["handle"]) in page
    assert "Recommended" not in page  # the voice it was drafted in, without the first read's marking
    assert 'start your own edition and steer it</a>' in page and 'href="/signup"' in page


def test_a_second_readers_crux_is_labelled_and_the_chosen_voice_shown(tmp_path):
    conn = connect(tmp_path / "site.db")
    edition.load_fixtures(conn)
    run_id = conn.execute("SELECT id FROM run WHERE work_id='bansan'").fetchone()[0]
    row = conn.execute("SELECT * FROM bible WHERE work_id='bansan' AND kind='reading' ORDER BY version DESC").fetchone()
    body = json.loads(row["body"])
    body["second_crux"] = [{"point": "It is about the husband.", "why": "He speaks last.", "for_the_english": "Keep him plain."}]
    eid = conn.execute("INSERT INTO event (run_id, seq, actor, type, payload) VALUES (?, 9999, 'steer', 'checkpoint.steered', '{}')",
                       (run_id,)).lastrowid
    conn.execute("INSERT INTO bible (work_id, version, kind, body, event_id) VALUES ('bansan', ?, 'reading', ?, ?)",
                 (row["version"] + 1, json.dumps(body), eid))
    conn.execute("UPDATE run SET options=json_set(options, '$.voice', 2) WHERE id=?", (run_id,))
    conn.commit()
    page = TestClient(create_app(tmp_path / "site.db")).get("/read/bansan/analysis").text
    assert "A second reader?" in page and "It is about the husband." in page
    assert escape(edition.RECOMMENDED.sub("", body["voice_takes"][2]["line"]).strip()) in page
    assert escape(edition.RECOMMENDED.sub("", body["voice_takes"][0]["line"]).strip()) not in page


def _body(b):
    return json.loads(b) if isinstance(b, str) else b


def test_model_text_says_analysis_not_bible():
    from house.edition import plain, plain_all
    assert plain("Bible, cast c2: Kayo is now 'Mother'.") == "Analysis, cast: Kayo is now 'Mother'."
    assert plain("I keep 'Baby', per the bible, and the story bible's policy.") == \
        "I keep 'Baby', per the analysis, and the analysis's policy."
    assert plain("The Story Bible and a bible; THE BIBLE; two bibles; cast c1, c3 and c4 too") == \
        "The Analysis and an analysis; THE ANALYSIS; two analyses; cast too"
    assert plain("Bibliography, cast c, c2") == "Bibliography, cast c"  # a bare cast id goes; "c" alone isn't one
    assert plain("He read the Bible every night. Bible, cast c2: shorter.") == "He read the Bible every night. Analysis, cast: shorter."
    assert plain(None) is None and plain("") == ""
    out = plain_all({"handle": "bible c2", "why": ["per the bible"], "anchors": [{"id": "p1", "href": "p1"}]})
    assert out == {"handle": "bible c2", "why": ["per the analysis"], "anchors": [{"id": "p1", "href": "p1"}]}


def test_model_text_says_paragraph_numbers_and_names_not_ids():
    from house.edition import plain, plain_all
    assert plain("Narrator stays close after p10.") == "Narrator stays close after paragraph 10."
    assert plain("Timeline: p2–p9") == "Timeline: paragraphs 2 to 9"
    assert plain("p10-p13: mother serves; p44-46 sweat") == "Paragraphs 10 to 13: mother serves; paragraphs 44 to 46 sweat"
    assert plain("坊や (c1 and c2 in direct speech)") == "坊や (in direct speech)"
    assert plain("(narrator reporting c2's vision)") == "(narrator reporting vision)"
    assert plain("(c3)") == "" and plain("cast c2 stays") == "cast stays"
    cast = {"c1": "Liu Dacheng", "c2": "Sun"}
    assert plain("(narrator reporting c2's vision; c1 and c2)", cast) == "(narrator reporting Sun's vision; Liu Dacheng and Sun)"
    assert plain("up10, pp, p.5 and Bp3 stay") == "up10, pp, p.5 and Bp3 stay"
    # ids and links stay as they are, for linking
    out = plain_all({"anchors": [{"id": "p30", "href": "p29", "label": "paragraph 30"}], "why": "see p30"})
    assert out == {"anchors": [{"id": "p30", "href": "p29", "label": "paragraph 30"}], "why": "see paragraph 30"}


def test_analysis_pages_show_no_ids_and_link_hard_spots_to_their_unit(client):
    import re
    for work in ("bansan", "shuchu"):
        for path in (f"/read/{work}/analysis", f"/read/{work}"):
            text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", client.get(path).text, flags=re.S))
            assert not re.search(r"\b[pc]\d+\b", text), path
    page = client.get("/read/bansan/analysis").text
    # 「晩餐」's p31 is shown merged into the unit that starts at p29: the link goes there, labelled p31
    assert '#p29">paragraph 31</a>' in page
    # a cast entry names the person once, then the Japanese
    shuchu = client.get("/read/shuchu/analysis").text
    assert "<b>Liu Dacheng</b> <span class=\"nm\">劉大成</span>" in shuchu and "Liu Dacheng Liu Dacheng" not in shuchu


def test_the_shelf_counts_paragraphs_as_the_reader_shows_them(client):
    home = client.get("/").text
    for work in ("bansan", "shuchu"):
        units = client.get(f"/read/{work}").text.count('class="unit ')
        assert f"· {units} paragraphs" in home, work
