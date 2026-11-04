from types import SimpleNamespace

from house.stages.common import Editor, change_flags

OLD = "Outside the door, grown dark, a violent sound of rain and wind — a storm."


def test_a_small_change_for_its_note_is_not_flagged():
    new = "Outside the darkened door, a violent sound of rain and wind — a storm."
    assert change_flags(OLD, new) == []


def test_a_shrunken_paragraph_is_flagged():
    flags = change_flags(OLD, "A storm.")
    assert any(f.startswith("paragraph shrank") for f in flags)


def editor(units, locked=()):
    conn = SimpleNamespace(execute=lambda *a: [{"segment_id": pid} for pid in locked])
    return Editor(SimpleNamespace(conn=conn, work_id="w"), units)


def test_an_edit_matches_once_and_forgives_copied_quotation_marks():
    ed = editor({("p1",): 'He said, "It\'s a storm." She nodded.'})
    assert ed("edit", {"old": '“"It\'s a storm."”', "new": '“"A storm."”', "reason": "", "replace_all": False}).startswith("Done")
    assert ed.edited()[("p1",)]["english"] == 'He said, "A storm." She nodded.'


def test_an_edit_found_more_than_once_is_refused_with_where_unless_replace_all():
    ed = editor({("p1",): "Ryujiro ran.", ("p2",): "Ryujiro and Ryujiro laughed."})
    reply = ed("edit", {"old": "Ryujiro", "new": "Ryūjirō", "reason": "", "replace_all": False})
    assert reply.startswith("Error: found 3 times") and "p1" in reply and "p2 (2 times)" in reply
    assert ed.edited() == {} and ed.refused == 1
    assert ed("edit", {"old": "Ryujiro", "new": "Ryūjirō", "reason": "", "replace_all": True}) == "Done: 3 replaced, in p1, p2."
    assert ed.edited()[("p2",)]["english"] == "Ryūjirō and Ryūjirō laughed."
    assert ed("edit", {"old": "nowhere", "new": "x", "reason": "", "replace_all": False}).startswith("Error: not found")


def test_an_edit_never_crosses_a_paragraph_or_touches_a_locked_line():
    ed = editor({("p1",): "the end.", ("p2",): "The start."}, locked=["p2"])
    assert ed("edit", {"old": "end. The", "new": "x", "reason": "", "replace_all": False}).startswith("Error: not found")
    assert "locked" in ed("edit", {"old": "start", "new": "beginning", "reason": "", "replace_all": False})
    assert ed("find", {"words": "end"}).startswith("1 times: p1")


def test_an_edit_outside_the_part_it_was_given_is_not_found():
    conn = SimpleNamespace(execute=lambda *a: [])
    ed = Editor(SimpleNamespace(conn=conn, work_id="w"), {("p1",): "inside", ("p9",): "outside"}, {"p1"})
    assert ed("edit", {"old": "outside", "new": "x", "reason": "", "replace_all": False}).startswith("Error: not found")


def test_findings_go_back_to_every_earlier_chapter_once():
    from types import SimpleNamespace as P

    from house.stages.desk import to_take_back
    chapters = [[P(id="p1"), P(id="p2")], [P(id="p3")], [P(id="p4"), P(id="p5")]]
    found = [{"segment_id": "p4", "reason": "she is his sister"}, {"segment_id": "p3", "reason": "the word means wine"}]
    back = to_take_back(chapters, found)
    assert [(i, [q["segment_id"] for q in qs]) for i, qs in back] == [(0, ["p4", "p3"]), (1, ["p4"])]
    assert to_take_back(chapters, [{"segment_id": "p1", "reason": "found in the first chapter"}]) == []
