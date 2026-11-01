# keikaku — the stages, in order

Written 30 Oct 2026. **This is the one list the orchestrator implements.** `ARCHITECTURE.md`, `RUNNING-A-TEXT.md` and `STORY-STATE.md` explain why; this says what runs, in what order, on what, and what code enforces. When another doc and this one disagree about the order of work, this one is right until it's changed, and the change goes here first.

## Units

- **Work:** one text. **Run:** one pass of a work through the house. **Segment:** a paragraph of the source, `p12`. Sentences inside it, `p12-s3`, exist only as anchors for queries and notes.
- **The paragraph is the unit of English.** Translation returns one English string per paragraph, plus best-effort spans saying which English renders which source sentence (one to one, two to one, reordered, or absent). Nothing forces one English sentence per Japanese one; a literary translator restructures, and a sentence-locked schema would push the model back towards literalism. The parallel layout aligns paragraph to paragraph, always; the sentence spans are used only to highlight the matching stretch on tap, and where there's no clean span the whole paragraph is the match.
- **Page:** the unit of *translation*. A drafting chunk of about 1k source tokens (~650 characters) of whole paragraphs, breaking at scene breaks where possible, drafted with the source (whole, or the page's chapter: `STORY-STATE.md` §3), the reading and the bible in view. The paragraph is only where the English is *stored* and *aligned*; nothing is ever translated a paragraph at a time. The Analyst can set the **drafting grain** per text in the style sheet: page (default) or scene, for dialogue-heavy texts or texts in very short paragraphs, and where the breaks fall. Checking and notes happen per page too; queries, revisions and labels are recorded per paragraph.
- **IDs are in the prompt.** Paragraph IDs (`p47`) and sentence IDs (`p47-s2`) come from the parser, in source order, and never change. The drafting call receives its paragraphs with their IDs printed and answers keyed by the same IDs; the referent annotations use them too. Pages are an internal unit for calls and budgeting only: readers never see a page number, the reader is continuous and anchored by paragraph.
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
| 3 | **crux-check** | work | `crux-check` · Spark low, then `head-select` · Spark minimal | Spark's crux; *same / different* with a line | Spark never sees Wonder's reading. The head-select call compares the two cruxes; "different" opens the first fork. |
| 4 | **bible** | work | `analyst-bible` · Spark medium; `analyst-referents` · Spark low, one call per ~5 pages | `bible.json` v1 (cast, ledger, narration, motifs, style sheet, hard spots, referent map, tiers) | Whole source and reading in the cached prefix. Schema-validated. |
| 5 | **voice-trial** | first page | `translate-draft` × 2–3 · Spark medium (one voice take each); `source-check` · Wonder low on each; `head-select` · Spark low | the voice reference page; the alternatives, kept | |
| — | **checkpoint** | run | none | one screen for the editor: crux (and any disagreement), reading, voice trial, key bible choices, open forks | **Stop** here if an editor is assigned and hasn't switched it off. Each editor change becomes a scoped rule. With no editor: continue, and the edition says so. Everything above is "the brief", about 15% of the allowance. |
| 6 | **draft** | page by page, in order | `translate-draft` · Spark medium | English per paragraph; translator notes; marked alternatives; `{t:id}` tokens on ledger terms | Sequential, because each page sees the previous pages' English. Context per `STORY-STATE.md` §3. |
| 7 | **source-check** | page, results per paragraph | `source-check` · Wonder low | error spans → queries, or "none" | One call per page, so the critic sees the scene and a one-line paragraph never gets a call of its own. Runs behind drafting (page n checked while page n+1 drafts). Code first: omission guard (length ratio), ledger checker. |
| 8 | **second-draft** | tricky and hard paragraphs | `translate-draft` · Spark medium (the paragraph, with its page's draft as context); `head-select` · Spark low | the head's pick, or a fork (hard only) | Can run alongside 7. At a fork, each side's case is one written paragraph from its author (the drafter for a draft, the critic for an objection), so the editor and later the reader get an argument, not two bare options. |
| 9 | **answer** | open queries | `translate-answer` · Spark low | per query: accepted / stet / revised + reason; revised text | A contested answer (stet or revised) goes back through 7 on the diff. An accepted fix is closed by code once the English has changed; accepted but unchanged is re-checked. The stage reports its accept rate. |
| 10 | **editors-letter** | work | `editors-letter` · Wonder low | a short letter; amendments to the reading | After the whole draft exists. Translation answers it via 9. |
| 11 | **editorial** | scene by scene | `editorial-scene` · Spark low | span queries | English only: never sees the source text. Plain paragraphs are read, not line-edited. |
| 12 | **copy-desk** | work | code (ledger, callbacks, length, tic list); `copy-desk` · Glimmer low | mechanical fixes applied by code; everything else as queries with a suggested replacement | Glimmer proposes, never writes the base text. Glimmer is optional: without it the code checks still run. |
| 13 | **notes** | page, notes anchored per paragraph | `notes` · Spark low | notes per view with anchors | One call per page. The keikaku test: only what the sentence can't give you. |
| 14 | **fact-check** | note | `fact-check` · Spark low + web_search | verified (with sources) / killed | Every note cites or dies. Casual notes can skip this when the pool is short. Interns may be asked for from 8, 13 or 14: the head's output sets `needs_intern`, the orchestrator runs the `intern` call and re-runs the head with the report (`ARCHITECTURE.md` §5). |
| 15 | **final-read** | work | `final-read` · Wonder low | queries | The English as a whole, then against the source: seams, voice drift, crux, continuity. A second final read only if the resulting changes were large (over 10% of paragraphs). |
| 16 | **release** | work | code | editions (Casual / Curious / Student) from the base text + tokens + notes; statuses; colophon; the bible and reading published; the author file updated with this work's entries | Proof/QC is code: every paragraph present, every token resolved, every note anchored. |

Rule propagation (an editor's rule or an accepted bible amendment) is not a stage: it queues revisions (`rule-scope` · Spark minimal on candidates found by ledger and regex), which go through 9 and 7 like any other.

**The minimal pipeline** (the fallback in `BUILD-PLAN.md`) is stages 0, 2, 4, 6, 7, 9, 12 (code only), 13, 16. It must work before anything else is added.

## How pages are cut and handed over

Code, before any model is involved.

1. **The parser** turns the source file into an ordered list of paragraphs with IDs, marking scene breaks (blank lines, section numbers, Aozora's ※ and ◇ markers) and dialogue lines.
2. **The pager** (`house/pager.py`, deterministic) walks the list and builds pages: it adds whole paragraphs until the next would take the page past the target (~650 characters), preferring to close at a scene break near the limit. It never splits a paragraph; a paragraph longer than the target is a page on its own. If the style sheet sets the grain to *scene*, it closes at the Analyst's break points instead.
3. **The orchestrator** goes page by page in order, assembles the context (`STORY-STATE.md` §3) and makes one `translate-draft` call per page.
4. **The answer** is a list of items, each naming the paragraph IDs it covers (one, or a group), with the English, sentence spans, notes and alternatives. The orchestrator checks every paragraph in the page is covered exactly once (retry once, then a failure event), stores a revision per paragraph, emits events, and moves on.

The model never decides where a page starts or ends and never sees half a paragraph. The only chunking choices a model makes are the Analyst's, at bible time: the grain and the break points, which the pager obeys.

## How a debate actually runs

No agent talks to another agent. There's no shared chat, no transcript passed around, and no agent chooses who to address. A debate is a **query**: one row in the `query` table with a fixed shape, and a short sequence of separate model calls that the orchestrator makes in a fixed order. Think of a publishing house's query sheet, where each note has a line reference, a reason and a box for the answer, and the editor decides whose turn it is.

A query carries: who raised it (department and role), who owns the answer (always Translation for the English; the Analyst for the bible; Notes for a note), the span, a category, the reason, the evidence (a quote from the source, a bible entry, a rule), a recommendation, a status, the round, and a one-sentence `say` for the House.

One query, step by step:

| Step | What happens | Who | Call |
|---|---|---|---|
| 1 | Source check reads a page against the Japanese and returns a list of issues per paragraph, possibly empty; take paragraph `p12` | critic | `source-check` on the page |
| 2 | The orchestrator writes each issue as a query, `open`, round 0, and emits events | code | none |
| 3 | When a paragraph's queries are in, one call answers them all: for each, *accepted* (with the fix), *stet* (with a reason) or *revised* (with the new text) | owner | `translate-answer` on `p12` + its open queries |
| 4 | Revisions become a new revision row. If every answer was *accepted* and the English changed, code closes the queries and the letters stop here. Otherwise the orchestrator sends **the diff** and the answers back to the critic that raised the query | code, then critic | `source-check` on the changed span |
| 5 | The critic either closes (fine now) or raises once more with new evidence: round 1 | critic | same call's output |
| 6 | The owner answers again | owner | `translate-answer` |
| 7 | **Round 2 is the end.** Still open: on a hard paragraph it becomes a fork for the editor, each side's case in a paragraph; otherwise the head picks (`head-select`) and the paragraph is labelled *head's pick, unresolved* | code, head | `head-select` |

Every call sees only its own inputs: the paragraph, the queries addressed to it, the bible, the reading and the rules. The critic never sees the owner's reasoning except the written answer; the owner never sees the critic's beyond the written query. That's the "letters" picture, and it's deliberate: written, specific, with evidence, and short.

**Why it can't explode.** The routing graph is fixed and acyclic apart from two bounded loops:
- the query loop (critic → owner → critic → owner), capped at two rounds;
- the revision loop (any change to the English goes back through Source check), capped at three revision cycles per paragraph per run.

Editorial, the editor's letter and the final read each raise queries into the same mechanism but never receive queries back, so nothing cycles between departments. Interns report to a head and raise nothing. Forks stop at the editor. A critic may always answer "none", and schemas limit how many issues one call can raise (eight per paragraph). On top sit the pool of drops and the spend caps: when they run low the house stops resolving and starts labelling (`RUNNING-A-TEXT.md` §5). Nothing in this section is asked of the prompts; it's all the orchestrator.

## What code enforces, whatever the prompts say

| Limit | Value | Where |
|---|---|---|
| Rounds per query | 2, then a fork (hard) or the head's pick stands, labelled | orchestrator |
| Revision cycles per paragraph | 3 per run; after that it's *flagged, unresolved* | orchestrator |
| Forks per checkpoint | 5, global first | orchestrator |
| Interns | one level; 3 per run; $0.10 per department per run; reports, never edits; a head asks via its output, never by a tool call | orchestrator |
| Drops of ink | 100 per sheet; when it's gone the house flags instead of resolving, in the order in `RUNNING-A-TEXT.md` §5 | budget module |
| Spend caps | pre-call estimate against live-run / daily / total caps; kill switch | budget module |
| Output shape | strict JSON schema per prompt; a call that fails validation is retried once, then the stage records a failure event and moves on | model client |
| Locked lines | never rewritten by a rule or a revision; a query to the editor instead | orchestrator |
| Tier changes | up any time; down only with a logged reason | orchestrator |
| Source check | never skipped by the budget | budget module |
| Source in a per-page call | the whole text up to 15k characters; above that, the page's chapter in full and the other chapters in one line each | context module |

## Stop and resume

What the editor sees of this, and what's published at each point, is `EDITORS-DESK.md`.

Every stage writes its outputs to the database before the next starts, so a run can stop after any stage and resume from the record. The response cache (model, prompt hash, input hash) makes a resumed or repeated stage free. Development uses stops after every stage; production stops only at the checkpoint.
