# keikaku — the prompts we need

Written 30 Oct 2026. Every model call in the house, what it's for, and when it's needed. The order they run in is `STAGES.md`. **All written (1 Nov), in `prompts/`**, one file per row below, in the shape described here. They are first drafts: each gets tuned against real output on 「晩餐」, and the examples are the parts most likely to change. Each lives in `prompts/<name>.md` with its JSON schema next to it in `schemas/`.

## How each prompt is written

Following ARCHITECTURE §3 ("prompts teach principles; code enforces limits"):
- **What the job is for and why**, in a few paragraphs, as you'd brief a new colleague. Not a list of rules.
- **One or two contrasting examples** of good output, from very different texts, so the model learns the judgement rather than copying a shape.
- **What it gets and what it returns.** The schema does the policing; the prompt doesn't repeat it.
- **No limits the orchestrator enforces** (budget, rounds, locks, schema). Those live in code.
- Short. If a prompt keeps growing, the job is probably two jobs.

Everything shares one **house brief** (below), which sits first in every cached prefix.

## Shared

| Prompt | What it teaches |
|---|---|
| **house-brief** | What keikaku is for: a window, not a rewrite; fidelity first, and plain good English; honest about doubt; queries, not silent changes; the crux comes first; Berman's deforming tendencies as shared vocabulary (`FROM-TRANSLATORS.md`). Every department reads it. |

## Before translation

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **background-brief** | Spark low + web search (as an intern) | Read around the text: author's life, period, reception, allusions | A page of notes with sources |
| **first-read** | Wonder medium | Read the whole text and write the house's reading, starting from the crux | Prose reading; open questions; two or three voice takes the reading allows |
| **crux-check** | Spark | Read the whole text independently, without Wonder's reading, and say what a translation of it stands or falls on | A short answer with reasons. A `head-select` call then says whether the two cruxes are the same; if not, it's the first fork |
| **analyst-bible** | Spark | Build the story bible from the text and the reading: cast, ledger, narration, motifs, style sheet, hard spots | Bible JSON |
| **analyst-referents** | Spark | Per section: speakers, implicit subjects, confidence, deliberate ambiguity, and each paragraph's tier | Referent-map JSON + tiers |
| **analyst-amend** | Spark | Rule on a proposed bible amendment (a missed echo, a better rendering) | Accept / reject with reason; the patch |

## Translation

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **translate-draft** | Spark medium | Draft a page in order, in the chosen voice. Also used for the voice trial, given one voice take, and for second drafts of a single paragraph | English per paragraph with best-effort sentence spans; `{t:id}` tokens on ledger terms; translator notes; marked alternatives |
| **translate-answer** | Spark | Answer queries, and the editor's letter: accept, stet with a reason, or revise | Per query: status, reason, revised text |
| **head-select** | Spark | A department head choosing between drafts or options, or opening a fork: one-line trade-offs, each side's case in a paragraph by its author, dissent quoted | Pick + reason, or a fork |

## Checking and revising

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **source-check** | Wonder low | Read the English against the Japanese: omissions, additions, wrong speaker, misread tone, the crux slipping. Answer "none" when there's nothing | Error spans + queries with evidence |
| **editors-letter** | Wonder | Read the whole English draft against the reading, as an editor reads a manuscript | A short letter of big-picture notes |
| **editorial-scene** | Spark | Read a scene of English alone, as a reader: voice, rhythm, clarity, deformations | Span queries |
| **copy-desk** | Glimmer | Style sheet, ledger, anachronisms, consistency | Queries |
| **notes** | Spark | Write notes for each edition (Casual / Curious / Student), passing the keikaku test: only what the sentence can't give you | Notes with anchors and sources |
| **fact-check** | Spark + web search | Verify, cite or kill each note | Verdict + sources |
| **final-read** | Wonder | Read the finished English as a whole, as a reader, then against the source: seams, voice drift, the crux, continuity | Queries |
| **rule-scope** | Spark low | Does this segment fall under this standing rule? | Yes / no / ask the editor |
| **intern** | Spark low + web search | Answer one research question a head asked | A report, never edits |

## The editor and readers

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **editor-note-to-rule** | Spark | Turn the editor's typed note into a scoped standing rule or a ruling on a fork | Rule + scope, or a decision |
| **reader-proposal** | Glimmer | Screen a reader's comment or proposed fix (spam, abuse, off-topic) and turn a proposal into a query | Pass / fail with the reason shown to the author; the query |
| **reader-report** | Spark | Catalogue reader's report on an untranslated work | Report fields |
| **acquisitions-rights** | Spark + web search | A requested work: author's death year, first publication, existing translations | *Eligible / in copyright / can't tell* + evidence |
| **cover** | `muse-image` | A cover from the reading's imagery and the house design | An image prompt template, not an agent |

## The exhibit

| Prompt | Model | Job |
|---|---|---|
| **baseline-oneshot** (S0) | Spark | Deliberately bare: "translate this into English". The control |
| **audit-spans** | Wonder, cross-checked by Spark Open | Blind read of any translation against the source, with the reading and bible: every problem marked with a one-line reason in plain words (name translated, wrong referent, missing sentence, anachronism, model tic, flat tone, varied repetition) |
| **exhibit-notes** | Wonder | For the side-by-side exhibit: plain-words margin notes an engineer with no Japanese can follow |

## When each is needed

| Milestone | Prompts |
|---|---|
| **M2a** (engine runs 晩餐 end to end) | house-brief, first-read, analyst-bible, analyst-referents, translate-draft, translate-answer, source-check, baseline-oneshot |
| **M3** (full pipeline) | crux-check, head-select, editors-letter, editorial-scene, copy-desk, notes, fact-check, final-read, analyst-amend, rule-scope, intern, background-brief |
| **M5** (showcase with the editor) | editor-note-to-rule |
| **M2e / M7** (site) | reader-proposal, reader-report, acquisitions-rights, cover |
| **M6** (the exhibit) | audit-spans, exhibit-notes |

It sounds a lot, but most are short, and seven are enough to run a text end to end.

## Examples the prompts need

The examples matter more than the wording. The ones that need the most care:
- **first-read:** two example readings of very different texts, each built on its own crux. These teach the most and set the tone for everything downstream. They also risk anchoring: if the reading of 「晩餐」 on the first run echoes either example, the examples come out and the prompt relies on description alone.
- **source-check:** a real wrong-speaker error, a real omission, and a clean page answered "none".
- **editors-letter:** one short letter on a draft that's accurate and still wrong as a whole.
