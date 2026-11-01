import pytest

from house import works
from house.lang.ja import aozora

DEMO = ["bansan", "sanjusan", "warogoku", "omoide"]


@pytest.mark.parametrize("work_id", DEMO)
def test_round_trip(work_id):
    raw = works.source_path(work_id).read_text(encoding="utf-8")
    parsed = works.parse(work_id)
    assert aozora.render(parsed) == raw
    for p in parsed.paragraphs:
        assert "".join(t["raw"] for t in p.tokens) == p.source


@pytest.mark.parametrize("work_id", DEMO)
def test_ids_are_ordered_and_text_is_clean(work_id):
    parsed = works.parse(work_id)
    assert [p.id for p in parsed.paragraphs] == [f"p{i + 1}" for i in range(len(parsed.paragraphs))]
    for p in parsed.paragraphs:
        assert "［＃" not in p.text and "《" not in p.text and "｜" not in p.text
        assert p.sentences and all(s["id"].startswith(p.id + "-s") for s in p.sentences)
    assert parsed.colophon.startswith("底本：")


def test_bansan_structure():
    w = works.parse("bansan")
    assert (w.title, w.author) == ("晩餐", "素木しづ")
    p2 = w.para("p2")
    ruby = [t for t in p2.tokens if t["t"] == "ruby"]
    assert ruby[0]["reading"] == "テーブル" and aozora.plain(ruby[0]["base"]) == "卓"
    assert "卓《テーブル》" in p2.model_text and "くり〳〵" in p2.text
    # the inputter's notes are kept as notes and never reach the text
    notes = [t for p in w.paragraphs for t in p.tokens if t["t"] == "note"]
    assert len(notes) == 2 and "底本では" in notes[1]["body"]
    assert w.paragraphs[-1].kind == "imprint"
    assert w.para("p7").kind == "dialogue"
    assert sum(1 for p in w.translatable()) == len(w.paragraphs) - 1


def test_ruby_on_gaiji_base():
    w = works.parse("sanjusan")
    ruby = [t for p in w.paragraphs for t in p.tokens if t["t"] == "ruby" and t["reading"] == "どんな"]
    assert ruby and ruby[0]["base"][0]["s"] == "什" and ruby[0]["base"][1]["t"] == "gaiji"
    assert ruby[0]["base"][1]["s"] != "〓"


def test_gaiji_decoding():
    assert aozora.gaiji_char("「麾」の「毛」にかえて「公」の右上の欠けたもの、第4水準2-94-57") != "〓"
    assert aozora.gaiji_char("「火＋玉」、U+7F9E") == "羞"


def test_sentences_keep_quoted_speech_with_its_verb():
    s = aozora.split_sentences("『坊や。』と大きな声を出した、子供は叫んだ。『うま。』")
    assert s == ["『坊や。』と大きな声を出した、子供は叫んだ。", "『うま。』"]
