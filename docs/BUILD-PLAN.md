# keikaku — build plan

Written 27 Oct 2026, the second day of the hackathon; updated 28 Oct with the final text picks and design direction. The work is in dependency order. **‖** marks lanes that can be built at the same time. Lanes code against the M1 contract (schema, event types, fixtures), not against each other.

## Where we are, 30 Oct

Nothing is built yet: the repo holds plans. Five days remain, and the last push has to be in by the evening of 4 Nov UK time. So the order below is the order, with the thinnest working path first and everything else added only once it runs:

1. **M0 and M1** (serial, now). M0 is blocked until `public/.env` holds a working `META_API_KEY`; `uv` is also missing.
2. **The minimal pipeline** (`STAGES.md`: parse, first read, bible, draft, source check, answer, code checks, notes, release) on 「晩餐」, writing events; the site and House view rendering the fixture in parallel (M2b, M2c), deploy (M2f).
3. **M3:** the remaining stages, forks, interns, rules. Midpoint check at the end of 1 Nov.
4. **M5 and M6:** the showcase brief and checkpoint, the full run, S-GT fetched, E2 + E4 + the planted continuity test, the exhibit. Then the shelf (M5b), the experiments (Tōkoku, Kasai) and E1.
5. **M7 and M8:** integrate, README, video, a clean-clone replay check, submit.

Started at the back of the queue, not cut: the Catalogue beyond the 15 launch titles, the acquisitions agent for outside requests, the Student edition, Glimmer on Modal (the code checks run without it), covers. The Sōseki stretch text is dropped; the stretch is now guest editors (M7b).

## Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | **First calls and cost calibration** (serial, first) | A Responses API call to Spark returns schema-valid JSON, uses `prompt_cache_key` and web_search, and logs input / cached / output / reasoning tokens and $ into a spend ledger. Wonder answers once; Glimmer answers once if the Modal endpoint is up, otherwise later. Reasoning tokens at low / medium effort are measured on a 1k-char chunk, and the cost table in ARCHITECTURE §10 is updated. |
| **M1** | **Contract** (serial) | `schema.sql`, the event-type list and JSON schemas for every department output are committed. The Aozora parser round-trips 晩餐, 我牢獄, 三十三の死 and the Setsu passage (ruby, emphasis, IDs, colophon). Fixture JSON for 晩餐 (segments, a few queries, notes, a fork, events) exists. |
| M2a ‖ | **Engine core** | The runtime, budgets, response cache, carried state, Analyst, Translation and Source check run 晩餐 end to end, writing events and revisions. |
| M2b ‖ | **Reader site** | The pamphlet design ported to templates: per-book accent colour, ruby, seals and colophon, a near-black dark mode. A reader settings panel (edition, layout, what to show, a quiet preset, text size, furigana) that never loses your place. The margin variorum, two-axis reactions, comments and proposals through the model screen, labels, credits. Everything renders from the fixture. Works at phone width. |
| M2c ‖ | **House view + streaming** | The floor plan and message stream play a fake event fixture over SSE, with resume and replay at 8×. |
| M2d ‖ | **Deterministic checkers + eval harness** | Tic detector, ledger checker and length-ratio flagger (shared with the copy desk). The S0 one-shot baseline. The T1 passages chosen and frozen. Plain counting only (sentences, words, characters, lexicon hits); no NLP libraries. |
| M2e ‖ | **Catalogue** | A Glimmer vs Spark spot check on 10 works. Reader's reports generated on Meta models, the 15 launch titles first and the long-list only if time allows. Catalogue pages with evidence and date for "untranslated". "I'd read this" votes, a request form (search the Aozora index or give an outside reference) and a wanted list. Acquisitions checks outside requests and the editor confirms. |
| M2f ‖ | **Ops** | Fly deploy. Spend caps (live run / daily / total), kill switch, one-run queue, per-IP limits, invite-link auth for editor and reviewers. The replay fallback works when the house is closed. |
| **M3** | **Full pipeline on 晩餐** (needs M2a; then adds Editorial, Copy desk, Notes, Fact-check, forks, interns, rules) | One run produces queries with stet / accept / revise, ≥1 fork with verbatim dissent, ≥1 intern with a logged reason, a standing rule that propagates and skips locked lines. Cost per 1k chars is within the pessimistic figure. The run streams into M2c and renders in M2b. |
| **M4** | **Experiments + prompt freeze** | 我牢獄, 雪をんな and the Setsu passage run. The hard text's failures are written up honestly. Prompts are tagged `frozen-v1`. **Midpoint check (below).** |
| M5 ‖ | **Showcase with the editor** | The brief runs on 三十三の死 and stops at the checkpoint (`RUNNING-A-TEXT.md` §4): the editor's changes become scoped rules, ≤5 forks. The full run follows. The edition carries honest labels, an editor's note and credits. If a bilingual reader has time to check passages, those are labelled *human-reviewed*; nothing waits for it. |
| M5b ‖ | **The shelf** | After M5's full run holds: the short Catalogue titles (under ~15k characters, the 15 launch titles first) run through the house with no editor, Spark calls on the Contributor tier (approved for public-domain texts), labelled *house-checked*. Target ten or more editions; each costs a dollar or two. The first thing cut if M5 slips. |
| M6 ‖ | **Evals** | The four questions below answered, with the comparison against S-GT as the headline. The annotated side-by-side exhibit is made. Charts render on the Evals page and in the README. |
| M7b | **Guest editors** (the stretch, in place of the Sōseki text) | The editors' desk per `EDITORS-DESK.md`: start a run on a whole work with the estimate reserved first; per-editor allowances in drops; pause and resume; the edition carries the editor's name. Invite links with an allowance and a suggested short story go in the submission for judges. If this isn't built, the desk says "coming" and the house editor starts runs by hand. |
| M7 | **Integrate** | Live site: showcase, experiments, Setsu comparison, Catalogue, House (live + replay), Evals, Credits, "Where this comes from". Presets are pre-briefed (reading and bible built ahead). A live run on a preset passage succeeds three times in a row from a phone. `keikaku serve --replay` shows the recorded run from a clean clone with no key. |
| M8 | **Ship** | 3-min video, README first screen, LICENSE, a secrets scan of the full history. **The judge path (below) works from a clean clone.** A dry run of the submission form on 3 Nov; the final push and submission on 4 Nov, hours before 9 PM ET. Caps set for the judging period. |

