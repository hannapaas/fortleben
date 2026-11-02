# keikaku — the prompts we need

Written 30 Oct 2026. Every model call in the house, what it's for, and whether it runs yet. The order they run in is `STAGES.md`. **All written, in `prompts/`**, one file per row below, in the shape described here, tuned against real output on 「晩餐」 (`experiments/`). Each lives in `prompts/<name>.md`, with its JSON schema in `house/schemas/<name>.json` where it has one (the two drafting prompts share `translate-draft.json`).

## How each prompt is written

Following ARCHITECTURE §3 ("prompts teach principles; code enforces limits"):
- **What the job is for and why**, in a few paragraphs, as you'd brief a new colleague. Not a list of rules.
- **One or two contrasting examples** of good output, from very different texts, so the model learns the judgement rather than copying a shape.
- **What it gets and what it returns.** The schema does the policing; the prompt doesn't repeat it.
- **No limits the orchestrator enforces** (budget, note caps, locks, schema). Those live in code.
- Short. If a prompt keeps growing, the job is probably two jobs.

Everything shares one **house brief** (below), which sits first in every cached prefix.

## Shared

| Prompt | What it teaches |
|---|---|
| **house-brief** | What keikaku is for: a window, not a rewrite; fidelity first, and plain good English; honest about doubt; queries, not silent changes; the crux comes first; Berman's deforming tendencies as shared vocabulary (`FROM-TRANSLATORS.md`). Every department reads it. |

## Before translation

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **background-brief** | Spark low + web search | Read around the text: author's life, period, reception, allusions. Not called yet | A page of notes with sources |
| **parts** | Spark low | See the book's shape (each paragraph's ID, length, kind, first words) and divide it into parts the readers, the desk and the final read can each judge whole | Where each part starts; why |
| **first-read** | Wonder medium | Read the whole text and write the house's reading, starting from the crux | Prose reading; open questions; up to three voice takes the reading allows |
| **crux-check** | Wonder low | Read the whole text independently, without the first reading, and say what a translation of it stands or falls on | A short answer with reasons. A `head-select` call then says whether the two cruxes are the same; if not, it's the first fork |
| **analyst-bible** | Spark medium | Build the story bible from the text and the reading: cast, narration, motifs, style sheet, hard spots | Bible JSON |
| **analyst-amend** | Spark | Rule on a proposed bible amendment (a missed echo, a better rendering). Not called yet | Accept / reject with reason; the patch |

## Translation

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **translate-draft-plain** | Spark medium by default (a run option) | The default drafter: draft a page in order as English a good writer would have written, in the book's voice, leaving fidelity to be restored by the readers and the desk (`experiments/05-plain-first-draft.md`) | English per paragraph or group; translator's notes; flags |
| **translate-draft** | Spark medium by default (a run option) | The faithful-first alternative (`--draft-prompt translate-draft`). Same job and the same schema | The same |
| **head-select** | Wonder low | A department head choosing between options or opening a fork: one-line trade-offs, each side's case in its author's words. Used by the crux check | Pick + reason, or a fork |

## Checking and revising

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **reader-faithful** | Spark by default, or Wonder | Read a part for the author's side: what her language does that the English doesn't. Margin notes, or none | Notes: span, what's wrong, the Japanese, a suggested wording where one is clear (a sentence or a whole passage if that's what it takes), how sure |
| **reader-readable** | Spark by default, or Wonder | Read a part for the English reader's side: is it prose a good writer would sign. Margin notes, or none | Notes, same shape |
| **desk** | Wonder by default, or Spark | The only call that writes after the draft: weigh both readers' notes and the translator's against the reading, change what needs changing, decline with reasons, record disagreements, say what changes an earlier part | Span edits (exact words in the English → replacement), each with the notes it answers and a reason; declined notes; disagreements, sent up or not; findings beyond this part |
| **final-read** | Spark by default, or Wonder | Read the finished English as a whole, as a reader, then against the source: seams, voice drift, the crux, continuity, a word an edit doubled | Small fixes as exact edits; notes for the editor, only for real judgement calls; a short verdict |
| **notes** | Spark low | Write notes for each edition (Casual / Curious / Student), passing the keikaku test: only what the sentence can't give you | Notes with anchors and sources |
| **editors-letter** | Wonder | Read the whole English draft against the reading, as an editor reads a manuscript. Not called yet | A short letter of big-picture notes |
| **copy-desk** | Glimmer | Style sheet, anachronisms, consistency. Not called yet: the copy desk is code only | Queries |
| **fact-check** | Spark + web search | Verify, cite or kill each note. Not called yet | Verdict + sources |
| **rule-scope** | Spark low | Does this segment fall under this standing rule? Not called yet | Yes / no / ask the editor |
| **intern** | Spark low + web search | Answer one research question a head asked. Not called yet | A report, never edits |

Retired on 2 Nov and gone from `prompts/`: `translate-answer` (the desk decides; nobody answers), `source-check` (replaced by the two readers), `analyst-referents` (the referent map was dropped), `editorial-scene` (folded into `reader-readable`). `translate-readthrough` was tried in experiment 3 and dropped.

## The editor and readers

None of these is called yet: they belong to the site.

| Prompt | Model | Job | Returns |
|---|---|---|---|
| **editor-note-to-rule** | Spark | Turn the editor's typed note into a scoped standing rule or a ruling on a fork | Rule + scope, or a decision |
| **reader-proposal** | Glimmer | Screen a reader's comment or proposed fix (spam, abuse, off-topic) and turn a proposal into a query | Pass / fail with the reason shown to the author; the query |
| **reader-report** | Spark | Catalogue reader's report on an untranslated work | Report fields |
| **acquisitions-rights** | Spark + web search | A requested work: author's death year, first publication, existing translations | *Eligible / in copyright / can't tell* + evidence |
| **cover** | `muse-image` | A cover from the reading's imagery and the house design | An image prompt template, not an agent |

## The exhibit and the experiments

Called by `keikaku audit` (`house/audit.py`). Each version of a text goes to the audits on its own, unlabelled, with the same reading and bible.

| Prompt | Model | Job |
|---|---|---|
| **baseline-oneshot** (S0) | Spark medium | Deliberately bare: "translate this into English". The control. Only its "Sent to the model" section is sent, with no house brief |
| **audit-spans** | Wonder medium, strict | Blind read of any translation against the source, with the reading and bible: every fidelity problem marked with a one-line reason in plain words (name translated, wrong referent, missing sentence, anachronism, model habit, flat tone, varied repetition) and a severity |
| **audit-readable** | Wonder medium, strict | Blind read of one English version for translationese: every span a literary editor would mark as reading like a translation, minor or serious, checked against the Japanese so the author's own strangeness isn't marked |
| **exhibit-notes** | Wonder | For the side-by-side exhibit: plain-words margin notes an engineer with no Japanese can follow. Not called yet |

## What runs today

Thirteen prompts run a text end to end: house-brief, parts, first-read, crux-check, head-select, analyst-bible, translate-draft-plain (or translate-draft), reader-faithful, reader-readable, desk, final-read, notes. The experiments add baseline-oneshot, audit-spans and audit-readable. The rest wait for the stages and the site that need them (`STAGES.md`, "Not built").

## Examples the prompts need

The examples matter more than the wording. The ones that need the most care:
- **first-read:** two example readings of very different texts, each built on its own crux. These teach the most and set the tone for everything downstream. They also risk anchoring: if the reading of 「晩餐」 on the first run echoes either example, the examples come out and the prompt relies on description alone.
- **editors-letter:** one short letter on a draft that's accurate and still wrong as a whole.
