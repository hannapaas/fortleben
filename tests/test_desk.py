from house.stages.desk import change_flags

TERMS = {"storm": {"casual": "storm", "curious": "storm", "student": "storm (arashi)"}}
OLD = "Outside the door, grown dark, a violent sound of rain and wind — a {t:storm}."


def test_a_small_change_for_its_note_is_not_flagged():
    new = "Outside the darkened door, a violent sound of rain and wind — a {t:storm}."
    assert change_flags(OLD, new, [{"span": "Outside the door, grown dark"}], TERMS) == []


def test_a_dropped_token_and_a_rewrite_are_flagged():
    new = "The storm raged outside, and the family sat together in the gloom of their narrow little room."
    flags = change_flags(OLD, new, [{"span": "grown dark"}], TERMS)
    assert "ledger token {t:storm} dropped" in flags
    assert any("far larger than the notes" in f for f in flags)


def test_a_shrunken_paragraph_is_flagged():
    flags = change_flags(OLD, "A {t:storm}.", [{"span": OLD}], TERMS)
    assert any(f.startswith("paragraph shrank") for f in flags)
