# keikaku — running a text: passes, triage and budget

Written 28 Oct 2026. How one text goes through the house, and how we keep the cost per page sane. Builds on `ARCHITECTURE.md` and `STORY-STATE.md`.

## The idea: work like a translator on a fee

A literary translator is usually paid a flat fee per 1,000 words and given a deadline. Some pages take minutes; a poem or a pun can take a day. They don't agonise over every sentence. They manage their time across the whole book, and they work in passes:
- a fast first draft;
- revision against the source;
- revision *without* the source, reading the English alone, often aloud;
- hard spots bracketed along the way and come back to, with some sent to the editor as queries.

keikaku copies that. A **rate per 1,000 Japanese characters** sets the budget for a text. The Analyst **triages** every paragraph by difficulty, most paragraphs get a short, cheap path, and debate happens only where it earns its cost. Debate on every line would be expensive theatre anyway: the research shows multi-round agent debate gets worse, not better, over rounds.

## 1. The rate card

- **Budget = rate × length.** The default rate is **$0.20 per 1,000 Japanese characters**, between the base and pessimistic estimates in ARCHITECTURE §10. A 20% reserve for hard spots sits inside that, not on top.
- In page terms, a Japanese paperback page is about 600 characters, or roughly 270 English words, so about **12¢ a page**. The showcase, 「三十三の死」 at 13.5k characters, gets $2.70.
- The envelope is a pool for the whole text, not a per-sentence allowance. Easy pages leave money for hard ones, as a translator's quick pages buy time for the difficult chapter.
- **When the envelope runs out, the house stops resolving and starts flagging.** Remaining hard spots are published as *flagged, unresolved*, with the options and the dissent on the page. That's the translator's bracket, made visible, and it's an open invitation for readers to help.

## 2. Triage

Before drafting, the Analyst gives every paragraph a tier, from signals already in the story bible: referent-map confidence, hard spots (poems, wordplay, allusions), classical grammar or dialect, dialogue density, and motif occurrences.

| Tier | Expected share | What it gets |
|---|---|---|
| **Plain** | ~70% | One draft. Source check (Wonder, low effort). Code checks. Covered by Editorial's read-through, with no line-by-line edit |
| **Tricky** | ~20% | Everything above, plus a second draft with the head selecting, Editorial span queries, and up to two query rounds |
| **Hard** | ~10% | Everything above, plus a fork to the editor with dissent quoted, an intern if the head asks, and Fact-check on any note |

Paragraphs can move up a tier mid-run (for example, Source check finds a real error in a "plain" one). They never move down silently. The shares are expectations, not quotas; the run reports the real mix.

## 3. The passes

1. **Read.** The Analyst reads the whole text once and writes the story bible and the tiers.
2. **Draft.** Translation drafts every paragraph in order, adding its own notes where it was unsure (its brackets).
3. **Check against the source.** Source check reads every paragraph against the Japanese and raises queries only on real problems. On plain paragraphs this is usually "none".
4. **Revise.** Translation answers the queries (accepted / stet / revised). Tricky paragraphs get second drafts; hard ones can become forks.
5. **Read without the source.** Editorial reads the English alone, a whole scene at a time rather than line by line, as a reader would, and sends span queries back. Every change goes back through Source check.
6. **Copy desk, notes and fact-check.**
7. **Whole-text read.** Wonder reads the source and translation together once, for continuity.

Every query has at most two rounds. After that, it's a fork for the editor or, if the editor hasn't ruled, the head's pick stands and is labelled as such.

## 4. Spending less when money is short

If the run is heading over its envelope, it gives things up in this order:
1. interns;
2. second drafts on tricky paragraphs (the first draft stands, flagged);
3. Fact-check on Casual-edition notes (Curious and Student keep it);
4. Editorial's read of plain paragraphs.

**Source check on every paragraph is never cut.** It's the department that stops fluent drift.

## 5. What readers see

Most lines don't have a debate behind them, and the page says so plainly: *drafted · checked · no queries*. A thin strip down the margin shows where the house spent its effort, paragraph by paragraph, so readers can see where the hard parts were and go straight to the arguments. Flagged, unresolved spots are marked in the text.

## 6. Calibrating it

- **M0:** price one paragraph of each tier on real calls, including reasoning tokens.
- **M3:** a full run on 「晩餐」. Compare actual spend per tier and per department with the rate card, then adjust the rate, the tier shares or the tier recipes.
- Every run reports cost per 1,000 characters and per page, split by tier and department. These figures go in the README.