## The judge path

What the organisers have said judges do: watch the 3-minute video, read the public repo, and run the project from its setup instructions, possibly with their own key. A hosted site is optional and nothing in the submission depends on it. So the repo must, from a clean clone:

1. **Run keyless.** `uv sync` then `keikaku serve --replay` serves the site with the recorded runs from `fixtures/`: the showcase and shelf editions, the House replaying a real run, the Evals page. No key, no network.
2. **Carry provenance.** Each recorded run in `fixtures/` is the complete event log with every model call's request hash, model, token counts, cost and response, so a judge can see the Meta calls that produced the text without re-running them. The README links a recording of the live run too.
3. **Run live with a key.** `.env.example` lists the names; with `META_API_KEY` set, `keikaku run <work>` runs a text and `keikaku serve` runs the House live, under the same caps as the hosted site.
4. **Say which Meta model does what and where it runs**, in the README's first screen: Spark and Wonder through the Meta Model API, Glimmer on Modal, Spark Open through a partner host. No licence links are required.
5. **Say how to use the hosted version**, including that it has replay mode and rate limits, and give the guest-editor invite if M7b is built.

**The video's fixed rules** (from the organisers): 3:00 at most; only what was built during the event, no slides; one opening line on what existed before the event and what was built during it; the working flow end to end with live Meta model calls visible on screen (logs or responses, not mocked); a brief segment on which part uses which Meta model; understandable in English. Content and shots are decided later.

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

