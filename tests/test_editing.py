"""The editor's own hand: rewriting the files a waiting run drafts from (on the desk and in the terminal),
and changing the English of their published edition, each kept in the record and shown as theirs.
All on 「晩餐」 from the committed fixture, with no key."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from house import context, desk, edition, orchestrator, pager, steer, web
from house.cli import main
from house.client import FIXTURES, FakeClient
from house.db import connect
from house.stages import Ctx
from house.stages.draft import stable_for, voice_take

DESK = {"X-Requested-With": "fetch"}
RECORDED = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
MODELS = {k: v for k, v in RECORDED["run"]["options"].items() if k.endswith("_model")}
CRUX = "**The crux**\n\n- **A supper that is a vision.** Hold the plainness; the vision is in the potatoes."


@pytest.fixture(autouse=True)
def keyless(monkeypatch):
    monkeypatch.setenv("KEIKAKU_SECRET", "test-secret")
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("HOUSE_OPEN", "true")
    monkeypatch.setattr("house.web.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(desk, "make_client", lambda conn, run_cap=None, **kw: FakeClient(
        conn, cache_dirs=[FIXTURES / "bansan" / "responses"], run_cap=run_cap))
    monkeypatch.setattr(desk, "DEFAULT_OPTIONS", MODELS)
    monkeypatch.setattr(desk, "_live", set())
    monkeypatch.setattr(desk, "_steering", set())
    monkeypatch.setattr(desk, "spawn", lambda fn, *args: fn(*args))


@pytest.fixture
def db(tmp_path):
    return tmp_path / "k.db"


@pytest.fixture
def conn(db):
    return connect(db)


@pytest.fixture
def waiting(conn, db):
    """An invited editor's run of bansan, waiting at the checkpoint."""
    token = desk.invite(conn, "Ines Example", work="bansan")
    run_id = desk.start(db, token, "bansan", True, "Ines Example")
    assert desk.state(conn, token)["runs"][0]["status"] == "waiting"
    return token, run_id


@pytest.fixture
def done(conn, db, waiting):
    """The same run approved in the recorded voice and published: Ines's edition."""
    token, run_id = waiting
    desk.approve(db, token, run_id, 0)
    ed = conn.execute("SELECT edition_id FROM release WHERE run_id=?", (run_id,)).fetchone()[0]
    return token, run_id, ed


def ctx_of(conn, run_id) -> Ctx:
    return orchestrator.context_for(conn, None, run_id)


# --- the files, at the checkpoint ------------------------------------------------------------------

def test_an_edited_reading_is_what_every_later_call_reads(conn, db, waiting):
    token, run_id = waiting
    before = stable_for(ctx_of(conn, run_id), voice_take(ctx_of(conn, run_id)))
    old = steer.texts(ctx_of(conn, run_id).latest("reading"), ctx_of(conn, run_id).latest("bible"))["reading"]
    assert old in before  # the file is, word for word, what the drafter reads

    assert desk.edit_file(db, token, run_id, "reading", CRUX + "\r\n\r\nShe is not dreaming.  \n") is True
    assert [f["edited"] for f in desk.state(conn, token)["checkpoints"][0]["files"]] == [True, False, False]
    ctx = ctx_of(conn, run_id)
    assert ctx.latest("reading")["edited_text"] == CRUX + "\n\nShe is not dreaming."
    after = stable_for(ctx, voice_take(ctx))
    assert "She is not dreaming." in after and old not in after
    assert context.reading(ctx.latest("reading")).startswith("## The house's reading\n")  # labelled as before
    ev = steer.edits(conn, run_id)
    assert [(e["file"], e["by"]) for e in ev] == [("reading", "Ines Example")]
    assert ev[0]["before"] == old.strip() and ev[0]["after"].endswith("She is not dreaming.")

    assert desk.edit_file(db, token, run_id, "reading", CRUX + "\n\nShe is not dreaming.") is False  # nothing new
    assert desk.edit_file(db, token, run_id, "reading", old) is True  # put back: the stored reading again
    assert "edited_text" not in ctx_of(conn, run_id).latest("reading")
    assert len(steer.edits(conn, run_id)) == 2


