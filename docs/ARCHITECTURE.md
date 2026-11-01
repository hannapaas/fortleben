# keikaku — architecture

Written 27 Oct 2026, the second day of the hackathon; updated 28 Oct with the final text picks. The plan, not yet the code: sections change as the build proves or disproves them. See `CONCEPT.md` for what it's for and `BUILD-PLAN.md` for the order of work.

Design choices worth knowing first:
- **Built per source language, Japanese first.** `work.language` is a field; a text enters through a source adapter (Aozora is the first); the bible, departments and site are language-neutral; anything Japanese-specific (the Aozora parser, ruby and furigana, the honorific policy, `fugashi` for stats) sits in `house/lang/ja/`. Nothing else assumes Japanese.
- **Source check runs on Wonder for every chunk**, not only on hard passages. It's affordable (§10), and same-model critique does most damage in exactly this department.
- **Views share one base text**: one English per paragraph with controlled tokens, not three separate translations. (Work → edition → view: `CONCEPT.md`, "Words".)
- **The catalogue's reader's reports are generated on Meta models.**
- **Glimmer works only on the English** unless a spot check shows it reads Japanese well. Its model card doesn't list Japanese.

## 1. Departments and flow

No manager agent. A deterministic orchestrator (plain code, a state machine per chunk) moves *text + open queries* between departments. Translation **owns** the English. Everyone else raises queries (`open → answered → accepted | stet | revised`). Department heads **select, never merge**, and send forks up with dissent quoted word for word.

```mermaid
flowchart TD
  ACQ["Acquisitions<br/>readers' reports + rights check"] --> P{{"Editor: provenance"}}
  P --> PARSE["Aozora parser (code)<br/>ruby, IDs, colophon"]
  PARSE --> BG["Background brief · Spark + web_search"]
  BG --> RDG["First read · Wonder<br/>the house's reading, from the crux"]
  RDG --> CX["Crux check · Spark, independent<br/>same crux, or the first fork"]
  CX --> AN["Analyst · Spark<br/>story bible: cast, ledger, referent map,<br/>narration, motifs, style sheet, hard spots, tiers"]
  AN --> VT["Voice trial · Spark ×2–3, checked by Wonder;<br/>head selects"]
  VT --> CP{{"Editor: checkpoint<br/>crux, reading, voice, key bible choices"}}
  CP --> TR["Translation desk · Spark — OWNER<br/>draft page by page; 2nd draft on tricky/hard paragraphs"]
  TR -->|"draft"| SC["Source check · Wonder<br/>every paragraph, every diff"]
  SC -->|"queries"| TR
  TR --> EL["Editor's letter · Wonder, English only<br/>the whole draft against the reading"]
  EL -->|"notes"| TR
  TR --> ED["Editorial · Spark, English only<br/>a scene at a time"]
  ED -->|"span queries"| TR
  TR --> CD["Copy desk · code + Glimmer<br/>ledger, callbacks, length, tics"]
  CD -->|"queries"| TR
  TR --> NE["Notes · Spark<br/>per edition, anchored"]
  NE --> FC["Fact-check · Spark + web_search<br/>cite or kill"]
  FC --> FR["Final read · Wonder<br/>whole, then against the source: seams, drift, crux, continuity"]
  FR -->|"queries"| TR
  TR -. "forks + verbatim dissent" .-> EIC{{"Editor: forks, standing rules, locks"}}
  EIC -. "rules (scoped)" .-> TR
  FR --> QC["Proof/QC (code)"] --> ED3["Views: Casual · Curious · Student"]
  ED3 --> RD["Reader desk<br/>reactions, proposals"]
  RD -. "queries by reason" .-> SC & ED & FC
```

**The exact order of stages, what each call takes and returns, and the limits code enforces are in `STAGES.md`; that list is what the orchestrator implements.** How a whole text moves through it (passes, difficulty tiers, the allowance per manuscript sheet, and what gets cut when money is short) is in `RUNNING-A-TEXT.md`. Rounds are capped at two per query. If it's unresolved after that, it goes to the editor as a fork with a one-line trade-off per option (at most 5 forks per checkpoint, global ones first). Critics edit **flagged spans only** and may answer "none". The English-only pass never sees the Japanese, and every change it makes goes back through Source check. Sensitivity flags (dated or harmful content in the source) are a query type routed to the editor. They lead to context notes, never bowdlerising.

## 2. Data model (SQLite)

