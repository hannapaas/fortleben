"""The desk page renders from the agreed context, without the backend (docs/EDITORS-DESK.md)."""

from jinja2 import Environment, FileSystemLoader

from house.db import ROOT

env = Environment(loader=FileSystemLoader(ROOT / "site/templates"), autoescape=True)
env.globals["url_for"] = lambda name, path: f"/static/{path}"


def desk(**over):
    d = {"token": "tok", "editor": {"name": "Ines Moreau", "credit_as": None},
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
    assert 'id="start" disabled' in html and "Another translation is running on the site" in html


def test_closed_disables_start_and_resume():
    html = render(desk(), closed="Runs can't start here: this copy of the site has no model key.")
    assert 'id="start" disabled' in html and 'class="btn resume" disabled' in html and "has no model key" in html


def test_no_desk_is_one_line():
    html = render(None, replay=True)
    assert "Translations can't be started" in html and 'id="desk"' not in html and "desk.js" not in html