def test_the_voices_file_renames_a_voice_and_must_keep_them_all(conn, db, waiting):
    token, run_id = waiting
    takes = ctx_of(conn, run_id).latest("reading")["voice_takes"]
    text = steer.voices_text(takes).replace(takes[0]["line"], "Short sentences; the mother never softens.")
    assert desk.edit_file(db, token, run_id, "voices", text)
    ctx = ctx_of(conn, run_id)
    assert voice_take(ctx)["line"] == "Short sentences; the mother never softens."
    assert "Short sentences; the mother never softens." in stable_for(ctx, voice_take(ctx))
    cp = desk.state(conn, token)["checkpoints"][0]
    assert cp["voices"][0]["line"] == "Short sentences; the mother never softens."
    assert [f["edited"] for f in cp["files"]] == [False, True, False]

    gone = text.split("## Voice 1")[0]
    with pytest.raises(desk.Refused, match="one heading per voice"):
        desk.edit_file(db, token, run_id, "voices", gone)
    with pytest.raises(desk.Refused, match="needs a name"):
        desk.edit_file(db, token, run_id, "voices", text.replace(f"## Voice 0: {takes[0]['label']}", "## Voice 0:"))


def test_an_edited_bible_is_read_and_the_desk_shows_the_files(conn, db, waiting):
    token, run_id = waiting
    old = desk.state(conn, token)["checkpoints"][0]["files"]
    assert [f["name"] for f in old] == ["reading", "voices", "bible"] and not any(f["edited"] for f in old)
    bible = next(f for f in old if f["name"] == "bible")["text"]
    assert desk.edit_file(db, token, run_id, "bible", bible + "\n\n### House rule\n- The baby is a girl throughout.")
    ctx = ctx_of(conn, run_id)
    assert "The baby is a girl throughout." in context.bible(ctx.latest("bible"))
    cp = desk.state(conn, token)["checkpoints"][0]
    assert [f["edited"] for f in cp["files"]] == [False, False, True]


def test_files_are_refused_unless_the_run_waits_and_the_text_is_there(conn, db, waiting):
    token, run_id = waiting
    with pytest.raises(desk.Refused, match="empty"):
        desk.edit_file(db, token, run_id, "reading", "   ")
    with pytest.raises(desk.Refused, match="no such file"):
        desk.edit_file(db, token, run_id, "secrets", "x")
    other = desk.invite(conn, "Someone else")
    with pytest.raises(desk.Refused, match="no such run"):
        desk.edit_file(db, other, run_id, "reading", "x")
    desk._steering.add(run_id)
    with pytest.raises(desk.Refused, match="still reading your last note"):
        desk.edit_file(db, token, run_id, "reading", "x")
    desk._steering.discard(run_id)
    desk.approve(db, token, run_id, 0)
    with pytest.raises(desk.Refused, match="only while the run waits"):
        desk.edit_file(db, token, run_id, "reading", "x")


def test_a_note_after_an_edit_is_read_against_it(conn, db, waiting, monkeypatch):
    """The steer call sees the editor's version beside the stored one; the amended reading it returns
    replaces both, and the bible nobody touched keeps its own edit."""
    token, run_id = waiting
    ctx = ctx_of(conn, run_id)
    desk.edit_file(db, token, run_id, "reading", CRUX + "\n\nShe is not dreaming.")
    bible = steer.texts(ctx.latest("reading"), ctx.latest("bible"))["bible"]
    desk.edit_file(db, token, run_id, "bible", bible + "\n\n- The baby is a girl.")
    reading, stored_bible = ctx_of(conn, run_id).latest("reading"), ctx_of(conn, run_id).latest("bible")
    first = [p.id for p in pager.pages(ctx.work.paragraphs)[0]]
    seen = []

    def call(self, actor, c):
        seen.append(c)
        if c.prompt == "steer":
            return SimpleNamespace(call_id=None, data={
                "reply": "Done.", "changed": ["The crux"], "question": "",
                "reading": {**steer.fields(reading, steer.READING_FIELDS), "reading": "She is not dreaming, and the English says so."},
                "bible": steer.fields(stored_bible, steer.BIBLE_FIELDS)})
        return SimpleNamespace(call_id=None, data={"items": [{"ids": [pid], "english": "x", "notes": []} for pid in first]})
    monkeypatch.setattr(Ctx, "call", call)
    rnd = steer.steer(conn, SimpleNamespace(budget=SimpleNamespace(cap_given=True)), run_id, "Make it plainer.")
    assert rnd["reply"] == "Done."
    inp = seen[0].input
    assert "The reading as it now reads, rewritten by hand" in inp and "She is not dreaming." in inp
    assert "The bible as it now reads, rewritten by hand" in inp and "The baby is a girl." in inp
    now = ctx_of(conn, run_id)
    assert "edited_text" not in now.latest("reading") and "the English says so" in context.reading(now.latest("reading"))
    assert "The baby is a girl." in context.bible(now.latest("bible"))  # unchanged by the note, so still the edit


