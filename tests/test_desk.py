from house.stages.common import apply_edit
from house.stages.common import change_flags

OLD = "Outside the door, grown dark, a violent sound of rain and wind — a storm."


def test_a_small_change_for_its_note_is_not_flagged():
    new = "Outside the darkened door, a violent sound of rain and wind — a storm."
    assert change_flags(OLD, new) == []


def test_a_shrunken_paragraph_is_flagged():
    flags = change_flags(OLD, "A storm.")
    assert any(f.startswith("paragraph shrank") for f in flags)


def test_an_edit_matches_once_and_forgives_copied_quotation_marks():
    text = 'He said, "It\'s a storm." She nodded.'
    assert apply_edit(text, '“"It\'s a storm."”', '“"A storm."”') == 'He said, "A storm." She nodded.'
    assert apply_edit("a b a", "a", "c") is None
    assert apply_edit("abc", "x", "y") is None


def test_findings_go_back_to_every_earlier_chapter_once():
    from types import SimpleNamespace as P

    from house.stages.desk import to_take_back
    chapters = [[P(id="p1"), P(id="p2")], [P(id="p3")], [P(id="p4"), P(id="p5")]]
    found = [{"segment_id": "p4", "reason": "she is his sister"}, {"segment_id": "p3", "reason": "the word means wine"}]
    back = to_take_back(chapters, found)
    assert [(i, [q["segment_id"] for q in qs]) for i, qs in back] == [(0, ["p4", "p3"]), (1, ["p4"])]
    assert to_take_back(chapters, [{"segment_id": "p1", "reason": "found in the first chapter"}]) == []
