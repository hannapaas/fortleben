"""The desk page renders from the agreed context, without the backend (docs/EDITORS-DESK.md)."""

from jinja2 import Environment, FileSystemLoader

from house.db import ROOT

env = Environment(loader=FileSystemLoader(ROOT / "site/templates"), autoescape=True)
env.globals["url_for"] = lambda name, path: f"/static/{path}"


def desk(**over):
    d = {"base": "/desk", "editor": {"name": "Ines Moreau", "credit_as": None},
         "allowance": {"granted": 4000, "reserved": 0, "spent": 1486, "available": 2514},
         "suggested": "sumiyaki", "busy": False,
         "works": [
             {"id": "tsuchi", "title": "土", "title_en": "The Soil", "author_en": "Nagatsuka Takashi", "year": 1910,
              "blurb": None, "sheets": 512.0, "estimate": 51200, "covered": False, "has_edition": False},
             {"id": "sumiyaki", "title": "炭燒のむすめ", "title_en": "The Charcoal-Burner's Daughter",
              "author_en": "Nagatsuka Takashi", "year": 1906, "blurb": None, "sheets": 20.0, "estimate": 2000,
              "covered": True, "has_edition": False}],
         "runs": [
             {"id": 31, "work_id": "bansan", "title_en": "Supper", "status": "done", "stage": "release",
              "stage_label": "published", "reserved": 0, "spent": 1486, "started": "2 Nov 2026", "edition_url": "/read/bansan"},
             {"id": 32, "work_id": "x", "title_en": "Snow", "status": "interrupted", "stage": "draft",
              "stage_label": "drafting", "reserved": 900, "spent": 410, "started": "2 Nov 2026", "edition_url": None}]}
    d.update(over)
    return d


def render(d, replay=False, closed=None):
    return env.get_template("desk.html").render(desk=d, replay=replay, closed=closed)


def test_desk_renders_allowance_works_and_runs():
    html = render(desk())
    assert "2,514" in html and "drops of ink" in html
    assert html.index("The Charcoal-Burner") < html.index("The Soil")  # the suggested work comes first
    assert 'value="sumiyaki" data-estimate="2000" data-title="The Charcoal-Burner&#39;s Daughter" checked' in html
    assert 'value="tsuchi"' in html and "48,686 more than you have" in html
    assert 'href="/read/bansan">Read it' in html and "Interrupted at drafting" in html and ">Resume<" in html
    assert "$" not in html and "desk.js" in html and "desk.css" in html


def test_busy_disables_start():
    html = render(desk(busy=True))
    assert 'id="start" disabled' in html and "Fortleben is full at the moment: three translations are going" in html
    assert 'class="btn resume" disabled' in html


def test_a_run_of_your_own_going_disables_start_only():
    html = render(desk(going=True))
    assert 'id="start" disabled' in html and "You have a translation going already" in html
    assert 'class="btn resume" disabled' not in html


def test_a_failed_run_says_why_and_can_be_resumed():
    failed = {"id": 33, "work_id": "x", "title_en": "Snow", "status": "failed", "stage": "draft", "stage_label": "checking against the Japanese",
              "reserved": 0, "spent": 900, "started": "3 Nov 2026", "edition_url": None,
              "failure": "It stopped when its budget ran out. Everything it finished is kept; resume it and it carries on from there."}
    html = render(desk(runs=[failed]))
    assert "Failed at checking against the Japanese." in html and "It stopped when its budget ran out." in html
    assert ">Resume<" in html and "nothing is paid for twice" not in html and "$" not in html


CHECKPOINT = {
    "run_id": 34, "title_en": "Supper", "voice": 1, "steering": False, "steer_error": None,
    "voices": [{"label": "a", "line": "Plain and quiet.", "english": ["Outside the door, a storm."], "redrafted": False},
               {"label": "b", "line": "Warmer.", "english": ["Outside, the storm had come.", "The lamp swung."], "redrafted": True}],
    "rounds": [{"note": "Less formal.", "reply": "The register is plainer now.", "changed": ["Style sheet: register"],
                "question": "Is the baby a girl throughout?", "english": ["Outside, the storm had come."]}],
    "reading": {"crux": [{"point": "A potato opens a vision.", "for_the_english": "Keep it plain."}], "second_crux": [],
                "prose": ["First paragraph of the reading.", "Second."], "questions": ["Is 坊や a girl's pet name?"]},
    "bible": {"cast": [{"handle": "the young mother", "role": "wife and mother", "name": "", "addressed": "女 (narrator)"}],
              "style_sheet": [{"label": "Register", "value": "Plain."}], "narration": [{"label": "Narrator", "value": "Close third."}],
              "motifs": [{"motif": "quiet and rest", "english": "Repeat, don't vary."}],
              "hard_spots": [{"where": "p8, p30", "kind": "address", "why": "坊や for a girl."}]}}


def test_a_waiting_run_shows_the_checkpoint_in_order():
    waiting = {"id": 34, "work_id": "bansan", "title_en": "Supper", "status": "waiting", "stage": "checkpoint",
               "stage_label": "waiting for the editor", "reserved": 0, "spent": 300, "started": "3 Nov 2026", "edition_url": None}
    html = render(desk(runs=[waiting], checkpoints=[CHECKPOINT]))
    assert "Waiting for you." in html and 'href="#checkpoint-34"' in html
    order = ["ready to draft", "A potato opens a vision", "First paragraph of the reading", "Is 坊や a girl",
             "Voice a", "Voice b", "Style sheet", "the young mother", "quiet and rest", "Less formal.",
             "The register is plainer now.", "Is the baby a girl", "Send note", "Approve and draft"]
    at = [html.index(x) for x in order]
    assert at == sorted(at)
    assert 'name="voice-34" value="1" checked' in html and "redrafted after your note" in html
    assert "<p>The lamp swung.</p>" in html
    assert '<details class="bible" open><summary>Style sheet' in html and '<details class="bible"><summary>Cast' in html
    assert "Reading your note" in html and 'class="line reading-note" aria-live="polite" hidden' in html


def test_the_checkpoint_while_a_note_is_read_and_when_the_house_is_full():
    html = render(desk(checkpoints=[dict(CHECKPOINT, steering=True)]))
    assert 'data-steering="1"' in html and 'class="btn send" disabled' in html and 'class="btn go approve" disabled' in html
    assert 'class="line reading-note" aria-live="polite">' in html
    full = render(desk(busy=True, checkpoints=[CHECKPOINT]))
    assert 'class="btn send">' in full and 'class="btn go approve" disabled' in full and 'data-full="1"' in full


def test_closed_disables_start_and_resume():
    html = render(desk(), closed="Runs can't start here: this copy of the site has no model key.")
    assert 'id="start" disabled' in html and 'class="btn resume" disabled' in html and "has no model key" in html


def test_no_desk_is_one_line():
    html = render(None, replay=True)
    assert "Translations can't be started" in html and 'id="desk"' not in html and "desk.js" not in html