| Table | Holds |
|---|---|
| `work` | Aozora card, full colophon, rights record (death year, 初出, translation search + date), status |
| `bible` | The story bible and the house's reading per work, as versioned JSON (`STORY-STATE.md`); each version points at the event that changed it |
| `author_file` | Per author: what the house learned across their works, each entry with its provenance (`STORY-STATE.md` §1a) |
| `segment` | Paragraphs `p12` from the source, Japanese with structured ruby, with sentence anchors `p12-s3` inside them for queries and notes. **The paragraph is the unit of English** (`STAGES.md`); which English renders which sentence is best-effort metadata the drafter returns, not a constraint on it |
| `revision` | Base English per paragraph, versioned, with the drafter's sentence spans. Each revision points at the event that caused it (draft, accepted query, rule, human edit) |
| `term` | Ledger: entity, reading, rendering per edition (Casual / Curious / Student), first-use note. Base text carries `{t:genin}` tokens, so **editions are presentations of one base text**, checked once |
| `note` | Anchor, editions it shows in, body, sources[], status `verified / unverified / killed`, author (department or person). Student hides anything unsourced |
| `query` | From → owner, span, category, reason, evidence[], recommendation, verbatim dissent, status, resolver |
| `fork` | Options (author + one-line trade-off), head's pick, the editor's decision, the rule it created |
| `rule` | Standing rule text, **explicit scope** (line / character / term / work / author / house), origin, lines it touched |
| `lock` | Segment, who locked it. Rules don't rewrite locked lines; they raise a query to the editor instead |
| `status` | Per segment: draft / house-checked / editor-approved / human-reviewed, plus who. Nothing waits on the last two |
| `event` | Append-only log: run, seq, actor (department + role, or person), type, payload, cost. The single source for history, the House stream and replay |
| `call` | Model, effort, tokens (input / cached / output / reasoning), $, prompt hash, cache key |
| `intern` | Department, brief, logged reason, budget, spend, report |
| `allowance` | Per editor: drops granted, reserved, spent; every grant with its reason (invite, funding target, house) |
| `reaction`, `proposal`, `person` | Two-axis reactions on a target (paragraph, note, or an alternative in a debate), with their counts never used to order or change anything; span proposals that become queries; trust level and how each person wants to be credited |
| `report` | Catalogue reader's report: reader-facing fields, internal scores, what it was based on, label, translation-status evidence and date |
| `edition` | One translation of a work: the editor (a person, or the house), its runs, current release |
| `release` | Edition version (v1, v1.1), changelog, credits |
| `vote` | "I'd read this": work, voter token (cookie + IP hash), date. One per voter per work |
| `request` | An Aozora work ID or an outside reference (title, author, link), the requester's reason (screened), the Acquisitions verdict (*eligible / in copyright / can't tell*) with evidence, the editor's decision, status |

### The margin: how the debate reaches the page

Nothing is collected for the margin specially; it falls out of the record. Every query, answer, fork, ruling, rule application, note, intern report and revision is stored with an anchor: a paragraph ID, and a span inside it where there is one. The reader's margin for paragraph `p12` is simply everything anchored to `p12`, in time order, rendered by kind: the critic's query with its evidence, the translator's answer, the head's pick or the fork with both cases, the editor's ruling and the rule it made, the alternatives the drafter left, the notes with their sources, and the revision history. Each agent's one-sentence `say` is the plain-words line at the top of its entry. A paragraph nobody queried shows *drafted · checked · no queries* and nothing else. So the margin is a database read, the same read the House replay and the editor's desk use, and it is complete by construction: there is no way for a decision to happen that isn't anchored somewhere.

## 3. Agent runtime

- Python `asyncio`, with the OpenAI SDK pointed at Meta's API on the **Responses API** (needed for caching hints, web_search and reasoning summaries). No agent framework.
- A department is a module: prompt files, a strict JSON schema, and `run(task, state) → queries | edits | notes`. Every output schema has a `say` field, one plain sentence for the House log. Muse never exposes its reasoning, so the visible debate *is* what the agents write.
- **Prompts teach principles; code enforces limits.** A department prompt explains what the job is for and why (fidelity over fluency, keep deliberate ambiguity, raise a query only when it matters), so the agent can make a sensible call on a case nobody foresaw. Absolute "always / never" lines are kept for the few things that are crucial, because models follow them literally even where they stop making sense. Anything that must hold no matter what (the spend cap, two rounds per query, output schemas, locked lines) is enforced by the orchestrator, not by the prompt. Prompts stay short as a result.
- The model client has a `FakeClient` that serves recorded responses from `fixtures/`, so the site, the House view and the tests run with no key. A paragraph gets at most three revision cycles per run; after that it's *flagged, unresolved* rather than argued over again.
- Translation runs chunk by chunk in order, because the state is carried forward. Other departments work behind it in parallel, under a concurrency semaphore. 429s and 5xx get retries with backoff.
- **A response cache** keyed on (model, prompt hash, input hash) makes reruns in development free and replays deterministic.
- **Standing-rule propagation:** a scoped search (ledger plus regex, then a cheap Spark classifier on the candidates) finds the affected segments. Translation revises them as queries. The UI shows "R4 · 12 lines, 2 locked lines sent to the editor".