# --- the files, in the terminal -----------------------------------------------------------------------

@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KEIKAKU_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


def test_the_terminal_takes_files_edited_by_hand(conn, db, waiting, data_dir, capsys):
    _, run_id = waiting
    assert main(["--db", str(db), "checkpoint", "bansan"]) == 0
    folder = data_dir / "checkpoints" / "bansan"
    reading = (folder / "reading.md").read_text(encoding="utf-8")
    assert reading.startswith("# The house's reading:")
    voices = (folder / "voices.md").read_text(encoding="utf-8")
    take = ctx_of(conn, run_id).latest("reading")["voice_takes"][1]
    assert f"## Voice 1: {take['label']}\n\n*{take['line']}*" in voices

    (folder / "reading.md").write_text(reading.split("\n", 1)[0] + "\n\n" + CRUX + "\n", encoding="utf-8")
    (folder / "voices.md").write_text(voices.replace(f"*{take['line']}*", "*Colder, and shorter.*"), encoding="utf-8")
    capsys.readouterr()
    assert main(["--db", str(db), "checkpoint", "bansan"]) == 0  # reads the edits before writing the files again
    printed = capsys.readouterr().out
    assert "Your edit of reading.md is saved" in printed and "Your edit of voices.md is saved" in printed
    ctx = ctx_of(conn, run_id)
    assert ctx.latest("reading")["edited_text"] == CRUX
    assert ctx.latest("reading")["voice_takes"][1]["line"] == "Colder, and shorter."
    assert (folder / "reading.md").read_text(encoding="utf-8").endswith(CRUX + "\n")  # the file is the edit
    assert main(["--db", str(db), "checkpoint", "bansan"]) == 0
    assert "Your edit" not in capsys.readouterr().out  # taken once

    (folder / "voices.md").write_text("## Voice 0: only one\n\nx\n", encoding="utf-8")
    assert main(["--db", str(db), "approve", "bansan", "--voice", "0"]) == 1
    assert "one heading per voice" in capsys.readouterr().out
    assert conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "waiting"


def test_files_written_for_another_run_are_left_alone(conn, db, waiting, data_dir):
    _, run_id = waiting
    folder = data_dir / "checkpoints" / "bansan"
    steer.write(conn, run_id, folder)
    (folder / "reading.md").write_text("# x\n\nsomething else", encoding="utf-8")
    assert steer.read_back(conn, run_id + 1, folder) == []
    (folder / steer.WRITTEN).unlink()
    assert steer.read_back(conn, run_id, folder) == []


# --- the English, after publication -------------------------------------------------------------------

def unit(ed: dict, uid: str) -> dict:
    return next(u for u in ed["units"] if u["id"] == uid)


def first_unit(conn, ed_id) -> dict:
    return next(u for u in edition.edition(conn, "bansan", ed_id)["units"] if not u["number"])


