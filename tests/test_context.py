"""What a per-page call sees of the source depends only on the length of the work (STORY-STATE §3)."""

from house import context
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
    paras = [para(1, "第一章", kind="heading")] + [para(i, "あ" * 1000) for i in range(2, 12)]
    paras += [para(12, "第二章", kind="heading")] + [para(i, "い" * 1000) for i in range(13, 23)]
    w = work(paras)
    out = context.source_text(w, around=[w.para("p15")], summaries={"0": "The first chapter: a dinner."})
    assert "Chapter 2 of 2, in full" in out
    assert "p15　" + "い" * 1000 in out
    assert "あ" * 1000 not in out  # the other chapter is a line, not the text
    assert "Chapter 1 (p1–p11): The first chapter: a dinner." in out
    # whole-book reads still get everything
    assert "あ" * 1000 in context.source_text(w)