## 4. Which model does what

| Job | Model | Why |
|---|---|---|
| Analyst, translation, editorial, notes, query answers | `muse-spark-1.3`, effort medium for drafting, low elsewhere, minimal for classifiers (rule scope, crux comparison); reasoning can't be switched off. `prompt_cache_key` per work + style-sheet version, `prompt_cache_retention: "24h"` | Strong and cheap. The stable prefix caches at 88% off |
| First read (the house's reading); Source check (every chunk, every diff); critic at forks; whole-text continuity read | `muse-wonder-1.0`, effort low (medium for the first read) | A different and stronger checkpoint from the drafter. The 1M context holds the whole source and translation in one call |
| Copy desk (English-side tics, register, consistency) | Muse Glimmer 30B hosted on Modal ($30 of credits, a listed partner, so the open-weight bonus can be verified) for the recorded runs and the live site; the laptop is too slow to rely on. Until the Modal endpoint exists the code checks run alone | Open weights, near-free. Proposes replacements for flagged spans; never writes the base text |
| Fact-check | Spark + `web_search` | Every note cites a source or dies |
| Catalogue | Spark low as the acquisitions editor; Glimmer as chunk reader if it passes a 10-report spot check, else Spark | Cheap at 200 reports |
| Requests from outside Aozora | Spark low + `web_search`: author dates, first publication, existing English translations; a short reader's report if a text is found | Capped per day; the editor confirms every verdict |
| Covers | `muse-image-1.0` | Decorative, $0.01 each. Cut first |

**About the shared lineage:** Glimmer is distilled from Spark, and Spark Open is Spark released as open weights. Wonder is a different, larger model but from the same family. So "a different model as critic" here means a different checkpoint, not independence, and the README will say so. **Every model this repo calls is a Meta model**, in the product and in the exhibit's audit alike: the hackathon's rule is strict (a participant's own tiny checker was ruled out), and the audit runs from this repo. So the auditor behind the exhibit is Wonder, cross-checked by Spark Open (open weights, run on any host), two checkpoints of one family, and the page says so. What's independent of any model is the editor's read of the marked-up passages, the 1918 human translation in the exhibit, and the deterministic checks.

## 5. Interns

When a head meets something no department covers (an embedded poem, a dialect line, a classical quotation, a Buddhist term, a period object), it can ask for an intern: one research question with a reason. A real house would ring a specialist reader. Here the intern is a single Spark call at low effort with web search that returns a short report with sources; the head then continues with the report in hand. Interns never edit text and never hire.

**Mechanics, no tool calls.** The head's output schema has an optional `needs_intern: {question, reason}`. If it's set, the orchestrator checks the caps, runs the `intern` prompt, and re-runs the head with the report added to its input. Two plain calls instead of a tool call inside a structured-output call, which the API makes awkward (`tool_choice` is `auto` only). It replays from the cache like everything else.

**The runtime enforces:** one level only; at most 3 interns per run; $0.10 per department per run; a report, never edits; first thing given up when the pool runs low. The reason is logged and shown; in the House an intern is a dotted square attached to its department. Typical triggers are the Analyst's hard-spot flags. We make no quality claim for them; they're shown, not scored.

## 6. Long context

The full design is in `STORY-STATE.md`. In short:

- **Pages** of about 1K source tokens, never splitting a paragraph.
- **The whole source sits in the cached prefix** for every text we run (all under ~30k characters). At $0.15 per million cached tokens, 24k tokens cost about $0.004 a call. So the model can look anywhere in the book, and the bible carries the decisions.
- **Look-ahead:** each call also sees the next paragraph of Japanese, read-only, because Japanese often resolves a subject or speaker after the fact.
- **Prompt order** (stable first, so it caches): house rules and department prompt; reading and bible; whole source; voice reference; the previous two paragraphs; the page with the analyst's speaker and subject notes.
- **Rule changes** bump the style-sheet version, which bumps the cache key, so rules are batched at the checkpoint.
- **Continuity** is checked in the final read, one Wonder call over the whole source and translation; the planted test (`BUILD-PLAN.md`, "The proof") measures what that catches.
- Novels, where the whole source can't sit in the prefix, are a later design (`STORY-STATE.md` §5).

## 7. Showing the house at work

Every event is written to `event`, and that record is what the House, the margin and the fixtures read. Event types: `call.started`, `agent.say`, `draft.paragraph`, `query.raised/resolved`, `fork.opened`, `intern.hired`, `budget.tick`, `rule.applied`, `run.done`.

**The House is a walkthrough of one finished run, not a live feed** (`SITE.md`, `/house`). It draws the text's route through the stages, shows a few picked moments at each stage, and opens any stage's full output. The engine flags candidates (queries, forks and rulings, large revisions, interns); the picks are a short list of event IDs, each with a one-line reason, and the page labels them as picked. Visitors can't start runs, so there's nothing to stream to them. Watching an editor's run live (Server-Sent Events read from the same log) is a later addition and the demo doesn't need it.

## 8. Stack, hosting, abuse

- **Stack:** Python 3.12 + FastAPI + SQLite (WAL) + Jinja templates. The front end is vanilla JS and CSS, with no build step. `uv` for packaging; pytest. One language serves the engine, the exhibit harness and the site. **No non-Meta ML model runs anywhere in the repo.**
- **Hosting:** one Fly.io machine plus a volume for SQLite (daily snapshots), with secrets in Fly. Prompts and keys stay on the server; the browser only ever receives events, text and notes.
- **Spend:**
  - Every call is priced from `usage` into a spend ledger.
  - A pre-call estimate is checked against the run's reservation, a daily global cap ($10 during judging) and a total cap.
  - Meta's spend-limit notification is a backstop, not a stop.
  - A `HOUSE_OPEN=false` kill switch. When the house is closed or a cap is hit, runs pause and resume later (`EDITORS-DESK.md`); the site itself carries on.
- **Abuse:**
  - Visitors can't start runs. Only editors can, through invite links, on works from the eligible index, with the estimate reserved first. No free paste, so we're not a free translation proxy and there's no copyright risk.
  - Reactions are rate-limited by cookie and IP. Comments and proposals are screened by a model, published if they pass, removable by the editor, flat with no reply threads, capped per day, with a takedown contact.
  - Editor and reviewer powers come through signed, revocable invite links. No passwords.

## 9. What's in this repo

Everything the demo needs runs from this repo: the engine, orchestrator, schemas, the department prompts the demo uses, the demo texts' style sheets and voice briefs, a sample tic list, the Aozora parser, the UI, the exhibit harness, results and raw verdicts, and replay fixtures. An optional private overlay (`KEIKAKU_PRIVATE_DIR`) can add voice profiles for other authors and longer word lists; the demo never depends on it. Copyrighted human translations used in evals are quoted in short excerpts only and never committed whole.

## 10. Cost model

**Assumptions:**
- Japanese source: 1.5 tokens per character.
- English: 0.6 tokens per source character.
- Stable prefix ~5k tokens, 80% of it cached.
- **Reasoning is billed as output.** Base case: medium effort ≈ 2× visible output, low ≈ 1k tokens per call (Wonder 1.5k). **Pessimistic: double the reasoning.** The first calls (M0) measure the real ratio, and this table gets updated.

**Measured at M0, 1 Nov** (`keikaku calibrate`, 「晩餐」, the whole text in the input, drafting p1–p8, 1,055 characters, with no reading or bible yet):

| Call | Input | Cached | Output | of which reasoning | Reasoning ÷ visible | $ |
|---|---|---|---|---|---|---|
| Spark draft, low | 6,046 | 0 | 3,793 | 621 | 0.20 | 0.024 |
| Spark draft, medium | 6,046 | 0 | 6,925 | 2,533 | 0.58 | 0.037 |
| Spark + web search (8 searches), low | 56,278 | 44,853 | 2,798 | 512 | 0.22 | 0.053 |
| Wonder crux check, whole text, low | 4,070 | 0 | 1,335 | 557 | 0.72 | 0.043 |

What it changes: reasoning is far cheaper than assumed (medium ≈ 0.6× visible, not 2×; Wonder low ≈ 550 tokens, not 1.5k). Visible output is far larger: the draft returned ~3–4k visible tokens for 1,055 characters, against the 630 assumed, because sentence spans repeated the English and every paragraph carried notes. Spans now anchor by first words. Drafting at medium is ≈ $0.035 per 1,000 characters, about 1.6× the base row below; Wonder is ≈ $0.013 per 1,000 characters of a whole-text read at low effort, about a third of the assumption. Web search is dominated by the search results fed back as input (56k tokens), not by the $2.50 per 1,000 searches. **Strict JSON schemas switch prompt caching off**: with `strict: true` two calls sharing a 3.7k-token prefix got no cache hit; with `strict: false` the second got 3,697 cached. So the client sends the schema non-strict (the output still follows it) and validates every response itself, with the one retry. The rows below stand until the first full run on 「晩餐」 (M3) replaces them.

Prices per million tokens (in / cached / out): Spark $1.25 / $0.15 / $4.25; Wonder $4 / $0.20 / $20; Glimmer hosted ≈ $0.30 / $0.04 / $1.20; web_search $2.50 per 1k searches.

| Full pipeline, per 1,000 Japanese chars | Base | Pessimistic |
|---|---|---|
| First read, Analyst, summaries, continuity read (amortised) | $0.015 | $0.025 |
| Translation lead draft + second drafts on ~20% of chunks | $0.022 | $0.035 |
| **Source check, Wonder, draft + diffs** | **$0.068** | **$0.12** |
| Editor's letter (Wonder, whole draft) + Editorial + copy desk | $0.025 | $0.04 |
| Notes + fact-check (with search) | $0.022 | $0.035 |
| Query answers, heads, interns | $0.010 | $0.02 |
| **Total** | **≈ $0.16** | **≈ $0.27** |

The English-alone side (editor's letter, Editorial) got more and notes got less on 30 Oct: for an edition that's pleasant to read, the revision without the source matters more than another note. The first read (one Wonder call at medium effort over the whole text, plus Spark's independent crux read) adds roughly $0.015 base / $0.025 pessimistic per 1,000 chars on top of the first row; the background brief and the voice trial are fixed costs of a few cents per text. The per-text table below hasn't been rescaled for these; M0 replaces all of these figures anyway.

| Text | Chars | One full run (base / pessimistic) | Planned spend |
|---|---|---|---|
| Shiraki Shizu 「晩餐」 (development text) | 3,400 | $0.54 / $0.92 | 5 tuning runs, inside "dev" below |
| Kitamura Tōkoku 「我牢獄」 (the hard text) | 4,500 | $0.72 / $1.22 | 3 runs: $2.2 / $3.6 |
| Kasai Zenzō 「雪をんな」 (plain control) | 3,200 | $0.51 / $0.86 | 3 runs: $1.5 / $2.6 |
| Koizumi Setsu 「思い出の記」 (vs its 1918 translation) | 30,700 whole; the brief always runs on the whole text | $4.9 / $8.3 whole; ~$0.9 / $1.5 for three windows after the brief | 1 whole run if the budget holds, else windows |
| **Showcase (provisional, 1 Nov): Nagatsuka Takashi 「炭燒のむすめ」** | 8,000 | **$1.28 / $2.16**; ~$3.1 at the rate the first real run on 「晩餐」 measured | 2 runs + rule reruns: $3.8 / $6.5 |
| Stretch: Natsume Sōseki 「幻影の盾」 | 22,100 | $3.54 / $5.97 | 1 run |

| Budget line, inside the $150 credits | Base | Pessimistic |
|---|---|---|
| Dev: smoke tests, prompt tuning, failed runs, 晩餐 ×5 | $25 | $40 |
| The other texts (Tōkoku, Kasai, Setsu whole) | $8.6 | $14.5 |
| Showcase | $3.8 | $6.5 |
| The exhibit (audit on all versions, both auditors) and the planted test | $8 | $14 |
| Catalogue, 200 reports | $4 | $7 |
| Rehearsals and video takes; covers | $6 | $11 |
| Stretch, one run | $3.5 | $6 |
| **Total** | **≈ $58** | **≈ $99** |

**Headline:** everything, the stretch included, fits in the $150 credits even in the pessimistic case. The live site after submission runs on separate billing, capped at $10 a day.

If reasoning turns out worse than pessimistic, there are three levers, in this order:
1. Move routine Source check to Spark Open on a partner host, and keep Wonder for flagged chunks.
2. Use Meta's cheaper Contributor tier for the shelf and the other texts.
3. Drop the stretch.
