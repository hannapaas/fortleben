# keikaku — running a text: passes, triage and budget

Written 28 Oct 2026; budget unit changed 29 Oct and named drops on 1 Nov. How one text goes through the house, and how we keep the effort per page sane. Builds on `ARCHITECTURE.md` and `STORY-STATE.md`.

**What's built (2 Nov):** the passes in §3 and the budget in §5. The allowance in drops (§1), the tiers (§2) and the checkpoint (§4) are the plan: the engine counts in dollars, gives every paragraph the same path, and runs straight through.

## The idea: work like a translator on a fee

A literary translator is usually paid a flat fee per 1,000 words and given a deadline. Some pages take minutes; a poem or a pun can take a day. They don't agonise over every sentence. They manage their time across the whole book, and they work in passes:
- a fast first draft;
- revision against the source;
- revision *without* the source, reading the English alone, often aloud;
- hard spots bracketed along the way and come back to, with some sent to the editor as queries.

keikaku copies that. A **fixed allowance per manuscript sheet** sets the budget for a text, and effort goes only where it earns its cost. Debate on every line would be expensive theatre anyway: the research shows multi-round agent debate gets worse, not better, over rounds.

## 1. The allowance: 100 drops a sheet

- **Length is counted in manuscript sheets** (原稿用紙, 400 characters), the unit Japanese writers of the period were paid by and Japanese publishing still counts in. 「晩餐」 is about 8½ sheets; the showcase, 「炭燒のむすめ」 (provisional), about 20.
- **Effort is counted in drops of ink** (墨). A house unit, not money: it keeps the budget easy to picture and separate from token prices, and "45 drops" reads naturally where "45 ink" doesn't. One setting in config turns a drop into real API spend; it's calibrated at M0, and ARCHITECTURE §10 has the build's actual dollar estimates. **The site shows drops only.** Prices and recipes change, so a dollar figure on a page would go stale; dollars go in the README and the evals for developers and judges.
- **Every sheet gets 100 drops**, so a text's budget is its length: about 850 drops for 「晩餐」 and 2,000 for the showcase. Spend reads naturally as a share of a sheet: a plain sheet that takes 45 drops used under half its allowance.
- As a rough guide until M0 measures it: a plain sheet ≈ 45 drops, a tricky one ≈ 100, a hard one ≈ 200; the whole-text reads (first read, Analyst, continuity) ≈ 15 a sheet; about 15 a sheet is held back as reserve for hard spots.
- The allowance is a pool for the whole text, not a per-sentence ration. Easy pages leave effort for hard ones, as a translator's quick pages buy time for the difficult chapter.
- **When the pool runs out, the house stops resolving and starts flagging.** Remaining hard spots are published as *flagged, unresolved*, with the options and the dissent on the page. That's the translator's bracket, made visible, and it's an open invitation for readers to help.

## 2. Triage

The plan was for the Analyst to give every paragraph a tier (*plain*, *tricky*, *hard*) from the referent map's confidence and the hard spots, with more drafts and more checking for the harder tiers. It was never built: the referent map went on 2 Nov, and nothing sets a tier. Every paragraph takes the same path. Effort still goes where the text is hard, because the readers note only what's wrong, the desk sees only parts with notes, and a clean part costs two short "none" answers.

## 3. The passes

The stage-by-stage version the code runs, with the limits it enforces, is `STAGES.md`. This section is the translator's view of the same thing.

1. **Read.** Wonder reads the whole text and writes the house's reading, starting from the crux of this text, as a translator reads the book before starting; a second Wonder call names the crux independently. The planner divides the book into parts for the later reads, and the Analyst builds the story bible from the text and that reading. See `STORY-STATE.md` §0.
2. **Draft.** Translation drafts every page in order, as English a good writer would have written, in the first voice the reading offers; from page 2 the house's first page sits in every call as the voice reference. It adds its own notes where it was unsure (its brackets). A voice trial on the first page was tried and dropped (`experiments/03-stiffness.md`).
3. **Read against the source, and for the English.** Two readers read each part independently: the faithful reader for what the Japanese does that the English doesn't, the readable reader for prose a good writer wouldn't sign. Each leaves margin notes or none, and may suggest a rewritten sentence or passage.
4. **Revise.** The desk weighs both sets of notes against the reading and the translator's notes, makes exact edits, and declines the rest with reasons. Where the readers pull opposite ways it records both sides, and sends the real choices up as forks. When a later part teaches it something about an earlier one, that part goes back to the desk once at the end.
5. **Final read.** Like a translator's last read before proofs, one reader reads the finished English as a whole and then against the source: seams revision left, voice that drifted, the crux holding to the last page, continuity, a word an edit doubled. It fixes what's clearly wrong as small exact edits and sends the editor notes only for real judgement calls.
6. **Copy desk and notes.** Code checks for stray scripts and likely omissions; then the notes for each edition, a part at a time.