**The auditor shares the house's blind spots.** Wonder also runs Source check inside the pipeline, with the same bible, so an error it can't see there it can't see in the audit either, and the comparison would flatter us. A cross-vendor judge isn't allowed (every model the repo calls must be Meta's), so the mitigation is weaker and is stated as such: Spark Open, a different checkpoint, runs the same audit on the headline set and both counts are reported side by side with their agreement; the comparison against the 1918 human translation and the deterministic checks don't depend on any judge at all. Where the auditors disagree, the page says so.

**The exhibit.** Judges can't read a novel, so the submission leads with one annotated side-by-side: one shortish passage, or three or four very short ones, with the one-shot version and ours, arrows and margin notes saying in plain words what went wrong and why ("doesn't know who *she* is: that was set up two pages earlier"; "the same word becomes three different words"; "this sentence is missing"; "makes an uneducated narrator sound well-read"). It should make sense to an engineer who reads no Japanese. Passages are picked from the audited set, and the full counts sit next to the exhibit, so it isn't cherry-picked; anywhere ours is worse is shown too.

## The evals: four questions, answered plainly

Everything here runs from the repo on Meta models or on plain counting, costs little, and exists to answer one question each. Anything that didn't answer a question a judge or a reader would ask has been cut (the long list it was cut from is in the private research notes, not here).

| | Question | How | What's shown |
|---|---|---|---|
| **E2 · accuracy** | Does the house make fewer meaning errors than what a reader uses today? | The blind span audit (`audit-spans`, Wonder, with the reading and bible) on keikaku, one-shot Spark (S0) and browser Google Translate (S-GT), on the same passages: T1 (the Setsu text and 2–3 other works with published translations, briefed whole first) and a sample of the showcase. Spark Open runs the same audit so the two auditors' agreement is reported. | Errors per 1,000 characters by type, and how many a reader of the English alone couldn't spot. **The annotated side-by-side exhibit** is built from these passages. The headline. |
| **E-ref · against a human** | How far are we from a published human translation? | The same audit on Setsu 1918 as a floor (an auditor that finds many errors in it is noisy, and we say so), and keikaku and S-GT shown beside it, one passage in full. | One chart, one passage. The honest bar where the human wins. |
| **E4 · voice** | Does it still read like default model English? | Three counts, no models: tic rate per 1,000 words from a lexicon; spread of sentence lengths against the Japanese's; length ratio by position. On S0, S-GT, keikaku and the 1918 text. | One small chart |
| **E-long · continuity** | What does reading the whole book buy? | (a) The planted test: ten known inconsistencies injected into a copy of the showcase; what one Wonder whole-text read catches against what the chunked check catches. (b) Whole source in the prefix on or off, on the showcase, measured by the ledger checker and E2. | A catch-rate table; one pair of numbers |

Secondary, reported with its caveat: **E1**, pairwise preference by a jury of Wonder, Glimmer and Spark Open, both orders, keikaku against S0 and S-GT. Same-family judges reward fluent drift, so this never leads; its order-flip rate is reported next to it as the calibration.

Not done unless there's time at the end: the translate–reflect–revise loop as a second baseline (S1); the per-stage ablation from the M5 snapshots (which department earned its keep).

**When:** S0 and S-GT on the dev passages after M0, to tune the auditor on real one-shot errors. Everything else after the M4 prompt freeze, on frozen test passages. All numbers frozen before the video is recorded. **No eval depends on a human rater**; if a bilingual reader does blind pairs, that's reported separately as a bonus.

**Passages are never translated cold.** For every T1 work the brief runs on the whole text (a few whole-text calls, mostly cached input, under a dollar for a 30k-character work) and only then are the passages drafted, with the real reading and bible. Setsu's 「思い出の記」 is 30.7k characters, so it's run whole if the budget holds, which gives a whole-work comparison. S0 and S-GT get the passage alone, which is exactly the difference being measured.

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
1. Guest editors (M7b); the house editor's desk stays.
2. Muse Image covers (typographic covers instead).
3. The Student edition (keep Casual + Curious).
4. E-long (b), the prefix on/off comparison (keep the planted test).
5. The Catalogue cut to 30 reports; the Acquisitions agent for outside requests (requests are still collected, and the editor checks them by hand).
6. Proposals (keep reactions).
7. Live runs on arbitrary Aozora cards (presets only), then replay-only House.
8. Live interns (keep them in the recorded run).

**Never cut:** the showcase with honest labels, Source check, E2 and E4, the planted continuity test (the cheapest legible proof of what Wonder's whole-text read adds), the S-GT comparison and its exhibit, the House replay, the video.
