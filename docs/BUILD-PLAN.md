# keikaku — build plan

Written 27 Oct 2026, the second day of the hackathon; updated 28 Oct with the final text picks and design direction. The work is in dependency order. **‖** marks lanes that can be built at the same time. Lanes code against the M1 contract (schema, event types, fixtures), not against each other.

## Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | **First calls and cost calibration** (serial, first) | A Responses API call to Spark returns schema-valid JSON, uses `prompt_cache_key` and web_search, and logs input / cached / output / reasoning tokens and $ into a spend ledger. Wonder and Glimmer (local + hosted) each answer once. Reasoning tokens at low / medium effort are measured on a 1k-char chunk, and the cost table in ARCHITECTURE §10 is updated. |
| **M1** | **Contract** (serial) | `schema.sql`, the event-type list and JSON schemas for every department output are committed. The Aozora parser round-trips 晩餐, 我牢獄, 三十三の死 and the Setsu passage (ruby, emphasis, IDs, colophon). Fixture JSON for 晩餐 (segments, a few queries, notes, a fork, events) exists. |
| M2a ‖ | **Engine core** | The runtime, budgets, response cache, carried state, Analyst, Translation and Source check run 晩餐 end to end, writing events and revisions. |
| M2b ‖ | **Reader site** | The pamphlet design ported to templates: per-book accent colour, ruby, seals and colophon, a near-black dark mode. A reader settings panel (edition, layout, what to show, a quiet preset, text size, furigana) that never loses your place. The margin variorum, two-axis reactions, proposals into a moderation queue, labels, credits. Everything renders from the fixture. Works at phone width. |
| M2c ‖ | **House view + streaming** | The floor plan and message stream play a fake event fixture over SSE, with resume and replay at 8×. |
| M2d ‖ | **Deterministic checkers + eval harness** | Tic detector, ledger checker and length-ratio flagger (shared with the copy desk). E4 stats. S0 and S1 baselines. T1/T3 sets assembled and frozen. A blind A/B form, in case a bilingual reader has time. |
| M2e ‖ | **Catalogue** | A Glimmer vs Spark spot check on 10 works. Reader's reports generated on Meta models for the long-list. Catalogue pages with evidence and date for "untranslated". "I'd read this" votes, a request form (search the Aozora index or give an outside reference) and a wanted list. Acquisitions checks outside requests and the editor confirms. |
| M2f ‖ | **Ops** | Fly deploy. Spend caps (live run / daily / total), kill switch, one-run queue, per-IP limits, invite-link auth for editor and reviewers. The replay fallback works when the house is closed. |
| **M3** | **Full pipeline on 晩餐** (needs M2a; then adds Editorial, Copy desk, Notes, Fact-check, forks, interns, rules) | One run produces queries with stet / accept / revise, ≥1 fork with verbatim dissent, ≥1 intern with a logged reason, a standing rule that propagates and skips locked lines. Cost per 1k chars is within the pessimistic figure. The run streams into M2c and renders in M2b. |
| **M4** | **Experiments + prompt freeze** | 我牢獄, 雪をんな and the Setsu passage run. The hard text's failures are written up honestly. Prompts are tagged `frozen-v1`. **Midpoint check (below).** |
| M5 ‖ | **Showcase with the editor** | The editor approves the style sheet for 三十三の死. Sample checkpoint (first ~1 page): notes become scoped rules, ≤5 forks. The full run follows. The edition carries honest labels, an editor's note and credits. If a bilingual reader has time to check passages, those are labelled *human-reviewed*; nothing waits for it. |
| M6 ‖ | **Evals** | E1–E6 done (timing below). Charts render on the Evals page and in the README. |
| M7 | **Integrate** | Live site: showcase, experiments, Setsu comparison, Catalogue, House (live + replay), Evals, Credits, "Where this comes from". A live run on a preset passage succeeds three times in a row from a phone. |
| M8 | **Ship** | 3-min video, README first screen, LICENSE, a secrets scan of the full history. Submitted on **3 Nov**, a day early. Caps set for the judging period. |