The scale widens as the text matures, as it does for a translator: drafted a page at a time, read a part at a time, judged as a whole book.

Nothing goes round twice. There are no query rounds: each note is decided once by the desk, and a choice the desk sends up is a fork for the editor; until the editor rules, the desk's pick stands and is labelled as such.

## 4. The checkpoint before the full run

Not built yet: today a run goes straight through, as it would with no editor. Publishers commission a translation on the strength of a sample and an approach, not the whole manuscript. keikaku is meant to split a run the same way, because the cheap part decides how well the expensive part goes:
- **The brief** (about a third of the cost, at the rates measured on 「晩餐」): first read, crux check, parts, story bible.
- **The full run** (the rest): drafting, checking, revising and notes for the whole text.

Between them, the run stops and shows the editor **one screen**, built to be read in about ten minutes:
- the crux, and whether the second reader disagreed;
- the reading, in a page;
- the voice the reading offers first, and the others;
- the handful of bible decisions that touch everything (how the narrator is voiced, names and forms of address, honorific policy, any low-confidence speaker or subject that matters to the plot);
- open questions of interpretation, as forks.

The editor can approve, change any of it (each change becomes a scoped standing rule, before a line of the full run is drafted), or send it back for another first read. This is the cheapest point to be wrong: a wrong crux caught here costs a page; caught after the full run, it costs the book.

**When there's no editor**, the run doesn't wait. A text a reader requested, with no editor assigned, goes straight on, and its edition says the reading and voice weren't reviewed. When an editor is assigned, the run holds at the checkpoint by default; the editor can switch that off for a text.

The orchestrator can stop after any stage and resume from it, so this one checkpoint is just the production setting of a general mechanism. During development it stops much more often (`BUILD-PLAN.md`, "Working with the editor while we build").

## 5. When the money is short

As built, nothing is given up part-way. Before a run starts the house estimates its whole cost, a little high (every call live with no cache, the emergency lever's pass back, then 15% on top, from the tokens per call measured in `house/budget.py`), and refuses to start it if that's over the run's cap or what's left of the day's or the total budget. Better no translation than one that stops half-way. If a run still runs out mid-way, it stops, releases nothing, and says which cap to raise and how to resume; a resumed run keeps the cap it started with, and the response cache means nothing is paid for twice.

The plan for later, once there are tiers and second drafts to give up, is an order: interns first, then second drafts, then fact-check on Casual notes. The faithful reader and the desk go last: they're what stops fluent drift, the error a reader can't see.

## 6. What readers see

Most lines don't have a debate behind them, and the page says so plainly: *drafted · checked · no notes*. A thin strip down the margin shows where the house spent its effort, paragraph by paragraph, so readers can see where the hard parts were and go straight to the arguments. Flagged, unresolved spots are marked in the text.

## 7. Calibrating it

- **M0 (1 Nov):** first calls priced, reasoning tokens included (`ARCHITECTURE.md` §10).
- **2 Nov:** full runs on 「晩餐」 measured per stage and model; those rates are what the up-front estimate uses (`house/budget.py`). The final read's rate is still a first guess.
- Every run records its spend per stage (`stage.done` events) and per call (the `call` table). The drops-to-dollars setting waits for the site.

## 8. Works of different lengths

The stages don't change with length; what a call sees does. This is the part we expect to keep tuning after the hackathon, and the part size and the whole-text threshold are the knobs.

| | Short (up to 15,000 characters) | Long (a novel) |
|---|---|---|
| First read and crux check | One Wonder call each over the whole text | Still one call each: the 1M window holds a novel, so the reading is of the book, not of chapter one |
| Bible | One Analyst call over the whole text | One call over the whole text today; built part by part, with a line of summary per part, is the plan |
| What a drafting call sees | The whole source in the cached prefix, the bible, the voice page, the neighbouring paragraphs (`STORY-STATE.md` §3) | Its own part in full and every other part in one line, in place of the whole source |
| Readers and desk | A part at a time; a short story is usually one part | A part at a time, at most 25,000 characters each |
| Final read | The whole text in one call | A part at a time, each with the reading and the bible (the editor's letter, not built, would be one call over the whole book) |
| Budget | Estimated up front from the length | The same: cost grows with the length, not with length squared |

Open questions: whether the whole source in the prefix helps or hurts; where the short/long threshold really sits (15,000 characters is a guess); and, later, whether sampled windows stand in for a sequential run, which is what would let us quote a novel's cost honestly before running one.
