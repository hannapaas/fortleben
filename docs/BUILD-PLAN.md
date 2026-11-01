# keikaku — build plan

Written 27 Oct 2026, the second day of the hackathon; updated 28 Oct with the final text picks and design direction. The work is in dependency order. **‖** marks lanes that can be built at the same time. Lanes code against the M1 contract (schema, event types, fixtures), not against each other.

## Where we are, 30 Oct

Nothing is built yet: the repo holds plans. Five days remain, and the last push has to be in by the evening of 4 Nov UK time. So the order below is the order, with the thinnest working path first and everything else added only once it runs:

1. **M0 and M1** (serial, now). M0 is blocked until `public/.env` holds a working `META_API_KEY`; `uv` and the Glimmer Ollama pull are also missing.
2. **The minimal pipeline** (`STAGES.md`: parse, first read, bible, draft, source check, answer, code checks, notes, release) on 「晩餐」, writing events; the site and House view rendering the fixture in parallel (M2b, M2c), deploy (M2f).
3. **M3:** the remaining stages, forks, interns, rules. Midpoint check at the end of 1 Nov.
4. **M5 and M6:** the showcase brief and checkpoint, the full run, S-GT fetched, E2 + E4 + the planted continuity test, the exhibit. Then the shelf (M5b), the experiments (Tōkoku, Kasai) and E1.
5. **M7 and M8:** integrate, README, video, a clean-clone replay check, submit.

Started at the back of the queue, not cut: the Catalogue beyond the 15 launch titles, the acquisitions agent for outside requests, the Student edition, E3's long-book windows and C0, Glimmer on Modal (the code checks run without it), covers and dictation, the stretch text.

## Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | **First calls and cost calibration** (serial, first) | A Responses API call to Spark returns schema-valid JSON, uses `prompt_cache_key` and web_search, and logs input / cached / output / reasoning tokens and $ into a spend ledger. Wonder and Glimmer (local + hosted) each answer once. Reasoning tokens at low / medium effort are measured on a 1k-char chunk, and the cost table in ARCHITECTURE §10 is updated. |
| **M1** | **Contract** (serial) | `schema.sql`, the event-type list and JSON schemas for every department output are committed. The Aozora parser round-trips 晩餐, 我牢獄, 三十三の死 and the Setsu passage (ruby, emphasis, IDs, colophon). Fixture JSON for 晩餐 (segments, a few queries, notes, a fork, events) exists. |
| M2a ‖ | **Engine core** | The runtime, budgets, response cache, carried state, Analyst, Translation and Source check run 晩餐 end to end, writing events and revisions. |
| M2b ‖ | **Reader site** | The pamphlet design ported to templates: per-book accent colour, ruby, seals and colophon, a near-black dark mode. A reader settings panel (edition, layout, what to show, a quiet preset, text size, furigana) that never loses your place. The margin variorum, two-axis reactions, comments and proposals through the model screen, labels, credits. Everything renders from the fixture. Works at phone width. |
| M2c ‖ | **House view + streaming** | The floor plan and message stream play a fake event fixture over SSE, with resume and replay at 8×. |
| M2d ‖ | **Deterministic checkers + eval harness** | Tic detector, ledger checker and length-ratio flagger (shared with the copy desk). E4 stats. S0 and S1 baselines. T1/T3 sets assembled and frozen. A blind A/B form, in case a bilingual reader has time. |
| M2e ‖ | **Catalogue** | A Glimmer vs Spark spot check on 10 works. Reader's reports generated on Meta models, the 15 launch titles first and the long-list only if time allows. Catalogue pages with evidence and date for "untranslated". "I'd read this" votes, a request form (search the Aozora index or give an outside reference) and a wanted list. Acquisitions checks outside requests and the editor confirms. |
| M2f ‖ | **Ops** | Fly deploy. Spend caps (live run / daily / total), kill switch, one-run queue, per-IP limits, invite-link auth for editor and reviewers. The replay fallback works when the house is closed. |
| **M3** | **Full pipeline on 晩餐** (needs M2a; then adds Editorial, Copy desk, Notes, Fact-check, forks, interns, rules) | One run produces queries with stet / accept / revise, ≥1 fork with verbatim dissent, ≥1 intern with a logged reason, a standing rule that propagates and skips locked lines. Cost per 1k chars is within the pessimistic figure. The run streams into M2c and renders in M2b. |
| **M4** | **Experiments + prompt freeze** | 我牢獄, 雪をんな and the Setsu passage run. The hard text's failures are written up honestly. Prompts are tagged `frozen-v1`. **Midpoint check (below).** |
| M5 ‖ | **Showcase with the editor** | The brief runs on 三十三の死 and stops at the checkpoint (`RUNNING-A-TEXT.md` §4): the editor's changes become scoped rules, ≤5 forks. The full run follows. The edition carries honest labels, an editor's note and credits. If a bilingual reader has time to check passages, those are labelled *human-reviewed*; nothing waits for it. |
| M5b ‖ | **The shelf** | After M5's full run holds: the short Catalogue titles (under ~15k characters, the 15 launch titles first) run through the house with no editor, Spark calls on the Contributor tier (approved for public-domain texts), labelled *house-checked*. Target ten or more editions; each costs a dollar or two. The first thing cut if M5 slips. |
| M6 ‖ | **Evals** | E1–E6 done (timing below), with the comparison against S-GT as the headline. The annotated side-by-side exhibit is made. Charts render on the Evals page and in the README. |
| M7 | **Integrate** | Live site: showcase, experiments, Setsu comparison, Catalogue, House (live + replay), Evals, Credits, "Where this comes from". Presets are pre-briefed (reading and bible built ahead). A live run on a preset passage succeeds three times in a row from a phone. `keikaku serve --replay` shows the recorded run from a clean clone with no key. |
| M8 | **Ship** | 3-min video, README first screen, LICENSE, a secrets scan of the full history. A dry run of the submission form on 3 Nov; the final push and submission on 4 Nov, hours before 9 PM ET. Caps set for the judging period. |

