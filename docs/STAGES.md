# keikaku — the stages, in order

Written 30 Oct 2026. **This is the one list the orchestrator implements.** `ARCHITECTURE.md`, `RUNNING-A-TEXT.md` and `STORY-STATE.md` explain why; this says what runs, in what order, on what, and what code enforces. When another doc and this one disagree about the order of work, this one is right until it's changed, and the change goes here first.

## Units

- **Work:** one text. **Run:** one pass of a work through the house. **Segment:** a paragraph of the source, `p12`. Sentences inside it, `p12-s3`, exist only as anchors for queries and notes.
- **The paragraph is the unit of English.** Translation returns one English string per paragraph, plus best-effort spans saying which English renders which source sentence (one to one, two to one, reordered, or absent). Nothing forces one English sentence per Japanese one; a literary translator restructures, and a sentence-locked schema would push the model back towards literalism. The parallel layout aligns paragraph to paragraph, always; the sentence spans are used only to highlight the matching stretch on tap, and where there's no clean span the whole paragraph is the match.
- **Page:** the unit of *translation*. A drafting chunk of about 1k source tokens (~650 characters) of whole paragraphs, breaking at scene breaks where possible, drafted with the source (whole, or the page's chapter: `STORY-STATE.md` §3), the reading and the bible in view. The paragraph is only where the English is *stored* and *aligned*; nothing is ever translated a paragraph at a time. The Analyst can set the **drafting grain** per text in the style sheet: page (default) or scene, for dialogue-heavy texts or texts in very short paragraphs, and where the breaks fall. Checking and notes happen per page too; queries, revisions and labels are recorded per paragraph.
- **IDs are in the prompt.** Paragraph IDs (`p47`) and sentence IDs (`p47-s2`) come from the parser, in source order, and never change. The drafting call receives its paragraphs with their IDs printed and answers keyed by the same IDs; the readers' notes and the desk's changes use them too. Pages are an internal unit for calls and budgeting only: readers never see a page number, the reader is continuous and anchored by paragraph.
- **Groups.** When the English wants two short source paragraphs as one, or one long one split, the drafter returns the English against a group of paragraphs and says so; alignment is group to group for that stretch. Rare, and logged.
- **What a paragraph is** is decided by the parser from the source (line breaks, the indent mark, dialogue lines on their own line), deterministically, before any model sees the text. A dialogue line is a paragraph.
- **Tier:** every paragraph is *plain*, *tricky* or *hard* (`RUNNING-A-TEXT.md` §2).

## The stages

Each stage is a module `house/stages/<name>.py` with `run(ctx) -> events`. The orchestrator may pause and resume between any two stages; in production it stops only at the checkpoint.

| # | Stage | Scope | Calls (prompt · model) | Produces | Notes |
|---|---|---|---|---|---|
| 0 | **parse** | work | code | segments with ruby, emphasis, scene breaks, colophon, rights record | Deterministic. Round-trip tested. |
| 1 | **background** | work | `background-brief` · Spark low + web_search | a page of notes with sources | A fixed stage, not an intern; doesn't count against intern caps. |
| 2 | **first-read** | work | `first-read` · Wonder medium | the house's reading; open questions; 2–3 voice takes | Whole source in one call. Gets the author file (`STORY-STATE.md` §1a) if the house has one, as information to weigh, not instructions. |
| 3 | **crux-check** | work | `crux-check` · Wonder low, then `head-select` · Wonder low | a second reader's crux; *same / different* with a line | The second reader never sees the first reading; it's a separate call with a different prompt, which matters more than a different model. The head-select call compares the two cruxes; "different" opens the first fork. About $0.04 on 「晩餐」, once per text. |
| 4 | **bible** | work | `analyst-bible` · Spark medium | `bible.json` v1 (cast, ledger, narration, motifs, style sheet, hard spots) | Whole source and reading in the cached prefix. Schema-validated. No referent map since 2 Nov: who speaks and acts in a sentence is worked out by whoever reads it (`STORY-STATE.md` §6). |
| 5 | **voice-trial** | first page | `translate-draft` × 2–3 (one voice take each); the readers on each; `head-select` · Spark low | the voice reference page; the alternatives, kept | |
| — | **checkpoint** | run | none | one screen for the editor: crux (and any disagreement), reading, voice trial, key bible choices, open forks | **Stop** here if an editor is assigned and hasn't switched it off. Each editor change becomes a scoped rule. With no editor: continue, and the edition says so. Everything above is "the brief", about 15% of the allowance. |
| 6 | **draft** | page by page, in order | `translate-draft` · Spark or Wonder (a run option), medium | English per paragraph; translator notes; flags; `{t:id}` tokens on ledger terms | Sequential, because each page sees the previous pages' English. Context per `STORY-STATE.md` §3. Sentence spans, if wanted, are computed later. |
| 7 | **readers** | chapter | `reader-faithful` and `reader-readable` · Spark or Wonder (a run option), medium | margin notes, at most eight per reader per chapter, or none | Two readers, independent: neither sees the other, nor the translator's notes. The faithful reader holds the author's side and meets the Japanese first; the readable reader holds the English reader's side and meets the English first. Each gets the reading, the cast and ledger, and the chapter in both languages. A note is a span, what's wrong, the Japanese quoted, a wording only if one is obvious, and how sure, in words. |
| 8 | **desk** | chapter | `desk` · Spark or Wonder (a run option), medium | its edits, each an exact span of the English and its replacement, with the notes it answers and a reason; the notes it declined and why; the disagreements, each sent up or not | The only call that writes after the draft. Never called for a chapter with no notes. Code checks every changed paragraph and accounts for every note (below). |
| 10 | **editors-letter** | work | `editors-letter` · Wonder low | a short letter; amendments to the reading | After the whole draft exists. The desk acts on it. Not built yet. |
| 11 | **editorial** | — | — | — | Folded into stage 7 on 2 Nov: the readable reader does this job, with the Japanese to hand. |
| 12 | **copy-desk** | work | code (ledger, callbacks, length, tic list); `copy-desk` · Glimmer low | mechanical fixes applied by code; everything else as queries with a suggested replacement | Glimmer proposes, never writes the base text. Glimmer is optional: without it the code checks still run. |
| 13 | **notes** | page, notes anchored per paragraph | `notes` · Spark low | notes per view with anchors | One call per page. The keikaku test: only what the sentence can't give you. |
| 14 | **fact-check** | note | `fact-check` · Spark low + web_search | verified (with sources) / killed | Every note cites or dies. Casual notes can skip this when the pool is short. Interns may be asked for from 8, 13 or 14: the head's output sets `needs_intern`, the orchestrator runs the `intern` call and re-runs the head with the report (`ARCHITECTURE.md` §5). |
| 15 | **final-read** | work | `final-read` · Wonder low | queries | The English as a whole, then against the source: seams, voice drift, crux, continuity. A second final read only if the resulting changes were large (over 10% of paragraphs). |
| 16 | **release** | work | code | editions (Casual / Curious / Student) from the base text + tokens + notes; statuses; colophon; the bible and reading published; the author file updated with this work's entries | Proof/QC is code: every paragraph present, every token resolved, every note anchored. |

Rule propagation (an editor's rule or an accepted bible amendment) is not a stage: it queues revisions (`rule-scope` · Spark minimal on candidates found by ledger and regex), which go to the desk like any other change.

**The pipeline as built** (2 Nov) is stages 0, 2, 3, 4, 6, 7, 8, 12 (code only), 13, 16. The final read (15) comes next.

## How pages are cut and handed over

Code, before any model is involved.

1. **The parser** turns the source file into an ordered list of paragraphs with IDs, marking scene breaks (blank lines, section numbers, Aozora's ※ and ◇ markers) and dialogue lines.
2. **The pager** (`house/pager.py`, deterministic) walks the list and builds pages: it adds whole paragraphs until the next would take the page past the target (~650 characters), preferring to close at a scene break near the limit. It never splits a paragraph; a paragraph longer than the target is a page on its own. If the style sheet sets the grain to *scene*, it closes at the Analyst's break points instead.
3. **The orchestrator** goes page by page in order, assembles the context (`STORY-STATE.md` §3) and makes one `translate-draft` call per page.
4. **The answer** is a list of items, each naming the paragraph IDs it covers (one, or a group), with the English, translator notes and flags. The orchestrator checks every paragraph in the page is covered exactly once (retry once, then a failure event), stores a revision per paragraph, emits events, and moves on.

The model never decides where a page starts or ends and never sees half a paragraph. The only chunking choices a model makes are the Analyst's, at bible time: the grain and the break points, which the pager obeys.

## How the readers and the desk work

No agent talks to another agent. There's no shared chat, no transcript passed around, and no agent chooses who to address. Think of a publishing house where two readers mark up a chapter in the margin, separately, and one desk editor goes through both sets of notes and decides.

| Step | What happens | Who | Call |
|---|---|---|---|
| 1 | The translator drafts the chapter's pages, in order | translator | `translate-draft` per page |
| 2 | The faithful reader and the readable reader each read the chapter, independently, and leave notes or none | readers | `reader-faithful`, `reader-readable` per chapter |
| 3 | The orchestrator stores each note as a row in the `query` table, owned by the desk, and numbers them per chapter (F1… and R1…) | code | none |
| 4 | If there are notes, the desk weighs them against the reading and returns only its edits (exact span → replacement), with the notes each change answers, the notes it declined and why, and every place the readers pulled opposite ways | desk | `desk` per chapter |
| 5 | Code applies each edit, refusing one whose span isn't in the English, then checks each changed paragraph (ledger tokens kept, no stray script, not shrunk, not rewritten far beyond its notes), refuses changes to locked lines, marks each note *taken*, *declined* or *forked*, and flags any the desk didn't address. Disagreements are recorded beside the line; the ones the desk sends up become forks for the editor | code | none |

That's all: no answer from the translator, no re-check, no rounds. The margin for a paragraph is the readers' notes and the desk's reasons, with the revision they caused. The final read is the whole-text check on what the desk changed.

**Why it can't explode.** The graph is a straight line per chapter: draft, two readers, desk. Nothing loops. Schemas cap each reader at eight notes a chapter; a reader may always answer "none"; a chapter with no notes skips the desk. On top sit the pool of drops and the spend caps. Nothing in this section is asked of the prompts; it's all the orchestrator.

## What code enforces, whatever the prompts say

| Limit | Value | Where |
|---|---|---|
| Notes per reader | 8 per chapter, or none | schema |
| Who writes after the draft | the desk only; a chapter with no notes isn't sent | orchestrator |
| Every note accounted for | taken, declined or forked; otherwise flagged *unaddressed* | orchestrator |
| A desk change | checked for dropped ledger tokens, stray scripts, shrinking, and a change far larger than its notes; flagged, not blocked | orchestrator |
| Forks | 5 per run from the desk, plus the crux fork | orchestrator |
| Interns | one level; 3 per run; $0.10 per department per run; reports, never edits; a head asks via its output, never by a tool call | orchestrator |
| Drops of ink | 100 per sheet; when it's gone the house flags instead of resolving, in the order in `RUNNING-A-TEXT.md` §5 | budget module |
| Spend caps | pre-call estimate against live-run / daily / total caps; kill switch | budget module |
| Output shape | a JSON schema per prompt, sent non-strict (strict mode gets no prompt-cache hits) and validated by the client; a call that fails validation is retried once, then the stage records a failure event | model client |
| Locked lines | never rewritten by a rule or the desk; refused and flagged | orchestrator |
| The readers | never skipped by the budget | budget module |
| Source in a per-page call | the whole text up to 15k characters; above that, the page's chapter in full and the other chapters in one line each | context module |

## Stop and resume

What the editor sees of this, and what's published at each point, is `EDITORS-DESK.md`.

Every stage writes its outputs to the database before the next starts, so a run can stop after any stage and resume from the record. The response cache (model, prompt hash, input hash) makes a resumed or repeated stage free. Development uses stops after every stage; production stops only at the checkpoint.
