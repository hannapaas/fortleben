# Fortleben — how this repo is built

The platform is Fortleben; the translation house inside it is keikaku, and the engine's package and CLI keep that name.

Written 30 Oct 2026. The rules of the road for anyone (or any agent) working in this repo, so parallel lanes don't tangle. Short on purpose.

## Layout

```
house/            the engine
  client.py       one model client: Responses API, pricing from usage, response cache, FakeClient
  budget.py       drops of ink, spend ledger, caps, kill switch
  orchestrator.py stages in order (docs/STAGES.md), stop/resume, queries, rules, locks
  stages/         one module per stage
  schemas/        JSON schema per prompt output; the contract
  events.py       event types; the only way state changes are recorded
  lang/ja/        everything Japanese-specific: the Aozora parser and source adapter, ruby, honorific policy, JA stats
  parser/         source adapter interface; other languages add house/lang/<code>/
  checks/         deterministic checkers (ledger, callbacks, length ratio, tics)
prompts/          one Markdown file per prompt (docs/PROMPTS.md), with examples
site/             FastAPI app, Jinja templates, static CSS/JS (no build step)
exhibit/          the audit harness, frozen passages, the marked-up results, the exhibit renderer
fixtures/         recorded runs and sample data; the site and House must run from these alone
db/schema.sql     the SQLite schema
tests/            pytest; every lane adds its own
```

## The contract

`db/schema.sql`, `house/events.py`, `house/schemas/` and `docs/STAGES.md` are the contract between lanes. Change them only with a note in the commit and the matching doc updated in the same commit. Lanes code against the contract and the fixtures, never against each other's unfinished work.

## Working rules

- **No model key needed to develop the site, the House view or the exhibit.** `FakeClient` serves responses from `fixtures/`; the response cache makes real reruns free. A judge cloning this repo can run `keikaku serve --replay` with no key and see the recorded run.
- **Every stage is callable on its own** from the CLI (`keikaku run <work> --to <stage>`, `--from <stage>`), so a stage can be tuned without rerunning the ones before it.
- **Limits live in code, principles live in prompts** (`ARCHITECTURE.md` §3). Don't add "never / always" lines to a prompt to fix a bug; add a check or a schema constraint.
- **Prompts are data.** Nothing in `house/` contains prompt text. A prompt file has: purpose and reasons; one or two contrasting examples; what it gets and returns. The schema polices the shape.
- **Events are the record.** Any change to text, queries, rules, budget or status goes through an event. The UI, replay and evals read events; nothing else is a source of truth.
- **Tests:** parser round-trips on the four demo texts; schema validation for every prompt; orchestrator runs 晩餐 end to end on `FakeClient` under a minute; budget caps are tested with a client that lies about usage.
- **Copy** in the UI and docs is plain British English: blunt, no marketing. Agents are square and named by department; people are round and named. Labels say *draft / house-checked / editor-approved / human-reviewed* in words.
- **Nothing here depends on a private overlay.** `KEIKAKU_PRIVATE_DIR` may add voice profiles and word lists; the demo runs at full quality without it.
- **Only Meta models run here**, in the product and in the exhibit's audit, by the hackathon's rule. No other provider's model, and no non-Meta ML library model in anything that runs.
- **Rights:** only Aozora works that pass the rights record (author died ≤1931, first published ≤1930) are fetched or stored. Published human translations used in evals are quoted in short excerpts only.

## Security, given that the code is public

- **Nothing secret in the code or its history.** Keys, tokens and the invite-link signing key live in `.env` locally and in Fly's secret store; `.env.example` has the names only. A full-history secrets scan runs before submission.
- **Invite links** are long random tokens made server-side, stored hashed, scoped (house editor / guest editor with an allowance / reviewer) and revocable. Reading the scheme gives nothing without a token.
- **Spending is capped in code**, not hidden: daily and total caps, one run at a time, reservation before a run, kill switch; visitors can't start runs at all. The worst case is runs pausing while the site carries on.
- **Reader text is data.** Comments, proposals and request reasons go through the model screen as quoted content, never as instructions, and nothing a reader types reaches a drafting prompt except as a query the owner answers.

## Git

- Work on `build`; each lane on its own branch (`engine`, `site`, `house-view`, `exhibit`, `catalogue`, `ops`), in its own worktree when lanes run at the same time, merged into `build` with normal merges. Small commits, one working change each, one-sentence messages. No squashing, no rebasing shared history.
- Secrets in `.env` (gitignored); `.env.example` lists the names.
