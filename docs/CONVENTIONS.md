# Fortleben — working in this repo

The platform is Fortleben; the translation house inside it is keikaku, and the engine's package and CLI keep that name. This is how the repo fits together and the few rules that keep it working, for anyone (or any coding assistant) changing it. The order of the stages is `STAGES.md`; what each prompt does is `PROMPTS.md`; the site is `SITE.md`.

## Layout

```
house/            the engine and the site's back end
  cli.py          the keikaku command: fetch, add, wish, run, checkpoint, steer, approve, fixture, download, audit, serve, invite, comments
  orchestrator.py the stages in order (STAGES), stop and resume, the up-front estimate
  stages/         one module per stage, each with run(ctx); Ctx (stages/__init__.py) is what a stage gets
  client.py       the one model client: Meta's Responses API, schema validation, pricing from usage, the response cache, FakeClient
  budget.py       the spend ledger, run estimates, caps, the kill switch
  context.py      what each call sees, and how a long work is cut into parts
  pager.py        cuts a work into drafting pages
  queries.py      the readers' queries and the code checks' flags, and their statuses
  events.py       event types: the only way a change of state is recorded
  schemas/        one JSON schema per prompt output
  checks/         deterministic checks: stray scripts, the omission guard, the house style in code
  steer.py        the checkpoint's notes and approval
  works.py        the works keikaku knows and the rights rule (eligible)
  acquire.py      adding a work from an Aozora link: card, rights rule, ruby text into the data folder
  parser/         the source adapter interface
  lang/ja/        everything Japanese: the Aozora adapter and card reader, ruby, gaiji
  audit.py        the blind audits and the one-shot baseline (docs/experiments/)
  fixture.py      exports a recorded run to fixtures/<work>/; zips a run for its editor (download)
  db.py           the SQLite connection and the data folder
  web.py          the site (FastAPI); edition.py assembles what a page shows
  desk.py         the editors' desk: invites, allowances, runs started from the site
  accounts.py     sign-up, sign-in, sessions, resets, editors' own keys
  comments.py     comments in the margin, the screen, reports, the editor's daily email
  wishlist.py     the public wishlist
prompts/          one Markdown file per prompt; house-brief.md comes first in every call
site/             Jinja templates and static CSS/JS, no build step (not a Python package: `site` would shadow Python's own)
fixtures/         works.json (the works and their rights records), sources/ (their texts), and recorded runs: <work>/run.json and <work>/responses/
db/schema.sql     the SQLite schema
tests/            pytest; tests/fixtures/ holds saved Aozora pages for the parser and the add
bin/              serve.sh (the site, under Litestream when a bucket is set), seed-wishlist.sh
Dockerfile        the site on Railway; litestream.yml streams the database to object storage
```

The database, the response cache, audits and releases live in the data folder: `KEIKAKU_DATA_DIR`, or `var/` in the repo (ignored by git).

## How a stage, a prompt and a schema fit together

- **A stage** is a module in `house/stages/` with `run(ctx)`, listed in `orchestrator.STAGES` in the order `STAGES.md` gives. It reads what earlier stages left in the database, makes its calls, and writes its outputs (revisions, queries, notes, documents) before the next stage starts, so a run can stop after any stage and resume from the record. Every stage runs on its own from the CLI: `keikaku run <work> --to <stage>`, `--from <stage>`, `--only <stage>`.
- **A call** is a `Call(prompt, model, effort, input, schema=...)` through `ctx.call`. The instructions are always `prompts/house-brief.md` followed by `prompts/<prompt>.md`; the input is the data blocks `context.py` assembles, stable ones first so the prefix caches. Nothing in `house/` contains prompt text.
- **A schema** in `house/schemas/<prompt>.json` is the shape of that prompt's output. The client validates every answer against it and asks again once if it doesn't fit; a Wonder answer that fails twice is made again on Spark, and the event log says so. `tests/test_schemas.py` checks every schema is valid and works in strict mode.
- **Limits live in code, principles in prompts.** A prompt explains the job and why, with one or two contrasting examples, and what it gets and returns. Budgets, note caps, locks and shapes are enforced in code and schemas. Don't fix a bug by adding "never" or "always" to a prompt; add a check or a schema constraint. Don't name internal concepts in a prompt either: the models repeat them in notes readers see.
- **Events are the record.** Every change to text, queries, rules, budget or status goes through an event (`house/events.py`). The site, replay and the audits read the record; nothing else is a source of truth.
- **The shared shapes** are `db/schema.sql`, `house/events.py`, `house/schemas/` and `STAGES.md`. Change one and update the matching doc in the same commit.
- **Only Meta models run here**: Spark and Wonder, through `house/client.py`, in the product and in the audits.

## Tests

```
uv sync
uv run pytest
```

The tests need no key and no network. `FakeClient` serves recorded responses from `fixtures/` and fails loudly (`FixtureMissing`) on a call it has no recording for, so a test can never spend. Every test gets its own data folder. Among them: the parser round-trips on saved Aozora pages; every schema validates; the orchestrator replays 「晩餐」 (`bansan`) end to end from its fixture in under a minute and reproduces the recorded run; budget caps hold against a client that lies about usage; the site, the desk, accounts, comments and the wishlist are tested through FastAPI's test client.

Add a test with the change it covers. Anything that would call a model uses `FakeClient` and a recording, never a live key.