def test_the_editor_changes_a_paragraph_and_the_page_says_it_was_them(conn, done):
    token, run_id, ed_id = done
    ines = desk.editor(conn, token)
    u = first_unit(conn, ed_id)
    old = u["en"]
    assert edition.edit(conn, ed_id, u["id"], "  The storm   came in.\n", ines) is True
    assert edition.edit(conn, ed_id, u["id"], "The storm came in.", ines) is False  # nothing new
    assert edition.edit(conn, ed_id, u["id"], "The storm came in at last.", ines) is True
    ed = edition.edition(conn, "bansan", ed_id)
    now = unit(ed, u["id"])
    assert now["en"] == "The storm came in at last." and ed["edited"] == 1
    assert [e["by"] for e in now["edits"]] == ["Ines Example", "Ines Example"]
    assert now["edits"][0]["diff"] == "The storm came in<ins> at last</ins>."  # newest first
    assert now["edits"][1]["date"] and "<del>" in now["edits"][1]["diff"]
    assert all(h["en"] != "The storm came in." for h in now["history"])  # keikaku's history stays keikaku's
    # In the record: a revision and its event, with before and after.
    ev = edition.hand_edits(conn, run_id)
    assert ev[0]["before"] == old and ev[-1]["english"] == "The storm came in at last." and ev[0]["person_id"] == ines["id"]
    # The house's edition and someone else are refused.
    house = conn.execute("SELECT id FROM edition WHERE editor='the house'").fetchone()
    with pytest.raises(edition.NotEditable, match="Only the editor"):
        edition.edit(conn, ed_id, u["id"], "x", {"id": ines["id"] + 99})
    if house:
        with pytest.raises(edition.NotEditable):
            edition.edit(conn, house[0], u["id"], "x", ines)
    with pytest.raises(edition.NotEditable, match="no such paragraph"):
        edition.edit(conn, ed_id, "p9999", "x", ines)
    with pytest.raises(edition.NotEditable, match="empty"):
        edition.edit(conn, ed_id, u["id"], " \n ", ines)


def test_a_group_is_edited_once_and_kept_whole(conn, done):
    _, run_id, ed_id = done
    ines = desk.editor(conn, done[0])
    group = next((u for u in edition.edition(conn, "bansan", ed_id)["units"] if len(u["paras"]) > 1), None)
    if group is None:
        pytest.skip("the recorded run has no groups")
    edition.edit(conn, ed_id, group["id"], "Joined, and edited.", ines)
    assert json.loads(conn.execute("SELECT segment_ids FROM revision ORDER BY id DESC LIMIT 1").fetchone()[0]) == group["paras"]
    with pytest.raises(edition.NotEditable):
        edition.edit(conn, ed_id, group["paras"][1], "x", ines)


@pytest.fixture
def site(db):
    return TestClient(web.create_app(db, screen=False))


def test_the_reader_page_lets_only_its_editor_edit(conn, db, done, site):
    token, run_id, ed_id = done
    page = site.get(f"/read/bansan?edition={ed_id}&edit=1").text
    assert "Edit the English" not in page and 'class="reader editing"' not in page  # not signed in
    u = first_unit(conn, ed_id)
    assert site.post("/read/bansan/edit", json={"edition": ed_id, "segment": u["id"], "english": "x"}, headers=DESK).status_code == 401

    site.get(f"/desk/{token}")  # the invite link signs Ines in
    page = site.get(f"/read/bansan?edition={ed_id}")
    assert page.headers["cache-control"] == "no-store" and "Edit the English" in page.text
    page = site.get(f"/read/bansan?edition={ed_id}&edit=1").text
    assert 'class="reader editing"' in page and f'data-edition="{ed_id}"' in page and "You're editing the English" in page
    assert site.post("/read/bansan/edit", json={"edition": ed_id, "segment": u["id"], "english": "x"}).status_code == 403  # no header
    r = site.post("/read/bansan/edit", json={"edition": ed_id, "segment": u["id"], "english": "The storm, <b>at last</b>."}, headers=DESK)
    assert r.status_code == 200 and r.json() == {"ok": True, "changed": True}
    page = site.get(f"/read/bansan?edition={ed_id}").text
    assert "Edited by Ines Example" in page
    assert "<b>at last</b>" not in page and "&lt;b&gt;at last&lt;/b&gt;" in page  # escaped, in the text and the diff
    assert "changed 1 paragraph by hand" in page and "No person has edited it." not in page
    assert site.post("/read/bansan/edit", json={"edition": ed_id, "segment": u["id"], "english": ""}, headers=DESK).status_code == 400
    assert site.post("/read/sumiyaki/edit", json={"edition": ed_id, "segment": u["id"], "english": "x"}, headers=DESK).status_code == 404
    assert site.post("/read/bansan/edit", json={"edition": "1", "segment": u["id"], "english": "x"}, headers=DESK).status_code == 400

    # Someone else, signed in, sees no way to edit and is refused.
    other = TestClient(web.create_app(db, screen=False))
    other.get(f"/desk/{desk.invite(conn, 'Someone')}")
    assert "Edit the English" not in other.get(f"/read/bansan?edition={ed_id}&edit=1").text
    assert other.post("/read/bansan/edit", json={"edition": ed_id, "segment": u["id"], "english": "y"}, headers=DESK).status_code == 403


