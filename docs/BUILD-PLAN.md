# Fortleben — build plan

Written 27 Oct 2026, the second day of the hackathon; updated 28 Oct with the final text picks and design direction. The work is in dependency order. **‖** marks lanes that can be built at the same time. Lanes code against the M1 contract (schema, event types, fixtures), not against each other.

## Where we are, 30 Oct

Nothing is built yet: the repo holds plans. Five days remain, and the last push has to be in by the evening of 4 Nov UK time. So the order below is the order, with the thinnest working path first and everything else added only once it runs:

1. **M0 and M1** (serial, now). M0 needs `public/.env` with `MODEL_API_KEY` (Meta's own name for it) and `uv` installed.
2. **The minimal pipeline** (`STAGES.md`: parse, first read, bible, draft, source check, answer, code checks, notes, release) on 「晩餐」, writing events; the site and House view rendering the fixture in parallel (M2b, M2c), deploy (M2f).
3. **M3:** the remaining stages, forks, interns, rules. Midpoint check at the end of 1 Nov.
4. **M5 and M6:** the showcase brief and checkpoint, the full run, S-GT fetched, the audit and the exhibit, the planted continuity test. Then the shelf (M5b) and the other texts (Tōkoku, Kasai).
5. **M7 and M8:** integrate, README, video, a clean-clone replay check, submit.

**The first session, concretely (M0 then M1):**
- `uv init` in `public/` with Python 3.12 pinned; the layout in `CONVENTIONS.md`; `.env.example` with `MODEL_API_KEY=`; pytest wired up.
- `house/client.py`: one call to `muse-spark-1.3` on the Responses API with a strict JSON schema, `prompt_cache_key` and `prompt_cache_retention: "24h"`, logging input / cached / output / reasoning tokens and dollars from `usage` into the spend ledger; the response cache keyed on (model, prompt hash, input hash); `FakeClient`. One call each to `muse-wonder-1.0` and, with web search, to Spark. Measure reasoning tokens at low and medium on a 1k-character chunk and update the cost table in `ARCHITECTURE.md` §10.
- `house/lang/ja/`: fetch and parse the four demo texts from Aozora (「晩餐」, 「我牢獄」, 「三十三の死」, 「思い出の記」), round-trip tests, paragraphs with IDs, scene breaks, ruby, gaiji, colophon.
- `db/schema.sql`, `house/events.py`, `house/schemas/` for the seven minimal-pipeline prompts, and a fixture for 「晩餐」 (segments, a few queries, notes, a fork, events) so the site and House lanes can start.
Then the minimal pipeline on 「晩餐」, stage by stage, stopping after each to read the output. The one design question that run settles: whether the sentence-level referent map earns its place (`STORY-STATE.md` §1); the same pages are drafted with and without it.

What to translate is being settled separately; it only matters at M5. The engine is built and tuned on 「晩餐」 whatever the showcase turns out to be, and the exhibit's comparison texts come at M6.

Started at the back of the queue, not cut: the Catalogue beyond the 15 launch titles, the acquisitions agent for outside requests, the Student edition, Glimmer on Modal (the code checks run without it), covers. The Sōseki stretch text is dropped; the stretch is now guest editors (M7b).

## Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | **First calls and cost calibration** (serial, first) | A Responses API call to Spark returns schema-valid JSON, uses `prompt_cache_key` and web_search, and logs input / cached / output / reasoning tokens and $ into a spend ledger. Wonder answers once; Glimmer answers once if the Modal endpoint is up, otherwise later. Reasoning tokens at low / medium effort are measured on a 1k-char chunk, and the cost table in ARCHITECTURE §10 is updated. |
| **M1** | **Contract** (serial) | `schema.sql`, the event-type list and JSON schemas for every department output are committed. The Aozora parser round-trips 晩餐, 我牢獄, 三十三の死 and the Setsu passage (ruby, emphasis, IDs, colophon). Fixture JSON for 晩餐 (segments, a few queries, notes, a fork, events) exists. |
| M2a ‖ | **Engine core** | The runtime, budgets, response cache, carried state, Analyst, Translation and Source check run 晩餐 end to end, writing events and revisions. |
| M2b ‖ | **Reader site** | The pamphlet design ported to templates: per-book accent colour, ruby, seals and colophon, a near-black dark mode. A reader settings panel (edition, layout, what to show, a quiet preset, text size, furigana) that never loses your place. The margin variorum, two-axis reactions, comments and proposals through the model screen, labels, credits. Everything renders from the fixture. Works at phone width. |
| M2c ‖ | **House view + streaming** | The floor plan and message stream play a fake event fixture over SSE, with resume and replay at 8×. |
| M2d ‖ | **Checkers + the exhibit harness** | Ledger checker and length-ratio flagger (shared with the copy desk). The S0 one-shot baseline. The audit prompt and the exhibit renderer (two or three columns, arrows, margin notes) working on fixture text. The S-GT passages fetched and dated. |
| M2e ‖ | **Catalogue** | A Glimmer vs Spark spot check on 10 works. Reader's reports generated on Meta models, the 15 launch titles first and the long-list only if time allows. Catalogue pages with evidence and date for "untranslated". "I'd read this" votes, a request form (search the Aozora index or give an outside reference) and a wanted list. Acquisitions checks outside requests and the editor confirms. |
| M2f ‖ | **Ops** | Fly deploy. Spend caps (live run / daily / total), kill switch, one-run queue, per-IP limits, invite-link auth for editor and reviewers. The replay fallback works when the house is closed. |
| **M3** | **Full pipeline on 晩餐** (needs M2a; then adds Editorial, Copy desk, Notes, Fact-check, forks, interns, rules) | One run produces queries with stet / accept / revise, ≥1 fork with verbatim dissent, ≥1 intern with a logged reason, a standing rule that propagates and skips locked lines. Cost per 1k chars is within the pessimistic figure. The run streams into M2c and renders in M2b. |
| **M4** | **The other texts + prompt freeze** | 我牢獄, 雪をんな and 思い出の記 run. The hard text's failures are written up honestly. Prompts are tagged `frozen-v1`. **Midpoint check (below).** |
| M4b | **Translation re-check** | Every text to be published (showcase, shelf, the other texts) searched again for existing translations, including fan and blog ones, dated; any found is credited and linked on the work's page. 「晩餐」 already has one (M Skeels, 2020) and stays as the development text. |
| M5 ‖ | **Showcase with the editor** | The brief runs on 三十三の死 and stops at the checkpoint (`RUNNING-A-TEXT.md` §4): the editor's changes become scoped rules, ≤5 forks. The full run follows. The edition carries honest labels, an editor's note and credits. If a bilingual reader has time to check passages, those are labelled *human-reviewed*; nothing waits for it. |
| M5b ‖ | **The shelf** | After M5's full run holds: the short Catalogue titles (under ~15k characters, the 15 launch titles first) run through the house with no editor, Spark calls on the Contributor tier (approved for public-domain texts), labelled *house-checked*. Target ten or more editions; each costs a dollar or two. The first thing cut if M5 slips. |
| M6 ‖ | **The exhibit** (a deliverable) | The exhibit component renders passage pairs with anchored margin notes and arrows, on the site and as a recordable view. The audit run on the showcase in all versions; the editor has struck what the auditor got wrong; the exhibit is built from the best passages, with the full list under it, and one passage is in the README as an image. Extras only after that: the planted continuity test, the era guess. |
| M7b | **Guest editors** (the stretch, in place of the Sōseki text) | The editors' desk per `EDITORS-DESK.md`: start a run on a whole work with the estimate reserved first; per-editor allowances in drops; pause and resume; the edition carries the editor's name. Invite links with an allowance and a suggested short story go in the submission for judges. If this isn't built, the desk says "coming" and the house editor starts runs by hand. |
| M7 | **Integrate** | Live site: showcase, the other texts, Setsu comparison, Catalogue, House (live + replay), the Exhibit, Credits, "Where this comes from". Presets are pre-briefed (reading and bible built ahead). A live run on a preset passage succeeds three times in a row from a phone. `keikaku serve --replay` shows the recorded run from a clean clone with no key. |
| M8 | **Ship** | 3-min video, README first screen, LICENSE, a secrets scan of the full history. **The judge path (below) works from a clean clone.** A dry run of the submission form on 3 Nov; the final push and submission on 4 Nov, hours before 9 PM ET. Caps set for the judging period. |

## The judge path

What the organisers have said judges do: watch the 3-minute video, read the public repo, and run the project from its setup instructions, possibly with their own key. A hosted site is optional and nothing in the submission depends on it. So the repo must, from a clean clone:

1. **Run keyless.** `uv sync` then `keikaku serve --replay` serves the site with the recorded runs from `fixtures/`: the showcase and shelf editions, the House replaying a real run, the Exhibit. No key, no network.
2. **Carry provenance.** Each recorded run in `fixtures/` is the complete event log with every model call's request hash, model, token counts, cost and response, so a judge can see the Meta calls that produced the text without re-running them. The README links a recording of the live run too.
3. **Run live with a key.** `.env.example` lists the names; with `MODEL_API_KEY` set, `keikaku run <work>` runs a text and `keikaku serve` runs the House live, under the same caps as the hosted site.
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

## The exhibit: the deliverable, not a benchmark

Translation is an art, and the honest way to show one translation is better than another is the way an editor or a reviewer does it: put them next to each other and point. So **the exhibit is a deliverable of the project, on a par with the showcase edition**: a set of short passages with the one-shot machine version beside ours, and margin notes with arrows saying in plain words what went wrong and why. It lives on the site, and the same component, recorded, is the material the video uses (the highlighted notes, not whole passages). Anything that looks like an evaluation study is extra, done only if there's time, and dropped without regret.

It's built as one reusable thing: a passage pair (or triple, with the 1918 human translation) plus anchored notes, each with a category, a one-line reason and the span it points at. The site renders it as margin notes with arrows; the video records that render. Judges see the same artefact in the README (one static image of one passage), on the site and in the video.

**What a reader uses today** is the baseline: the same passage pasted into browser Google Translate (S-GT, fetched by hand and dated), and one-shot Spark with a bare prompt (S0), so it's also clear what the house adds over the model alone. The copy says "a one-shot machine translation" and puts the method in a footnote.

**The first panel is the page, not the text.** What a reader gets today is the Aozora page with the browser's "translate this page" clicked: ruby mangled into the line, the colophon rendered as nonsense, dialogue run together, names changing between screens, nothing to tap. The exhibit opens with one dated screenshot of that beside the same passage in the Fortleben reader. No arrows; the difference is the whole page. The annotated passages below it then show why the text itself is better, which is what the rubric scores. The same pair is the README's first image.

**The exhibit.** Three or four short passages from the showcase, and one or two with a public-domain human translation as a third column: Setsu's 「思い出の記」 against Hisada and Johnson (1918), and Sōseki's 「坊っちゃん」 against Morri (1918), the one Japanese novel a judge might recognise. Botchan is famous and much translated, so before a passage is used we check that the one-shot output doesn't echo a published translation (a sanity check, not a result): a direct comparison against Morri, which we hold in full, and exact-phrase searches of eight to ten distinctive sentences in Google Books against the copyrighted translations, which answer even without showing the page. We avoid the famous opening, take a mid-book passage, and swap the passage on any hit. The page says what was checked and how; its brief on the whole text costs a few dollars rather than cents. For each: the one-shot version, ours, and **margin notes with arrows, in plain words an engineer who reads no Japanese can follow**. The kinds of thing the notes point at:

- a name translated when it should have stayed a name, or a term rendered three different ways across the text;
- doesn't know who *she* is: that was settled two pages earlier;
- a sentence missing, or one added to explain what the author left implicit;
- an anachronism, or the wrong period: a 1914 narrator in 2020s English;
- model tics: the padded triplet, "not X but Y", the abstract noun where the author gave an image;
- flat tone: the emotion or the irony gone, so the meaning goes with it;
- a deliberate repetition "varied" away;
- and, where it's true, **a place where ours is worse**, or where the 1918 translator does something neither machine managed.

**How it's made.** The notes aren't written by hand from scratch and they aren't cherry-picked. Wonder reads each version against the Japanese with the house's reading and story bible (`audit-spans`), marks every problem it finds with a one-line reason in those categories, on the one-shot versions and on ours alike, blind to which is which; Spark Open does the same pass so the two can be compared. The editor reads the marked-up passages, strikes anything the auditor got wrong (and says so on the page), and the exhibit is built from the passages with the most to teach. Under the exhibit sits **the whole list** for the whole showcase: every problem marked in each version, with its reason, so the exhibit can be checked against the full picture. One plain sentence sums it up ("across the whole story the auditor marked N problems in the one-shot and M in ours; the list is here"). That's the only number, and it's a count of the notes, not a metric.

**The one test that's about the engine, not the text:** does the final read actually see across the whole book? Take our finished translation of the showcase and deliberately break it in ten places a page-by-page check can't see: a character's name rendered differently in a later chapter, who spoke a line, an object that changed colour, an age, a day of the week. Run the final read over the broken copy and see how many of the ten it catches. One sentence in the README ("the whole-text read caught 9 of 10 planted continuity breaks") and the ten listed. It needs someone who can read the Japanese to plant them well, about twenty minutes, late in the week; if that time doesn't exist, it's dropped, not faked.

**Small experiments, kept only if they work.** Run once the exhibit passages exist; each is a few calls; any that doesn't separate the versions cleanly is dropped and the page says it was tried.
- *The blind era guess.* Give a model a passage of English with no context and ask when it was written, where, who is narrating, and whether it's a translation. Run on the one-shot, ours and the 1918 text. Useful if the one-shot reads as contemporary marketing English and ours as an early-twentieth-century first-person account; it also catches the opposite failure, fake period pastiche. Useless if the names give the game away for all three.
- *Others as they occur*, under the same rule: plain words, a reader would care, no counting of things readers don't notice.

**Passages are never translated cold.** For every passage, including the Setsu one, the house's brief runs on the whole text first (a few whole-text calls, mostly cached input, under a dollar for a 30k-character work) and only then is the passage drafted, with the real reading and bible. Setsu's 「思い出の記」 is 30.7k characters, so it's run whole if the budget holds. One-shot and Google Translate get the passage alone, which is exactly the difference being pointed at.

**What's not done:** model juries, preference votes, sentence statistics, ablation grids. The research behind the house considered them; none of them shows a judge or a reader anything the exhibit doesn't show better. The planted test and the small experiments above are the only extras, and they're extras. **No human rater is required**; if a bilingual reader does look at the exhibit, their notes go on the page with their name.

## Midpoint exit check (end of 1 Nov)

These must be true:
1. M3 is done: a real end-to-end run on 晩餐, within the pessimistic cost.
2. A real run streams into the House view.
3. The reader site renders 晩餐 from the database in two editions.
4. The showcase is parsed, its story bible built, and its style sheet drafted.
5. Credit spend is ≤ $45.

**If 1 or 2 fails:** fall back to the minimal pipeline (Analyst → Translation → Source check → Copy desk → Notes). Interns and forks then appear only in the recorded run.
**If more than two items fail:** stop adding, ship the showcase and the exhibit, and cut from the list below.

## Cut list (cut from the top)
1. Guest editors (M7b); the house editor's desk stays.
2. Muse Image covers (typographic covers instead).
3. The Student view (keep Casual + Curious).
4. The Setsu column of the exhibit (keep the showcase passages).
5. The Catalogue cut to 30 reports; the Acquisitions agent for outside requests (requests are still collected, and the editor checks them by hand).
6. Proposals (keep reactions).
7. Live runs on arbitrary Aozora cards (presets only), then replay-only House.
8. Live interns (keep them in the recorded run).

**Never cut:** the showcase with honest labels, Source check, the exhibit (passages side by side with arrows and margin notes), the House replay, the video.
