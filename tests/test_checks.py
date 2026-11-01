from house import checks

TERMS = {"light": {"casual": "the dark electric light", "curious": "dentō", "student": "dentō"},
         "storm": {"casual": "storm", "curious": "storm", "student": "arashi"}}


def test_ledger_flags_unknown_tokens_and_doubled_words():
    assert checks.ledger("under the {t:light}", TERMS) == ["doubled “the the” in the casual view where a token meets the text"]
    assert checks.ledger("under the dark {t:light}", TERMS)[0].startswith("doubled “the dark the dark”")
    assert checks.ledger("a {t:storm}", TERMS) == []
    assert checks.ledger("a {t:gale}", TERMS) == ["unknown ledger token {t:gale}"]


def test_stray_scripts():
    assert checks.stray_scripts("except where теплопод blocks") and not checks.stray_scripts("ジャガ芋 potato")


def test_omission_guard_uses_the_texts_own_baseline():
    ja = "あ" * 100
    pairs = {f"p{i}": (ja, "x" * 300) for i in range(6)}
    pairs["p9"] = (ja, "x" * 100)
    assert list(checks.omissions(pairs)) == ["p9"]


def test_a_token_that_starts_a_sentence_is_capitalised():
    assert checks.render('"{t:storm}." He whispered it.', TERMS) == '"Storm." He whispered it.'
    assert checks.render("Rain. {t:storm} came.", TERMS) == "Rain. Storm came."
    assert checks.render("rain and wind — a {t:storm}.", TERMS) == "rain and wind — a storm."
