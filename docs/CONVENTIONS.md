# Fortleben — how this repo is built

The platform is Fortleben; the translation house inside it is keikaku, and the engine's package and CLI keep that name.

Written 30 Oct 2026. The rules of the road for anyone (or any agent) working in this repo, so parallel lanes don't tangle. Short on purpose.

## Layout

```
house/            the engine
  cli.py          the keikaku command: fetch, add, run, checkpoint, steer, approve, fixture, download, audit, serve, invite, comments
  works.py        the works keikaku knows: fixtures/works.json, then works added from an Aozora link (the `work` table)
  acquire.py      adding a work from an Aozora link: card, rights rule, ruby text into the data folder
  client.py       one model client: Responses API, pricing from usage, response cache, FakeClient
  budget.py       spend ledger, run estimates, caps, kill switch
  orchestrator.py stages in order (docs/STAGES.md), stop and resume, the up-front estimate
  steer.py        the checkpoint's notes and approval (docs/STEERING.md)
  stages/         one module per stage
  context.py      what each call sees, and how a long work is cut into parts
  pager.py        cuts a work into drafting pages
  queries.py      the readers' notes and code checks' flags, and their statuses
  schemas/        JSON schema per prompt output; the contract
  events.py       event types; the only way state changes are recorded
  audit.py        the blind audits and the one-shot baseline (docs/experiments/)
  fixture.py      exports a recorded run to fixtures/<work>/, and zips a run for its editor (download)
  lang/ja/        everything Japanese-specific: the Aozora source adapter and parser, ruby, gaiji
  parser/         source adapter interface; other languages add house/lang/<code>/
  checks/         deterministic checkers (stray scripts, the omission guard)
prompts/          one Markdown file per prompt (docs/PROMPTS.md), with examples
site/             Jinja templates and static CSS/JS (no build step); the FastAPI app is house/web.py,
                  since a package named `site` would shadow Python's own, and house/edition.py assembles what it shows
fixtures/         works.json (the works the house knows, with rights records), their sources, recorded runs
db/schema.sql     the SQLite schema
tests/            pytest; every lane adds its own
```

Not built yet: the House walkthrough (`/house`) and `exhibit/` (the exhibit renderer and frozen passages).

## The contract

`db/schema.sql`, `house/events.py`, `house/schemas/` and `docs/STAGES.md` are the contract between lanes. Change them only with a note in the commit and the matching doc updated in the same commit. Lanes code against the contract and the fixtures, never against each other's unfinished work.

## Working rules

- **No model key needed to develop the site, the House view or the exhibit.** `FakeClient` serves responses from `fixtures/`; the response cache makes real reruns free. A judge cloning this repo can run `keikaku --replay run bansan` with no key and replay the recorded run; `keikaku serve` will show it once the site exists.
- **Every stage is callable on its own** from the CLI (`keikaku run <work> --to <stage>`, `--from <stage>`), so a stage can be tuned without rerunning the ones before it.
- **Limits live in code, principles live in prompts** (`ARCHITECTURE.md` §3). Don't add "never / always" lines to a prompt to fix a bug; add a check or a schema constraint.
- **Prompts are data.** Nothing in `house/` contains prompt text. A prompt file has: purpose and reasons; one or two contrasting examples; what it gets and returns. The schema polices the shape.
- **Every experiment gets a write-up** in `docs/experiments/` once its result is in: the question, the runs, the numbers, and what changed in the engine. Add it to the index in the same commit as the change it led to.
- **Events are the record.** Any change to text, queries, rules, budget or status goes through an event. The UI, replay and evals read events; nothing else is a source of truth.
- **Tests:** parser round-trips on the works in `fixtures/works.json`; schema validation for every prompt; orchestrator runs 晩餐 end to end on `FakeClient` under a minute; budget caps are tested with a client that lies about usage.
- **Copy** in the UI and docs is plain British English: blunt, no marketing. Agents are square and named by department; people are round and named. Labels say *draft / house-checked / editor-approved / human-reviewed* in words.
- **Nothing here depends on a private overlay.** `KEIKAKU_PRIVATE_DIR` may add voice profiles and word lists; the demo runs at full quality without it.
- **Only Meta models run here**, in the product and in the exhibit's audit, by the hackathon's rule. No other provider's model, and no non-Meta ML library model in anything that runs.
- **Rights:** only Aozora works that pass the rights record (author died ≤1931, first published ≤1930) are fetched or stored. A work added from a link is checked by code from its Aozora card (house/acquire.py): a year that can't be read is a refusal, never a guess. Published human translations used in evals are quoted in short excerpts only.

## Security, given that the code is public

- **Nothing secret in the code or its history.** Keys, tokens and the invite-link signing key live in `.env` locally and in Railway's variables; `.env.example` has the names only. A full-history secrets scan runs before submission.
- **Invite links** are long random tokens made server-side, stored hashed, scoped (house editor / guest editor with an allowance / reviewer) and revocable. Reading the scheme gives nothing without a token. Opening one signs the editor in.
- **Accounts** are an email address and a password, kept as a salted scrypt hash; sessions, reset links and invite tokens are random and stored only as hashes, compared in constant time. Desk JSON requests need an `X-Requested-With` header and HTML forms a token matching the `fl_csrf` cookie, so another site can't post to them.
- **Spending is capped in code**, not hidden: run, daily and total caps, an estimate before every run that refuses one that won't fit, a kill switch; visitors can't start runs at all (and on the site, once built, one run at a time). The worst case is runs pausing while the site carries on.
- **Reader text is data.** Comments, proposals and request reasons go through the model screen as quoted content, never as instructions, and nothing a reader types reaches a drafting prompt except as a query the owner answers.

## Git

- Work on `build`; each lane on its own branch (`engine`, `site`, `house-view`, `exhibit`, `catalogue`, `ops`), in its own worktree when lanes run at the same time, merged into `build` with normal merges. Small commits, one working change each, one-sentence messages. No squashing, no rebasing shared history.
- Secrets in `.env` (gitignored); `.env.example` lists the names.
