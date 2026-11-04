"""What a per-page call sees of the source depends only on the length of the work (STORY-STATE §3)."""

from house import context, works
from house.parser import Paragraph, ParsedWork


def para(i: int, text: str, kind: str = "narration", scene_break: bool = False) -> Paragraph:
    return Paragraph(id=f"p{i}", seq=i, kind=kind, text=text, source=text, tokens=[], sentences=[],
                     scene_break_before=scene_break, model_text=text)


def work(paras) -> ParsedWork:
    return ParsedWork(title="t", author="a", head="", paragraphs=paras, lines=[], colophon="", meta={})


def test_a_short_work_goes_in_whole():
    w = work([para(1, "あ" * 100), para(2, "い" * 100)])
    out = context.source_text(w, around=[w.paragraphs[1]])
    assert "The whole source text" in out and "p1" in out and "p2" in out


def test_a_long_work_without_headings_is_cut_at_scene_breaks():
    paras = [para(i, "あ" * 1000, scene_break=(i % 3 == 0)) for i in range(1, 31)]  # 30k chars
    w = work(paras)
    chs = context.chapters(w)
    assert len(chs) > 1 and sum(len(c) for c in chs) == 30
    assert all(sum(len(p.text) for p in c) >= context.CHAPTER_CHARS for c in chs[:-1])


def test_a_long_work_shows_one_chapter_in_full_and_the_rest_in_a_line():
    paras = []
    for c, ch in enumerate("あいう"):  # three chapters of 20,000 characters: long, but each part fits
        paras += [para(len(paras) + 1, f"第{c + 1}章", kind="heading")] + [para(len(paras) + 2 + i, ch * 2000) for i in range(10)]
    w = work(paras)
    assert context.is_long(w) and len(context.chapters(w)) == 3
    out = context.source_text(w, around=[w.para("p15")], summaries={"0": "The first chapter: a dinner."})
    assert "Part 2 of 3, in full" in out
    assert "p15　" + "い" * 2000 in out
    assert "あ" * 2000 not in out  # the other chapters are a line, not the text
    assert "Part 1 (p1–p11): The first chapter: a dinner." in out
    assert "あ" * 2000 in context.source_text(w)  # whole-book reads still get everything


def test_a_chapter_too_big_for_one_reading_is_split():
    w = work([para(1, "第一章", kind="heading")] + [para(i, "あ" * 5000) for i in range(2, 14)])
    assert all(sum(len(p.text) for p in c) <= context.MAX_PART_CHARS for c in context.chapters(w))


def test_a_group_the_drafter_joined_appears_once():
    from house.stages.common import unit_of
    w = work([para(1, "あ"), para(2, "い"), para(3, "う")])
    units = {("p1",): "One.", ("p2", "p3"): "Two and three."}
    out = context.chapter_pairs(w.paragraphs, units, "en")
    assert out.count("Two and three.") == 2  # once in the whole chapter, once in the pairs
    assert "p2–p3　Two and three." in out
    assert unit_of(units, "p2-p3") == ("p2", "p3") and unit_of(units, "p3") == ("p2", "p3")
    assert unit_of(units, "p9") is None
    assert unit_of(units, "change to p1: the opening") == ("p1",)
    assert unit_of(units, "Japanese rendering of p2 - p3: ...") == ("p2", "p3")


def test_a_planned_split_is_followed_and_a_bad_one_refused():
    from house.stages.parts import check
    w = works.parse("shuchu")
    ids = [p.id for p in w.translatable()]
    assert check(w, [ids[0], ids[20], ids[40]]) is None
    w.parts = [ids[0], ids[20], ids[40]]
    assert [c[0].id for c in context.chapters(w)] == [ids[0], ids[20], ids[40]]
    assert sum(len(c) for c in context.chapters(w)) == len(ids)
    assert check(w, [ids[5]])  # doesn't start at the start
    assert check(w, [ids[0], ids[30], ids[10]])  # out of order
    assert check(w, [ids[0], "p9999"])  # no such paragraph


def test_a_second_readers_crux_is_carried_in_the_reading():
    crux = [{"point": "The narrator never judges.", "why": "Every step is even.", "for_the_english": "Keep it cool."}]
    second = [{"point": "The repetition is the piece.", "why": "Three words recur.", "for_the_english": "Keep them."}]
    out = context.reading({"crux": crux, "reading": "A page.", "open_questions": []})
    assert "second reader" not in out
    out = context.reading({"crux": crux, "reading": "A page.", "open_questions": [], "second_crux": second})
    assert "A second reader's crux" in out and "The repetition is the piece." in out
    assert out.index("never judges") < out.index("A second reader's crux")
