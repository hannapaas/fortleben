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


def render(d, replay=False, closed=None, page="desk.html", **ctx):
    return env.get_template(page).render(desk=d, replay=replay, closed=closed, **ctx)


def steps(at: int) -> list[dict]:
    from house.desk import STEPS
    return [{"label": label, "state": "done" if i < at else "now" if i == at else "next", "yours": i == 1}
            for i, (label, _) in enumerate(STEPS)]


def test_the_desk_lists_your_translations_and_starts_a_new_one_on_its_own_page():
    html = render(desk())
    assert 'href="/read/bansan">Read it' in html and "Interrupted at drafting" in html and ">Resume<" in html
    assert 'href="/desk/translations/31"><i>Supper</i>' in html and 'href="/desk/new">Start a new translation' in html
    assert html.index("Your translations?") < html.index("Who?") and 'value="sumiyaki"' not in html
    assert "$" not in html and "desk.js" in html and "desk.css" in html


def test_a_new_translation_lists_the_works_and_what_they_cost():
    html = render(desk(), page="desk_new.html")
    assert "2,514" in html and "drops of ink" in html and 'href="/desk">← Your desk' in html
    assert html.index("The Charcoal-Burner") < html.index("The Soil")  # the suggested work comes first
    assert 'value="sumiyaki" data-estimate="2000" data-title="The Charcoal-Burner&#39;s Daughter" checked' in html
    assert 'value="tsuchi"' in html and "48,686 more than you have" in html and 'id="start"' in html


def test_busy_disables_start():
    html = render(desk(busy=True), page="desk_new.html")
    assert 'id="start" disabled' in html and "Fortleben is full at the moment: three translations are going" in html
    assert 'class="btn resume" disabled' in render(desk(busy=True))


def test_a_run_of_your_own_going_disables_start_only():
    html = render(desk(going=True), page="desk_new.html")
    assert 'id="start" disabled' in html and "You have a translation going already" in html
    assert 'class="btn resume" disabled' not in render(desk(going=True))


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
    "files": [{"name": "reading", "title": "The reading", "text": "**The crux**\n\n- A potato opens a vision.", "edited": True},
              {"name": "voices", "title": "The voices", "text": "## Voice 0: a\n\nPlain and quiet.", "edited": False},
              {"name": "bible", "title": "The analysis", "text": "### Cast\n- **c1 the young mother**", "edited": False}]}


def test_a_waiting_run_shows_the_checkpoint_in_order():
    waiting = {"id": 34, "work_id": "bansan", "title_en": "Supper", "status": "waiting", "stage": "checkpoint",
               "stage_label": "waiting for the editor", "reserved": 0, "spent": 300, "started": "3 Nov 2026", "edition_url": None}
    assert 'href="/desk/translations/34">Review and approve' in render(desk(runs=[waiting]))
    html = render(desk(runs=[dict(waiting, steps=steps(1))], checkpoints=[CHECKPOINT]), page="desk_run.html", run_id=34)
    assert "Waiting for you." in html and 'id="checkpoint-34"' in html
    assert '<li class="step done">Reading the story' in html and 'class="step now yours" aria-current="step">Your review' in html
    assert '<li class="step next">Drafting the English' in html and 'class="dots"' not in html  # nothing moves while it's yours
    order = ["what every stage of the translation will read", "The reading", "A potato opens a vision", "The analysis",
             "c1 the young mother", "The voice", "Plain and quiet.", "Warmer.", "Less formal.", "The register is plainer now.",
             "Is the baby a girl", "Send note", "Approve and translate"]
    at = [html.index(x) for x in order]
    assert at == sorted(at)
    assert html.count("A potato opens a vision") == 1  # each file once
    assert 'class="voice picked"' in html and 'value="Warmer."' not in html  # no fields without a voices file
    assert '<button type="button" class="btn go send" hidden>Send note</button>' in html  # until a note is written
    assert 'name="voice-34" value="1" checked' in html and "redrafted after your note" in html
    assert "<p>The lamp swung.</p>" in html and "Edited by you." in html
    assert '<button type="button" class="btn save" disabled>Save</button>' in html  # until something changes
    assert "Reading your note" in html and 'class="line reading-note" aria-live="polite" hidden' in html


RUN = {"id": 34, "work_id": "bansan", "title_en": "Supper", "status": "waiting", "stage": "checkpoint", "stage_label": "",
       "reserved": 0, "spent": 300, "started": "3 Nov 2026", "edition_url": None, "steps": steps(1)}


def test_a_running_translation_shows_its_stage_moving():
    html = render(desk(runs=[dict(RUN, status="running", stage="draft", steps=steps(3))]), page="desk_run.html", run_id=34)
    assert 'class="step now" aria-current="step">Checking it against the Japanese and revising<span class="dots"' in html
    assert html.count('class="step done') == 3 and html.count('class="step next"') == 3


def test_the_checkpoint_while_a_note_is_read_and_when_the_house_is_full():
    html = render(desk(runs=[RUN], checkpoints=[dict(CHECKPOINT, steering=True)]), page="desk_run.html", run_id=34)
    assert 'data-steering="1"' in html and 'class="btn go send" hidden disabled' in html and 'class="btn go approve" disabled' in html
    assert 'class="line reading-note" aria-live="polite">' in html
    full = render(desk(busy=True, runs=[RUN], checkpoints=[CHECKPOINT]), page="desk_run.html", run_id=34)
    assert 'class="btn go send" hidden>' in full and 'class="btn go approve" disabled' in full and 'data-full="1"' in full


def test_closed_disables_start_and_resume():
    closed = "Runs can't start here: this copy of the site has no model key."
    assert 'id="start" disabled' in render(desk(), closed=closed, page="desk_new.html")
    html = render(desk(), closed=closed)
    assert 'class="btn resume" disabled' in html and "has no model key" in html and "Start a new translation" not in html


def test_no_desk_is_one_line():
    html = render(None, replay=True)
    assert "Translations can't be started" in html and 'id="desk"' not in html and "desk.js" not in html
