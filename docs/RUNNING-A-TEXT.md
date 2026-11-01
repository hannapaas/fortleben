# keikaku — running a text: passes, triage and budget

Written 28 Oct 2026; budget unit changed 29 Oct and named drops on 1 Nov. How one text goes through the house, and how we keep the effort per page sane. Builds on `ARCHITECTURE.md` and `STORY-STATE.md`.

## The idea: work like a translator on a fee

A literary translator is usually paid a flat fee per 1,000 words and given a deadline. Some pages take minutes; a poem or a pun can take a day. They don't agonise over every sentence. They manage their time across the whole book, and they work in passes:
- a fast first draft;
- revision against the source;
- revision *without* the source, reading the English alone, often aloud;
- hard spots bracketed along the way and come back to, with some sent to the editor as queries.

keikaku copies that. A **fixed allowance per manuscript sheet** sets the budget for a text. The Analyst **triages** every paragraph by difficulty, most paragraphs get a short, cheap path, and debate happens only where it earns its cost. Debate on every line would be expensive theatre anyway: the research shows multi-round agent debate gets worse, not better, over rounds.

## 1. The allowance: 100 drops a sheet

- **Length is counted in manuscript sheets** (原稿用紙, 400 characters), the unit Japanese writers of the period were paid by and Japanese publishing still counts in. 「晩餐」 is about 8½ sheets; the showcase, 「三十三の死」, about 34.
- **Effort is counted in drops of ink** (墨). A house unit, not money: it keeps the budget easy to picture and separate from token prices, and "45 drops" reads naturally where "45 ink" doesn't. One setting in config turns a drop into real API spend; it's calibrated at M0, and ARCHITECTURE §10 has the build's actual dollar estimates. **The site shows drops only.** Prices and recipes change, so a dollar figure on a page would go stale; dollars go in the README and the evals for developers and judges.
- **Every sheet gets 100 drops**, so a text's budget is its length: about 850 drops for 「晩餐」 and 3,400 for the showcase. Spend reads naturally as a share of a sheet: a plain sheet that takes 45 drops used under half its allowance.
- As a rough guide until M0 measures it: a plain sheet ≈ 45 drops, a tricky one ≈ 100, a hard one ≈ 200; the whole-text reads (first read, Analyst, continuity) ≈ 15 a sheet; about 15 a sheet is held back as reserve for hard spots.
- The allowance is a pool for the whole text, not a per-sentence ration. Easy pages leave effort for hard ones, as a translator's quick pages buy time for the difficult chapter.
- **When the pool runs out, the house stops resolving and starts flagging.** Remaining hard spots are published as *flagged, unresolved*, with the options and the dissent on the page. That's the translator's bracket, made visible, and it's an open invitation for readers to help.

## 2. Triage

Before drafting, the Analyst gives every paragraph a tier, from signals already in the story bible: referent-map confidence, hard spots (poems, wordplay, allusions), classical grammar or dialect, dialogue density, and motif occurrences.

| Tier | Expected share | What it gets |
|---|---|---|
| **Plain** | ~70% | One draft. Source check (Wonder, low effort). Code checks. Covered by Editorial's read-through, with no line-by-line edit |
| **Tricky** | ~20% | Everything above, plus a second draft with the head selecting, Editorial span queries, and up to two query rounds |
| **Hard** | ~10% | Everything above, plus a fork to the editor with dissent quoted, an intern if the head asks, and Fact-check on any note |

Paragraphs can move up a tier mid-run (for example, Source check finds a real error in a "plain" one). Moving one down is logged with a reason, because quietly downgrading hard paragraphs is exactly how a run would save money at the reader's expense. The shares are expectations, not quotas; the run reports the real mix.

## 3. The passes

The stage-by-stage version the code runs, with the limits it enforces, is `STAGES.md`. This section is the translator's view of the same thing.

1. **Read.** A short background brief on the author and period, then Wonder reads the whole text and writes the house's reading, starting from the crux of this text, as a translator reads the book before starting. The Analyst then builds the story bible and the tiers from the text and that reading. See `STORY-STATE.md` §0.
2. **Find the voice, then draft.** The first page is drafted two or three ways and one is chosen as the voice reference (`FROM-TRANSLATORS.md`). Then Translation drafts every page in order, adding its own notes where it was unsure (its brackets) and leaving a few marked alternatives where it can't yet choose.
3. **Check against the source.** Source check reads every paragraph against the Japanese and raises queries only on real problems. On plain paragraphs this is usually "none".
4. **Revise.** Translation answers the queries (accepted / stet / revised). Tricky paragraphs get second drafts; hard ones can become forks.
5. **Read without the source.** First the editor's letter: Wonder reads the whole English draft against the reading and writes big-picture notes (voice drift, a character who sounds wrong, the crux slipping), which Translation answers. Then Editorial reads the English alone, a whole scene at a time rather than line by line, as a reader would, and sends span queries back. Every change goes back through Source check.
6. **Copy desk, notes and fact-check.**
7. **Final read.** Like a translator's last read-through before proofs, Wonder reads the finished English as a whole, as a reader would, and then against the source. It looks for seams that revision left, voice that drifted, the crux holding to the last page, and continuity (contradictions, a confused speaker, a fact that changes). Anything it finds goes back as queries; a second final read happens only if those changes were large.