def test_the_desk_offers_to_edit_a_finished_edition(conn, done):
    token, run_id, ed_id = done
    run = desk.state(conn, token)["runs"][0]
    assert run["edit_url"] == f"/read/bansan?edition={ed_id}&edit=1"


def test_the_appendix_publishes_what_the_editor_changed_in_the_files(conn, db, waiting, site):
    token, run_id = waiting
    desk.edit_file(db, token, run_id, "reading", CRUX + "\n\nShe is not dreaming.")
    # The draft under the edited reading would miss the recording, so the run is published by hand from the
    # recorded release: the release is this run's, so the appendix reads this run's edits.
    ed_id = conn.execute("INSERT INTO edition (work_id, editor) VALUES ('bansan', 'Ines Example')").lastrowid
    rel = conn.execute("INSERT INTO release (edition_id, run_id, version, body) VALUES (?, ?, 'v0.1', ?)",
                       (ed_id, run_id, json.dumps(RECORDED["release"], ensure_ascii=False))).lastrowid
    conn.execute("UPDATE edition SET current_release=? WHERE id=?", (rel, ed_id))
    conn.commit()
    page = site.get(f"/read/bansan/analysis?edition={ed_id}").text
    assert "Changed by hand?" in page and "The reading</b>, edited by Ines Example" in page
    assert "<ins>She</ins>" in page and "<del>" in page and "<ins>dreaming" in page
    assert "what Ines Example changed in it by hand" in site.get(f"/read/bansan?edition={ed_id}").text


def test_the_desk_route_saves_a_file_and_refuses_without_its_header(conn, db, waiting, site):
    token, run_id = waiting
    url = f"/desk/{token}/runs/{run_id}/files/reading"
    assert site.post(url, json={"text": CRUX}).status_code == 403  # not from the desk page
    r = site.post(url, json={"text": CRUX}, headers=DESK)
    assert r.status_code == 200 and r.json() == {"ok": True, "changed": True}
    assert site.post(url, json={"text": CRUX}, headers=DESK).json() == {"ok": True, "changed": False}
    assert site.post(url, json={"text": 7}, headers=DESK).status_code == 400
    assert site.post(f"/desk/{token}/runs/{run_id}/files/nope", json={"text": "x"}, headers=DESK).status_code == 404
    page = site.get(f"/desk/{token}").text
    assert "three files" in page and "Edited by you." in page


# --- what the review turned up --------------------------------------------------------------------------