## Working with the editor while we build

In production a run stops once, at the checkpoint before the full run (`RUNNING-A-TEXT.md` §4). While we develop, it stops after every stage, so each stage can be checked and its prompt tuned before the next one is built on it. The orchestrator's stop-and-resume is the same mechanism in both cases; development just uses more stops. The response cache makes reruns of earlier stages free.

Most of the back-and-forth is between the developer and the outputs: run a stage on 「晩餐」, read the result, set it against the S-GT version and the auditor's notes, adjust the prompt, rerun. The editor's time is the scarcest thing in the build, so it's spent at a few points where taste matters most and can't be guessed:

| When | What the editor sees | Time | What it changes |
|---|---|---|---|
| After first-read works (M2a) | The house's reading and crux for 「晩餐」. Is the crux right? What's missing or wrong? | ~5 min | The first-read prompt and its examples |
| After the voice trial works (M2a) | Two or three versions of 「晩餐」's first page. Which one, and why, in a line? | ~5 min | The voice-trial and draft prompts |
| First full draft of 「晩餐」 (M3) | Our draft beside S-GT, with the auditor's notes. Mark the three worst things in ours; say where the auditor is wrong | ~15 min | Source check, editor's letter, the auditor |
| The showcase checkpoint (M5) | The real production checkpoint on 「三十三の死」, as a reader of the finished house would see it | ~10–15 min | The showcase, and a test of the checkpoint itself |
| Before submission (M8) | The annotated exhibit | ~10 min | What judges see first |

Under an hour across the week. Each touchpoint is a single review page with specific questions answerable in a line, sent when it's ready and answered when there's time. Nothing waits for an answer: if none has come by the next session, the developer's pick stands and is noted, and the answer is applied when it comes. The editor's answers become prompt examples and test cases, which is how taste gets into the house.

## The headline comparison: against what readers use today

Today a reader who wants one of these stories pastes it into Google Translate in the browser. If keikaku isn't clearly better than that, there's no point. So that is the headline baseline, **S-GT**: free browser Google Translate output on the same passages, fetched by hand and dated. The copy doesn't attack Google; it says "a one-shot machine translation", with the method in a footnote. It sits alongside S0 (one-shot Spark, no context), so we can also show how much comes from the house rather than the model.

**The measure:** the E2 span-level audit run on keikaku and S-GT alike, blind (outputs unlabelled, order shuffled). The auditor is Wonder with the source, the house's reading and the story bible, because that's what tells it what to look for: who's speaking, what a name or term was set up as pages earlier, which repetition is deliberate, what the crux is. Headline numbers: errors per 1,000 characters by type, and how many of them a reader of the English alone could never spot.

**The auditor shares the house's blind spots.** Wonder also runs Source check inside the pipeline, with the same bible, so an error it can't see there it can't see in the audit either, and the comparison would flatter us. The non-Meta judge (approved for evals only) runs the same audit on the headline set, and both counts are reported side by side. Where they disagree, the page says so.

**The exhibit.** Judges can't read a novel, so the submission leads with one annotated side-by-side: one shortish passage, or three or four very short ones, with the one-shot version and ours, arrows and margin notes saying in plain words what went wrong and why ("doesn't know who *she* is: that was set up two pages earlier"; "the same word becomes three different words"; "this sentence is missing"; "makes an uneducated narrator sound well-read"). It should make sense to an engineer who reads no Japanese. Passages are picked from the audited set, and the full counts sit next to the exhibit, so it isn't cherry-picked; anywhere ours is worse is shown too.

## Eval runs and when they happen
- **After M0:** S0 one-shot on dev passages, used to build Spark's own excess-vocabulary list for the tic detector (E4, free). Fetch S-GT for the dev passages too, so the auditor is tuned on real one-shot errors early.
- **After M4 freeze:** S-GT, S0, S1 and S2 on T1 (8–12 passages: the Setsu/1918 pair plus 2–3 more public-domain works with published translations) and on T3 (20–30 probes).
  - **A passage is never translated cold.** The house's whole point is that it has read the book, so for every T1 work the brief runs on the *whole* text (background, first read, crux, bible: a few whole-text calls, mostly cached input, under a dollar for a 30k-character work), and only then are the sampled passages drafted, with the real reading, bible and position state. That's the same "read everything, translate a sample" method as E3. Setsu's 「思い出の記」 is 30.7k characters, so if the budget allows it is simply run whole, which gives a whole-work reference comparison; otherwise three windows. S0 gets the passage alone, which is exactly the difference being measured. The T3 probes are the one exception: they're short constructed items with their context given inline, and every system sees the same context.
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
   - C3×3: C3 with three-page chunks instead of one, on 晩餐. Does the longer unit read better, and does it drop more sentences?
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

## Midpoint exit check (end of 1 Nov)

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

**Never cut:** the showcase with honest labels, Source check, E2/E4 and the planted continuity test (the cheapest legible proof of what Wonder's whole-text read adds), the S-GT comparison and its exhibit, the House replay, the video.