The scale widens as the text matures, as it does for a translator: drafted a page at a time, read in scenes, judged as a whole book.

Every query has at most two rounds (the orchestrator enforces this). After that, it's a fork for the editor or, if the editor hasn't ruled, the head's pick stands and is labelled as such.

## 4. The checkpoint before the full run

Publishers commission a translation on the strength of a sample and an approach, not the whole manuscript. keikaku splits a run the same way, because the cheap part decides how well the expensive part goes:
- **The brief** (about 15% of the allowance): background brief, first read, crux check, story bible, and the voice trial on the first page.
- **The full run** (the rest): drafting, checking, revising and notes for the whole text.

Between them, the run stops and shows the editor **one screen**, built to be read in about ten minutes:
- the crux, and whether the second reader disagreed;
- the reading, in a page;
- the voice trial: the chosen first page and the alternatives;
- the handful of bible decisions that touch everything (how the narrator is voiced, names and forms of address, honorific policy, any low-confidence speaker or subject that matters to the plot);
- open questions of interpretation, as forks.

The editor can approve, change any of it (each change becomes a scoped standing rule, before a line of the full run is drafted), or send it back for another first read. This is the cheapest point to be wrong: a wrong crux caught here costs a page; caught after the full run, it costs the book.

**When there's no editor**, the run doesn't wait. A text a reader requested, with no editor assigned, goes straight on, and its edition says the reading and voice weren't reviewed. When an editor is assigned, the run holds at the checkpoint by default; the editor can switch that off for a text.

The orchestrator can stop after any stage and resume from it, so this one checkpoint is just the production setting of a general mechanism. During development it stops much more often (`BUILD-PLAN.md`, "Working with the editor while we build").

## 5. Spending less when the pool is short

If the run is heading over its allowance, it gives things up roughly in this order, cheapest loss to the reader first:
1. interns;
2. second drafts on tricky paragraphs (the first draft stands, flagged);
3. Fact-check on Casual-edition notes (Curious and Student keep it);
4. Editorial's read of plain paragraphs.

**Source check is the last thing to go.** It's the department that stops fluent drift, the error a reader can't see. A text that can't afford it on every paragraph is better published with the gap labelled than quietly finished without it.

## 6. What readers see

Most lines don't have a debate behind them, and the page says so plainly: *drafted · checked · no queries*. A thin strip down the margin shows where the house spent its effort, paragraph by paragraph, so readers can see where the hard parts were and go straight to the arguments. Flagged, unresolved spots are marked in the text.

## 7. Calibrating it

- **M0:** price one paragraph of each tier on real calls, including reasoning tokens.
- **M3:** a full run on 「晩餐」. Compare actual spend per tier and per department with the guide above, then adjust the drop-to-spend setting, the tier shares or the tier recipes. The 100 ink a sheet stays fixed; what a unit of ink buys is what moves.
- Every run reports drops per sheet, split by tier and department, alongside its real API spend. The spend figures go in the README and the evals, not on the site.

## 8. Works of different lengths

The recipes don't change with length; the context strategy and the pool do. This is the part we expect to keep tuning after the hackathon, and the pool and the tiers are the knobs.

| | Short (up to ~30k characters: everything we run now) | Long (a novel, later) |
|---|---|---|
| First read | One Wonder call over the whole text | Still one call: the 1M window holds a novel, so the reading is of the book, not of chapter one |
| Bible | One Analyst call plus referent passes | Built chapter by chapter, the same bible updated as the Analyst goes |
| What a drafting call sees | The whole source in the cached prefix, plus the small carried state (`STORY-STATE.md` §3) | The current chapter plus the neighbouring chapters' summaries in place of the whole source; the rolling summary becomes chapter summaries |
| Editor's letter and final read | Whole text, one call each | Whole book, one call each, costed per release; whether a very long book needs them per part is open |
| Pool | 100 drops a sheet | The same, so the pool grows with the book; a novel's hard chapter is paid for by its plain ones |

Open questions, in the order E3 answers them: whether the whole source in the prefix helps or hurts (C5 against C3); where the short/long threshold really sits; whether sampled windows stand in for a sequential run, which is what would let us quote a novel's cost honestly before running one.
