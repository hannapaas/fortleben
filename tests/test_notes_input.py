"""The notes stage sees the road not taken: for its part, the readers' notes the desk declined and the
disagreements it recorded, as plain lines after the part itself; nothing of the kind, no block."""

import json

import pytest

from house.db import connect
from house.stages.notes import ROAD, road_not_taken


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "notes.db")
    c.execute("INSERT INTO work (id, title, author) VALUES ('w', '晩餐', '素木しづ')")
    c.execute("INSERT INTO run (id, work_id) VALUES (1, 'w')")
    query = ("INSERT INTO query (run_id, work_id, segment_id, span, raised_by, owner, category, reason, recommendation, "
             "status, answer) VALUES (1, 'w', ?, ?, ?, 'desk', 'flow', ?, ?, ?, ?)")
    c.execute(query, ("p3", "a quiet, lonely heart", "reader/readable", "Dictionary English.", "a lonely heart",
                      "declined", json.dumps({"note": "R1", "reason": "Declined: the Japanese piles the words up itself."})))
    c.execute(query, ("p3", "the potato", "reader/faithful", "Too plain.", None, "taken", json.dumps({"note": "F1", "reason": "Changed."})))
    c.execute(query, ("p9", "far away", "reader/faithful", "In the next part.", None, "declined", json.dumps({"note": "F2", "reason": "No."})))
    event = "INSERT INTO event (run_id, seq, actor, type, payload) VALUES (1, ?, 'desk', ?, ?)"
    c.execute(event, (1, "disagreement.recorded", json.dumps(
        {"notes": ["F3", "R2"], "paragraph": "p2–p3", "faithful_side": "Her hand is the mother's.",
         "readable_side": "It reads as the child's.", "choice": "Kept “her”.", "send_up": False})))
    c.execute(event, (2, "query.raised", json.dumps({"paragraph": "p2"})))
    c.commit()
    return c


def test_the_block_lists_the_declined_note_and_the_disagreement_in_the_part(conn):
    block = road_not_taken(conn, 1, ["p1", "p2", "p3"])
    assert block.startswith(f"## {ROAD}")
    lines = [line for line in block.splitlines() if line.startswith("- ")]
    assert len(lines) == 2
    disagreement, declined = lines  # in paragraph order: the group p2–p3 comes before p3
    assert disagreement.startswith("- p2–p3: the readers disagreed.")
    assert "Her hand is the mother's." in disagreement and "It reads as the child's." in disagreement
    assert "Chosen: Kept “her”." in disagreement
    assert declined.startswith("- p3, on “a quiet, lonely heart”: a reader of the English alone raised: Dictionary English.")
    assert "Suggested: “a lonely heart”" in declined
    assert declined.endswith("Declined: the Japanese piles the words up itself.")  # said once, not twice
    assert "Too plain." not in block  # a note the desk took is in the English already
    assert "In the next part." not in block  # another part's


def test_a_part_with_nothing_declined_or_disputed_gets_no_block(conn):
    assert road_not_taken(conn, 1, ["p4", "p5"]) == ""
    assert road_not_taken(conn, 2, ["p1", "p2", "p3"]) == ""
