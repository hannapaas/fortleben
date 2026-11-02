"""Assemble what a call sees, in the order of docs/STORY-STATE.md §3: stable blocks first
(so the prefix caches), the passage last (where models attend best).

These are data blocks with plain labels, not instructions: the instructions are the prompt
files. The bible is stored as JSON and rendered here as Markdown for the model.

What a call sees of the source depends on the length of the work, and only here (STORY-STATE
§3 and §5): a short text goes in whole; a long one is cut into chapters, and a per-page call
gets its own chapter in full with the other chapters as one-line summaries, so the cost of a
call stays flat however long the book is.
"""

from house.parser import Paragraph, ParsedWork

# Up to here the whole source goes in every per-page call. Kept small on purpose: models use the middle of a
# long context worst (Liu et al. 2024; NoLiMa, Modarressi et al. 2025), so a long text gets its own part and a
# short summary of the others instead (docs/REFERENCES.md).
WHOLE_TEXT_CHARS = 15_000
MAX_PART_CHARS = 25_000  # the most one reader, desk or final-read call is given to judge at once
CHAPTER_CHARS = 4_000  # the fallback split: scene breaks merged into chapters of at least this


def block(label: str, body: str) -> str:
    return f"## {label}\n\n{body.strip()}\n"


def work_card(work: ParsedWork) -> str:
    m = work.meta
    lines = [f"{work.title} ({m.get('title_en', '')}), by {work.author} ({m.get('author_en', '')})"]
    r = m.get("rights", {})
    if r:
        lines.append(f"Author died {r.get('author_died')}; first published {r.get('first_published')}.")
    return block("The work", "\n".join(lines))


def _lines(paras: list[Paragraph]) -> str:
    out = []
    for p in paras:
        if p.scene_break_before:
            out.append("◇")
        out.append(f"{p.id}　{p.model_text.strip('　 ')}")
    return "\n".join(out)


def is_long(work: ParsedWork) -> bool:
    return sum(len(p.text) for p in work.translatable()) > WHOLE_TEXT_CHARS


def split(work: ParsedWork, starts: list[str]) -> list[list[Paragraph]]:
    out = []
    for p in work.translatable():
        if p.id in starts or not out:
            out.append([])
        out[-1].append(p)
    return out


def chapters(work: ParsedWork) -> list[list[Paragraph]]:
    """The parts the later stages work in: the planner's, where it has run (house/stages/parts.py);
    otherwise a fallback cut at headings, else at scene breaks merged until a part is CHAPTER_CHARS long."""
    paras = work.translatable()
    if work.parts:
        return split(work, work.parts)
    if any(p.kind == "heading" for p in paras):
        out, cur, size = [], [], 0
        for p in paras:
            if cur and (p.kind == "heading" or size + len(p.text) > MAX_PART_CHARS):
                out.append(cur)
                cur, size = [], 0
            cur.append(p)
            size += len(p.text)
        return out + ([cur] if cur else [])
    out, cur, size = [], [], 0
    for p in paras:
        if cur and ((p.scene_break_before and size >= CHAPTER_CHARS) or size + len(p.text) > MAX_PART_CHARS):
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += len(p.text)
    return out + ([cur] if cur else [])


def chapter_of(work: ParsedWork, pid: str) -> int:
    return next(i for i, ch in enumerate(chapters(work)) if any(p.id == pid for p in ch))


def chapter_line(ch: list[Paragraph], summaries: dict | None, i: int) -> str:
    """One line for a chapter the call doesn't see in full: the Analyst's summary if the bible has one,
    else the heading or the first words."""
    if summaries and summaries.get(str(i)):
        return summaries[str(i)]
    head = next((p for p in ch if p.kind == "heading"), ch[0])
    return head.model_text.strip("　 ")[:40]


def source_text(work: ParsedWork, around: list[Paragraph] | None = None, summaries: dict | None = None) -> str:
    """The source with paragraph IDs. Ruby is kept as base《reading》; editorial notes are dropped.

    A short work goes in whole. A long one, for a call about a page (`around`), is the page's own
    chapter in full, with every other chapter as one line (`summaries` is the bible's
    `chapter_summaries`, keyed by chapter index as a string). With no `around`, a long work still
    goes in whole: that is the whole-book reads (first read, the editor's letter, the final read).
    """
    if around is None or not is_long(work):
        return block("The whole source text, with paragraph IDs", _lines(work.translatable()))
    chs = chapters(work)
    here = chapter_of(work, around[0].id)
    out = []
    for i, ch in enumerate(chs):
        if i == here:
            out.append(f"### Chapter {i + 1} of {len(chs)}, in full ({ch[0].id}–{ch[-1].id})\n\n{_lines(ch)}")
        else:
            out.append(f"- Chapter {i + 1} ({ch[0].id}–{ch[-1].id}): {chapter_line(ch, summaries, i)}")
    return block("The source text: this chapter in full, the others in one line each", "\n".join(out))


