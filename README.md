# Fortleben

A platform for literature nobody has translated into English, Japanese first, where the translations are made by **keikaku**, a human-directed translation house run by agents on Meta's models, and go on changing after they're made.

*Fortleben*, living on: Walter Benjamin's word for what a work does in translation. (It also happens to echo the Future of Books Fund behind Aozora Bunko.) *keikaku*, plan: the fansub joke about a translator's note that explains nothing, which is the test every note here has to pass.

Work in progress for the Meta Global AI Developer Hackathon. Everything in this repo was written during the event (from 27 Oct 2026); the commit history is the record.

## Plans
- [Concept](docs/CONCEPT.md): what it is and who it's for.
- [Architecture](docs/ARCHITECTURE.md): departments, data model, which Meta model does what, cost.
- [Story state](docs/STORY-STATE.md): how the house remembers a text (the story bible and what each call sees).
- [Running a text](docs/RUNNING-A-TEXT.md): the passes a text goes through, the checkpoint, and the budget.
- [The site](docs/SITE.md): every page, what a reader can do there, how it grows.
- [The editors' desk](docs/EDITORS-DESK.md): how a run works for the person steering it: estimates, the checkpoint, what's committed and published when, running out, samples.
- [Steering](docs/STEERING.md): who runs the house and how they steer it: the checkpoint, notes in plain words, bringing your own key.
- [Stages](docs/STAGES.md): the exact order the orchestrator runs, and the limits code enforces.
- [Conventions](docs/CONVENTIONS.md): repo layout, the contract between lanes, tests, git.
- [From translators](docs/FROM-TRANSLATORS.md): what we took from how literary translators and editors work, and where it lives in the design.
- [Prompts](docs/PROMPTS.md): every model call in the house, and when each is needed.
- [Build plan](docs/BUILD-PLAN.md): milestones, the exhibit (passages side by side with margin notes, the project's proof), and the cut list.
- [Experiments](docs/experiments/README.md): what we tried while building the house, the numbers, and what changed because of them.
- [References](docs/REFERENCES.md): the papers and books the design draws on, by the decision each bears on.

## Running it

You need Python 3.12 and [`uv`](https://docs.astral.sh/uv/). Nothing below needs a key.

```sh
uv sync
uv run keikaku serve --replay           # the site at http://127.0.0.1:8000, serving the recorded runs
uv run keikaku --replay run bansan      # replay the recorded run of 「晩餐」 in the terminal: no key, no network, no spend
uv run pytest                           # the tests, also keyless
```

Two pages are the proof of the project. **The house** (`/house`) walks through one real run: the text's route through the stages, drawn as stations, with one or two picked moments from the record at each (a reader's note and what the desk did with it, a fork and both sides' case, a line before and after revision) and every station's full output a click away: the reading, the whole story bible, the query log, the notes. **The exhibit** sets passages of the house's English beside a one-shot translation from the same model and, where one exists, a published human translation, with the margin notes anchored to the lines they're about, so the difference the house makes can be read rather than claimed.

`--replay` serves every call from the recorded responses in `fixtures/<work>/`: 「晩餐」 and 「酒虫」 have recordings, each the complete record of a live run (every model call's model, tokens, cost and response, the readers' notes, the desk's decisions, the event log). Without a key the house replays anyway.

To run live, copy `.env.example` to `.env` and set `MODEL_API_KEY` (a Meta Model API key). Then:

```sh
uv run keikaku fetch                    # fetch the works in fixtures/works.json from Aozora Bunko
uv run keikaku --cap 3 run sumiyaki     # one work through every stage, with a $3 run cap
uv run keikaku --cap 2 run bansan --to bible   # stop after a stage
uv run keikaku run bansan --from desk   # resume the latest run from a stage (--run N for another)
uv run keikaku fixture bansan           # export a run to fixtures/<work>/ so it replays without a key
uv run keikaku audit bansan --runs 1 2 --baseline --readable  # blind audits of runs 1 and 2 beside a one-shot
```

`keikaku add <aozora url>` adds any work on Aozora Bunko that passes the rights rule; `keikaku wish <url>` puts one on the public wishlist (`bin/seed-wishlist.sh` seeds a new database with a few). `keikaku serve` (without `--replay`) serves the live database, with the recorded runs loaded into it once; `keikaku invite "Name"` makes an invite link to the editors' desk, where an editor can run a whole work ([docs/EDITORS-DESK.md](docs/EDITORS-DESK.md)). The site runs as one service from the `Dockerfile` (Railway, with a volume at `KEIKAKU_DATA_DIR`; `bin/serve.sh` starts it under Litestream when a backup bucket is set).

`keikaku run` takes `--draft-model`, `--reader-model`, `--desk-model` and `--final-model` (`spark` or `wonder`) and `--draft-prompt` (`translate-draft-plain` or `translate-draft`); the defaults are the best set-up the experiments found. A run is estimated before it starts, a little high, and refused if the estimate won't fit its cap or what's left of the daily and total caps. The run cap is `--cap`, which goes before the command, or `KEIKAKU_CAP_RUN` (default $30, enough for a novel: 「晩餐」 estimates at about $1.25, 「炭燒のむすめ」 at about $1.85, a 300-page novel at about $24); the daily cap is `KEIKAKU_CAP_DAILY` (default $30) and the total `KEIKAKU_CAP_TOTAL` (default $100). `HOUSE_OPEN=false` stops all live calls.

Which Meta model does what: `muse-spark-1.3` plans the parts, writes the story bible, drafts, reads, copy-edits and writes the notes; `muse-wonder-1.0` writes the house's reading, checks the crux, edits at the desk, does the final read and runs the audits. Both are called through the Meta Model API. No other provider's model runs anywhere in this repo. The stages are in [docs/STAGES.md](docs/STAGES.md); what we tried and why the defaults are what they are is in [docs/experiments/](docs/experiments/README.md).

## Licence

The code, prompts and docs are AGPL-3.0-or-later: if you run a changed version as a service, you share your changes. The English keikaku produces, and the recorded runs in `fixtures/`, are CC BY-SA 4.0. See `LICENSE`.