## Recording and replaying runs

A response is cached under a key made of the model, the effort, a hash of the instructions (house brief plus prompt), a hash of the input, a hash of the schema, and any tools. A rerun of the same call is free, and a replay is exact.

- **Record:** run the work live with `MODEL_API_KEY` set (`uv run keikaku run <work>`), then `uv run keikaku fixture <work>` copies that run's responses into `fixtures/<work>/responses/` and its full record into `fixtures/<work>/run.json`. Nothing in a fixture is edited by hand.
- **Seeding a site:** every server loads the recordings into its database when it starts, each once. A recording is numbered from 1001 (`keikaku fixture` gives it the next number, or `--as`), clear of a live database's own runs, and a work recorded again takes a new number. Its other ids move past the database's where they're taken, and its release becomes the next version of the work's house edition, so a work recorded again replaces the old recording on the shelf on the next deploy.
- **Replay:** `uv run keikaku --replay run <work>` runs the recorded work with no key and no spend; `uv run keikaku serve --replay` serves every recorded run as the site.
- **Changing a prompt or a schema invalidates its recordings.** The hashes change, so `FakeClient` no longer finds the responses and the replay test fails with `FixtureMissing` at the first changed call. Changing `house-brief.md` invalidates every recording. So does changing what a stage puts in a call's input. Re-record the fixture with a live run and `keikaku fixture` in the same change. A fixture recorded by an earlier pipeline is skipped by the replay test, with a message saying to re-record it.

## Adding a work: the rights rule

Only works that pass the rights rule are fetched or stored: the author died in 1931 or earlier and the work was first published by 1930. It's `works.eligible()` in `house/works.py`, applied by code.

- **To the repo:** add the work and its rights record to `fixtures/works.json` (where the death and first-publication years come from, any existing English translations), then `uv run keikaku fetch <work>` puts its text in `fixtures/sources/`. A death between 1932 and 1938 is allowed only where the record's verdict gives a strong reason.
- **From a link:** `uv run keikaku add <aozora card url>` (or the desk, or the wishlist) goes through `house/acquire.py`: it reads the Aozora card, takes the death year of every credited person and the 初出 year, and refuses when any is past the rule or can't be read. A year that can't be read is a refusal, never a guess. A work split across several cards, or with no ruby text file, is refused too. The text goes to the data folder, never the repo.
- Every edition carries the Aozora attribution and its colophon. Published human translations are quoted in short excerpts only, never committed whole.

## Configuration

Copy `.env.example` to `.env` and fill in what you need; it lists every setting with a line on each. The ones that matter most:

- `MODEL_API_KEY`: the Meta Model API key. Without it the house runs on `FakeClient` and the site serves recorded runs only.
- `KEIKAKU_DATA_DIR`: where the database and cache live (on Railway, the volume's mount path).
- `KEIKAKU_CAP_RUN`, `KEIKAKU_CAP_DAILY`, `KEIKAKU_CAP_TOTAL`: spend caps, checked before every call. `HOUSE_OPEN=false` is the kill switch.
- `KEIKAKU_SECRET`: salts the hashes of commenters' cookies and addresses and of invite tokens, signs the moderation links, and encrypts editors' own keys.
- `RESEND_API_KEY`, `REPORT_EMAIL_TO`, `REPORT_EMAIL_FROM`: mail for the comments email and password resets; without a key, mail goes to the server log.
- `KEIKAKU_BASE_URL`: the site's own address, for links in mail and invites.
- `KEIKAKU_TRUST_PROXY`, `KEIKAKU_CONTACT`, the comment limits and the Litestream backup settings.

## Security, given that the code is public

- **No secrets in the repo or its history.** Keys and the secret live in `.env` (ignored by git) locally and in Railway's variables in production; `.env.example` has the names only. If one is ever committed, rotate it: deleting the file doesn't remove it from history.
- **`KEIKAKU_SECRET`** must be a long random string on any public server. Without it, moderation links are refused and editors can't store a key. Changing it voids every invite link and moderation link and makes stored keys unreadable, so editors add theirs again.
- **`KEIKAKU_TRUST_PROXY=true`** only behind a proxy that appends the visitor's address to `X-Forwarded-For` (Railway does). Then the rate limits read the right-most value, the one the proxy added. Reached directly, leave it false: otherwise anyone can make up an address and walk past every limit.
- **Nothing relies on the scheme being secret.** Passwords are scrypt hashes; session, reset and invite tokens are random and stored only as hashes; forms carry a CSRF token and the desk's JSON requests a header another site can't set. `SITE.md` has the details.
- **Reader text is data.** A comment and its name reach a model only as quoted content for the screen, never as instructions, and nothing a reader types reaches a drafting prompt. An editor's checkpoint note goes to the model as the editor's note, which is what it is for.
- **Spending is capped in code**, and visitors can't start runs. The worst case is runs pausing while the site carries on.

## Copy

UI and docs are plain British English: blunt, concrete, no marketing. Labels say *draft / house-checked / editor-approved / human-reviewed* in words. Leave out what isn't built rather than promising it. Every experiment gets a write-up in `docs/experiments/` once its result is in: the question, the runs, the numbers, and what changed in the engine, added to the index in the same commit as that change.

## Git

Small commits, one working change each, with one-sentence messages. Merge with normal merges, so every commit stays visible; no squashing, no rebasing shared history.