def test_a_note_that_replaces_an_edit_says_so_in_the_record(conn, db, waiting, monkeypatch):
    token, run_id = waiting
    desk.edit_file(db, token, run_id, "reading", CRUX + "\n\nTHE FATHER IS A GHOST.")
    reading, bible = ctx_of(conn, run_id).latest("reading"), ctx_of(conn, run_id).latest("bible")
    first = [p.id for p in pager.pages(ctx_of(conn, run_id).work.paragraphs)[0]]

    def call(self, actor, c):
        if c.prompt == "steer":
            return SimpleNamespace(call_id=None, data={"reply": "Done.", "changed": ["The reading"], "question": "",
                                                       "reading": {**steer.fields(reading, steer.READING_FIELDS), "reading": "Plainer."},
                                                       "bible": steer.fields(bible, steer.BIBLE_FIELDS)})
        return SimpleNamespace(call_id=None, data={"items": [{"ids": [pid], "english": "x", "notes": []} for pid in first]})
    monkeypatch.setattr(Ctx, "call", call)
    steer.steer(conn, SimpleNamespace(budget=SimpleNamespace(cap_given=True)), run_id, "Plainer.")
    last = steer.edits(conn, run_id)[-1]
    assert (last["by"], last["cause"], last["file"]) == ("keikaku", "note", "reading")
    assert "GHOST" in last["before"] and "GHOST" not in last["after"]
    assert edition.file_edits(conn, run_id)[-1]["cause"] == "note"


def test_headings_and_house_editions_cant_be_edited(conn, done):
    token, run_id, ed_id = done
    ines = desk.editor(conn, token)
    paras = json.loads(conn.execute("SELECT body FROM release WHERE run_id=?", (run_id,)).fetchone()[0])["views"]["casual"]
    heading = next((p for p in paras if edition.NUMBER.fullmatch(p["ja"].strip("　 "))), None)
    if heading:
        with pytest.raises(edition.NotEditable):
            edition.edit(conn, ed_id, heading["id"], "Chapter One", ines)
    conn.execute("UPDATE edition SET editor='the house' WHERE id=?", (ed_id,))
    with pytest.raises(edition.NotEditable, match="Only the editor"):
        edition.edit(conn, ed_id, first_unit(conn, ed_id)["id"], "x", ines)


def test_long_diffs_stay_quick_and_whole():
    import time
    long = " ".join(f"w{i % 7}" for i in range(4000))
    t = time.time()
    out = edition.diff_html(long, long + " end")
    assert time.time() - t < 0.5 and out.startswith("<del>") and "<ins>" in out
    assert edition.diff_html("a <b>", "a <i>") == "a &lt;<del>b</del><ins>i</ins>&gt;"


def test_a_renamed_voice_is_published_as_the_editors(conn, db, waiting):
    token, run_id = waiting
    takes = ctx_of(conn, run_id).latest("reading")["voice_takes"]
    desk.edit_file(db, token, run_id, "voices", steer.voices_text(takes).replace(takes[0]["line"], "Flat and cold."))
    assert edition.analysis(conn, "bansan", run_id)["voice_by"] == "Ines Example"
    assert len(steer.edits(conn, run_id)) == 1 and steer.edits(conn, run_id)[0]["person_id"] == desk.editor(conn, token)["id"]


def test_terminal_edits_for_another_run_are_kept_aside_and_said(conn, db, waiting, data_dir, capsys):
    _, run_id = waiting
    folder = data_dir / "checkpoints" / "bansan"
    steer.write(conn, run_id, folder)
    written = json.loads((folder / steer.WRITTEN).read_text())
    (folder / steer.WRITTEN).write_text(json.dumps({**written, "run": run_id + 1}))  # as if for an older run
    (folder / "reading.md").write_text("# x\n\nmine", encoding="utf-8")
    capsys.readouterr()
    assert main(["--db", str(db), "checkpoint", "bansan"]) == 0
    out = capsys.readouterr().out
    assert "reading.md wasn't taken" in out and "reading.unused.md" in out
    assert (folder / "reading.unused.md").read_text(encoding="utf-8").endswith("mine")
    assert "edited_text" not in ctx_of(conn, run_id).latest("reading")


def test_paragraph_edits_are_capped_per_hour(monkeypatch):
    from house import accounts
    monkeypatch.setattr(accounts, "_edits", type(accounts._edits)(accounts._edits.default_factory))
    assert all(accounts.allow_edit(7, now=1000.0) for _ in range(accounts.EDITS_PER_HOUR))
    assert not accounts.allow_edit(7, now=1000.0) and accounts.allow_edit(8, now=1000.0)
    assert accounts.allow_edit(7, now=1000.0 + 3601)
