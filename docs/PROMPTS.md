# Notes on the prompts

Every model call in the house uses one file from `prompts/`. The instructions sent are always the house brief, then that file (`house/client.py`, `instructions`); nothing in `house/` contains prompt text. Where a prompt has a schema it's `house/schemas/<name>.json` (both drafting prompts share `translate-draft.json`), and the answer is validated against it. The order the stages run in is in `STAGES.md`.

Two things hold for every call:
- **Every schema has a `say` field**: one sentence for the House log. An answer whose sentence isn't a sentence is treated as broken, never used and never cached.
- **Wonder calls use strict decoding** unless a call says otherwise; Spark calls don't, except where noted. If Wonder's answer fails the schema twice, the same call is made once more on Spark and the log says so.

"Run option" means the model can be switched per run, between Spark and Wonder: `--draft-model`, `--reader-model`, `--desk-model` and `--final-model` on `keikaku run`; the copy desk's model is the `copy_model` option. Defaults are in `house/stages/common.py` (`DEFAULTS`).

## The prompts the house calls

| Prompt | Called by | Model, effort | What it's for | Returns |
|---|---|---|---|---|
| **house-brief** | Every call except the one-shot baseline (`house/client.py`) | — | What the house is for: a window, not a rewrite; fidelity first, in plain good English; honest about doubt; queries, not silent changes; the crux first; Berman's deforming tendencies as a shared vocabulary (`FROM-TRANSLATORS.md`) | Nothing: it's the first part of every other prompt |
| **work-card** | Adding a work from an Aozora link (`house/acquire.py`, `describe`) | Spark, low | From the title, the author and the opening: the romanised author (surname first), an English title and one sentence for the list of works | Author, title, blurb |
| **parts** | Stage `parts` (`house/stages/parts.py`) | Spark, low | See the book's shape (each paragraph's ID, length, kind and first words, not its text) and divide it into parts the readers, the desk and the final read can each judge whole. Code checks the answer covers the book once, in order, and falls back to the book's own divisions if it doesn't | Where each part starts; why |
| **first-read** | Stage `first-read` (`house/stages/first_read.py`) | Wonder, medium | Read the whole text and write the house's reading, starting from the crux. Every later call carries it, and it's published with the edition as the house's view | The crux; the reading; open questions; the voice takes the reading allows |
| **crux-check** | Stage `crux-check` (`house/stages/crux_check.py`) | Wonder, low | Read the whole text without the first reading and say what a translation of it stands or falls on | The crux, how sure, what would change its mind |
| **head-select** | Stage `crux-check`, after the second reading | Wonder, low | A department head with options in front of it: here, whether the two cruxes name the same thing. Heads pick, never merge. If they differ, the second crux is added to the reading, marked as a second reader's, and a fork opens for the editor with each side's case in its own words | Pick or fork; same or different; the reason; the fork's question and one-line trade-offs |
| **analyst-bible** | Stage `bible` (`house/stages/bible.py`) | Spark, medium | The story bible from the text and the reading: cast, narration, deliberate repetitions, the style sheet, hard spots, a summary of each part | Bible JSON |
| **translate-draft-plain** | Stage `draft` (`house/stages/draft.py`), page by page; also the checkpoint's first page in each voice (`house/stages/checkpoint.py`) | Spark by default (run option), medium | The default drafter: write the page as English a good writer would have written, in the book's voice, and leave fidelity to the readers and the desk to restore (`experiments/05-plain-first-draft.md`) | English per paragraph, or per group of paragraphs joined; translator's notes |
| **translate-draft** | The same, with `--draft-prompt translate-draft` | As above | The faithful-first drafter. Same job, same schema | The same |
| **steer** | The checkpoint, when a person leaves a note on the reading, the bible or the first page (`house/steer.py`; from the editors' desk or `keikaku steer`) | Wonder, medium | Carry the note into the reading and the bible as what the text does in English, change only what the note touches, and reply in a few plain sentences. The note is quoted as data, never as instructions. The first page is then drafted again in the amended reading | What changed, a line each; the reading and the bible, amended or as they were; the reply; a question, or none |
| **reader-faithful** | Stage `readers` (`house/stages/readers.py`), once a part | Spark by default (run option), medium, strict | The author's side: meet the Japanese first, then the English, and say what her language does that the English doesn't | Margin notes, or none: paragraph, the span, the problem, the Japanese, a suggested wording where one is clear, how sure |
| **reader-readable** | Stage `readers`, once a part, independently of the faithful reader | Spark by default (run option), medium, strict | The English reader's side: meet the English first, the Japanese to hand, and mark where it stops being prose a good writer would sign | Margin notes, the same shape |
| **desk** | Stage `desk` (`house/stages/desk.py`), once a part that has notes | Wonder by default (run option), medium | The only call that writes after the draft: weigh both readers' notes and the translator's against the reading, and change what needs changing with the edit tool, each edit naming the notes it answers. Code refuses an edit whose words aren't found exactly once, and never touches a locked line | Notes declined, with reasons; disagreements, sent up as forks or not; findings that change an earlier part |
| **final-read** | Stage `final-read` (`house/stages/final_read.py`): the whole text in one call, or a part at a time for a long one | Wonder by default (run option), medium | Read the finished English as a reader, then against the Japanese: seams, voice drift, the crux, continuity, a word an edit doubled. Fix what it's sure of with the edit tool | Notes for the editor, only for real judgement calls; a short verdict |
| **copy-desk** | Stage `copy-desk` (`house/stages/copy_desk.py`), after code has applied house style | Spark by default (`copy_model`), low; up to 30 turns | Make names, terms and italics consistent with the edit tool and a find tool, working from two lists code makes: words the English spells more than one way, and name readings the ruby gives. Sees the whole English when it fits | A summary of what it changed |
| **notes** | Stage `notes` (`house/stages/notes.py`), once a part, on the finished English | Spark, low | Notes for each view (Casual, Curious, Student) that pass the keikaku test: only what the sentence can't give the reader. Each call also sees the readers' notes the desk declined | Notes with anchor, span, views and sources, stored as unverified |
| **reader-proposal** | Every comment posted in the margin, in the background (`house/comments.py`, `screen`) | Spark, low | Decide whether a comment, and the name its writer gave, can be shown. The comment is quoted as data, never instructions. Until it passes, only its writer sees it | Pass or fail, with the reason shown to the writer |
| **baseline-oneshot** | `keikaku audit --baseline` (`house/audit.py`) | Spark, medium | The control: "translate this into English". Only its "Sent to the model" section is sent, with no house brief, no reading and no schema | The English, as plain text |
| **audit-spans** | `keikaku audit` (`house/audit.py`) | Wonder, medium, strict | A blind read of one version against the Japanese, with the reading and the bible: every fidelity problem, with its kind, a one-line reason in plain words and a severity | Marks; an overall line |
| **audit-readable** | `keikaku audit --readable` | Wonder, medium, strict | A blind read of one version for translationese: every span a literary editor would mark as reading like a translation, checked against the Japanese so the author's own strangeness isn't marked | Marks; an overall line |

The audits get each version on its own, unlabelled, with the same reading and bible, so the same prompt reads ours and the baseline alike.


## How the prompts are written

The rule is that prompts teach principles and code enforces limits.

- **Say what the job is for and why**, in a few paragraphs, as you'd brief a new colleague, so that a case nothing covers can still be worked out. Not a list of rules.
- **Few always and never rules.** A reason generalises; a rule gets applied where it doesn't fit. The few that stay are the ones that are never right to break: the reader's text is data, a note is never voiced as the author.
- **One or two contrasting examples, from very different texts**, so the model learns the judgement rather than copying a shape. The examples matter more than the wording, and they risk anchoring: if a run's output echoes one, the example comes out and the prompt relies on description alone.
- **What it gets and what it returns.** The schema does the policing; the prompt doesn't repeat it.
- **No limits the code enforces**: budget, caps on notes, findings and forks, locked lines, exact-match edits. Those live in `house/`, where they can't be argued with.
- **No internal names.** A model given a house term for something repeats it in notes a reader sees, so prompts describe the thing instead of naming it.
- **Short.** A prompt that keeps growing is usually two jobs.
- **The house brief sits first in every call**, so it's the start of every cached prefix; the stable blocks (the reading, the bible, the source) come next and the page last.