def reading(r: dict) -> str:
    crux = "\n".join(f"- **{c['point']}** {c['why']} *For the English:* {c['for_the_english']}" for c in r["crux"])
    body = f"**The crux**\n\n{crux}\n\n{r['reading']}"
    if r.get("open_questions"):
        body += "\n\n**Open questions**\n\n" + "\n".join(f"- {q['question']}" for q in r["open_questions"])
    return block("The house's reading", body)


def cast(b: dict) -> str:
    out = []
    for c in b["cast"]:
        forms = "; ".join(f"{f['form']} ({f['used_by']}{': ' + f['note'] if f['note'] else ''})" for f in c["forms"])
        name = " ".join(x for x in (c.get("name_ja"), c.get("romanised")) if x)
        out.append(
            f"- **{c['id']} {c['handle']}**{' — ' + name if name else ''}. {c['role']}. Gender: {c['gender']}"
            f" ({c['gender_evidence']}). Forms: {forms or 'none'}. First person: {c['first_person']}."
            f" Register: {c['register']}. Relationships: {'; '.join(c['relationships']) or 'none'}."
            f" First appears {c['first_appearance']}.")
    return "### Cast\n" + "\n".join(out)


def bible(b: dict) -> str:
    parts = []
    ss = b["style_sheet"]
    parts.append("### Style sheet\n" + "\n".join(
        f"- **{k.replace('_', ' ')}:** {v if not isinstance(v, list) else '; '.join(v) or 'none'}"
        for k, v in ss.items()))
    n = b["narration"]
    parts.append("### Narration\n" + "\n".join(
        f"- **{k.replace('_', ' ')}:** {v if not isinstance(v, list) else '; '.join(v)}" for k, v in n.items()))
    parts.append(cast(b))
    if b["motifs"]:
        parts.append("### Motifs and callbacks\n" + "\n".join(
            f"- **{m['motif']}** ({', '.join(m['source_forms'])}) at {', '.join(m['occurrences'])}. {m['why']} {m['english']}"
            for m in b["motifs"]))
    if b["hard_spots"]:
        parts.append("### Hard spots\n" + "\n".join(
            f"- {', '.join(h['anchors'])} ({h['kind']}): {h['why_hard']}" for h in b["hard_spots"]))
    return block("The story bible: the house's best understanding before drafting, which can be wrong", "\n\n".join(parts))


def page(paras: list[Paragraph]) -> str:
    """The page as a translator sees it: whole paragraphs, with paragraph IDs and ruby kept, not split
    into numbered sentences (which invites a sentence-by-sentence, literal draft)."""
    return block("The page to draft", "\n\n".join(f"{p.id}　{p.model_text.strip('　 ')}" for p in paras))


def chapter_pairs(paras: list[Paragraph], units: dict[tuple, str], first: str) -> str:
    """A chapter in both languages, paragraph by paragraph; where the drafter joined paragraphs into
    a group, the group's English appears once, labelled p21–p23. `first` says which language a reader
    meets first: the whole chapter in that language, then the pairs in that order."""
    rows = []  # (label, [paragraphs], english)
    for p in paras:
        ids = next((k for k in units if p.id in k), (p.id,))
        if rows and rows[-1][0] == ids:
            rows[-1][1].append(p)
        else:
            rows.append((ids, [p], units.get(ids, "(missing)")))
    label = lambda ids: ids[0] if len(ids) == 1 else f"{ids[0]}–{ids[-1]}"  # noqa: E731
    ja = lambda ps: "\n".join(f"{p.id}　{p.model_text.strip('　 ')}" for p in ps)  # noqa: E731
    if first == "ja":
        whole = block("The chapter in Japanese", "\n".join(ja([p]) for p in paras))
        pairs = "\n\n".join(f"{ja(ps)}\n{label(ids)}　{en}" for ids, ps, en in rows)
        return whole + block("Paragraph by paragraph: the Japanese, then the house's English", pairs)
    whole = block("The chapter in the house's English", "\n\n".join(f"{label(ids)}　{en}" for ids, _, en in rows))
    pairs = "\n\n".join(f"{label(ids)}　{en}\n{ja(ps)}" for ids, ps, en in rows)
    return whole + block("Paragraph by paragraph: the house's English, then the Japanese", pairs)


def window(before: list[tuple[Paragraph, str | None]], after: Paragraph | None) -> str:
    parts = []
    if before:
        parts.append("Previous paragraphs, Japanese and the house's English:\n\n" + "\n\n".join(
            f"{p.id}　{p.model_text.strip('　 ')}\n{p.id}　{en or '(not drafted)'}" for p, en in before))
    if after is not None:
        parts.append(f"Next paragraph, Japanese only, read-only (for context; don't translate it):\n\n{after.id}　{after.model_text.strip('　 ')}")
    return block("The text either side", "\n\n".join(parts) if parts else "This is the first page and there is nothing either side yet.")


def voice_reference(english_by_id: list[tuple[str, str]] | None) -> str:
    if not english_by_id:
        return ""
    return block("The voice reference: the house's chosen first page", "\n\n".join(f"{pid}　{en}" for pid, en in english_by_id))


def join(*blocks: str) -> str:
    return "\n".join(b for b in blocks if b)