## Eval runs and when they happen
- **After M0:** S0 one-shot on dev passages, used to build Spark's own excess-vocabulary list for the tic detector (E4, free).
- **After M4 freeze:** S0, S1 and S2 on T1 (8–12 passages: the Setsu/1918 pair plus 2–3 more public-domain works with published translations) and on T3 (20–30 probes).
  - Then the E2 accuracy audit and the E1 jury.
  - **No eval depends on human raters.** LLM judges are known to reward fluent drift, so the headline numbers are the reference-based comparisons (against the 1918 translations) and E2's span-level accuracy audit; the model jury is reported with that caveat. If a bilingual reader does blind A/B pairs, they're reported separately as a bonus.
- **During M5:** the snapshots after each stage give E5 (errors fixed vs errors introduced, per department, interns on vs off) at no extra cost.
- **After M5:** E3, the long-context experiment below. E6 judge calibration comes out of the E1 data.
- **All numbers are frozen before the video is recorded.**

## Long-context experiment (E3): book behaviour on a short-story budget

**Question:** do chunked fresh calls with a carried state behave like whole-book context? And does quality drift with position?

1. **Read everything, translate a sample.**
   - Run the Analyst and the rolling summaries over one long public-domain work (100–150k chars; translated or not doesn't matter, because there's no reference). That's mostly input tokens, so it costs about $0.50.
   - Translate only three five-chunk windows, at 0–5%, 45–50% and 90–95%, so the state at each window is the real state at that position.
2. **Validate the sampling on the showcase.**
   - Compare the sampled windows against the full sequential M5 run.
   - If the consistency metrics match within noise, the windows stand in for the whole book, and novel-scale cost can be extrapolated honestly.
3. **Conditions** (translate call only, frozen prompts, low effort):
   - C1: no state.
   - C2: ledger only.
   - C3: the full carried state (≤5k).
   - C5: C3 plus the whole source in the cached prefix. This is the Meta-specific question: is the 1M window, cheap when cached, better than curation?
   - C0: append-only full history, on the showcase only. Prefix caching should make it cheaper than people assume; measure it.
4. **Drift probes** (model-free):
   - Entity consistency for everything that occurs ≥3 times.
   - Honorific-rule adherence.
   - 10–20 callbacks introduced early and recurring late.
   - Tense stability.
   - Length ratio and tic rate plotted by position.
5. **Planted continuity test:**
   - Inject 10 known inconsistencies into a copy of the showcase translation.
   - Compare what one Wonder whole-text read catches with what the chunked Spark check catches.
   - Report the catch rate.

**Cost:** about $5–10 on Standard, under $1 on Contributor. **Charts:** consistency against $ per condition; drift lines by position; a catch-rate table.

## Midpoint exit check (31 Oct)

These must be true:
1. M3 is done: a real end-to-end run on 晩餐, within the pessimistic cost.
2. A real run streams into the House view.
3. The reader site renders 晩餐 from the database in two editions.
4. The showcase is parsed, its story bible built, and its style sheet drafted.
5. Credit spend is ≤ $45.

**If 1 or 2 fails:** fall back to the minimal pipeline (Analyst → Translation → Source check → Copy desk → Notes). Interns and forks then appear only in the recorded run.
**If more than two items fail:** stop adding, ship the showcase and evals, and cut from the list below.

## Cut list (cut from the top)
1. The stretch text.
2. Muse Image covers (typographic covers instead) and Voice Transcribe dictation.
3. The Student edition (keep Casual + Curious).
4. E3's long-book windows and C0 (keep C1/C3/C5 on the showcase).
5. The Catalogue cut to 30 reports; the Acquisitions agent for outside requests (requests are still collected, and the editor checks them by hand).
6. Proposals (keep reactions).
7. Live runs on arbitrary Aozora cards (presets only), then replay-only House.
8. Live interns (keep them in the recorded run).

**Never cut:** the showcase with honest labels, Source check, E1/E2/E4, the House replay, the video.
