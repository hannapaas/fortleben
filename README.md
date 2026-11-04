# Fortleben

A site for Japanese literature nobody has translated into English. The translations are made by **keikaku**, a translation house run by agents on Meta's models and steered by a person, and they go on changing after they're published: editors correct them paragraph by paragraph, and readers leave notes in the margin.

*Fortleben*, living on: Walter Benjamin's word for what a work does in translation. (It also happens to echo the Future of Books Fund behind Aozora Bunko.) *keikaku*, plan: the fansub joke about a translator's note that explains nothing, which is the test every note here has to pass.

Built for the Meta Global AI Developer Hackathon, 27 Oct to 4 Nov 2026. Everything in this repo was written during the event; the commit history is the record.

## What it does

- **Translates a whole work the way a translation house would.** One reader forms a view of what the text turns on, a story bible records who everyone is and how they speak, a drafter writes plain English a page at a time, two readers check it (one against the Japanese, one as English), a desk weighs their notes against the reading, and a final read and a copy editor finish it. The stages are in [docs/STAGES.md](docs/STAGES.md).
- **Stops for the person steering it.** Before anything is drafted, the editor sees the house's reading, the story bible and page 1 in each voice the text allows. They answer in plain words, edit the files by hand if they want, pick a voice and approve. Nothing after that waits for them. See [docs/EDITORS-DESK.md](docs/EDITORS-DESK.md).
- **Publishes every edition with its working shown.** The reader page sets the English beside the Japanese with its ruby, the translator's notes in the margin, and each edit after release with who made it. The analysis page shows how the house read the text before drafting it, and what the editor changed in that reading.
- **Takes any work on Aozora Bunko that's out of copyright.** Paste a link; the rights rule is checked from Aozora's own card (everyone credited died in 1931 or earlier, first published by 1930) and anything else is refused with the reason.
- **Lets anyone take part.** Readers comment on a paragraph (screened by a model, rate-limited, hidden on reports). Anyone can add a work to the public wishlist. Anyone can sign up and run a translation on their own Meta key.

## Running it

You need Python 3.12 and [`uv`](https://docs.astral.sh/uv/). Nothing below needs a key.

```sh
uv sync
uv run keikaku serve --replay           # the site at http://127.0.0.1:8000, serving the recorded runs
uv run keikaku --replay run bansan      # replay the recorded run of 「晩餐」 in the terminal: no key, no network, no spend
uv run pytest                           # the tests, also keyless
```

`--replay` serves every model call from the recordings in `fixtures/<work>/`. 「晩餐」 (`bansan`) and 「酒虫」 (`shuchu`) are recorded there, each the complete record of a live run: every call's model, tokens, cost and response, the readers' notes, the desk's decisions and the event log.

To run live, copy `.env.example` to `.env` and set `MODEL_API_KEY` (a Meta Model API key). Then:

```sh
uv run keikaku fetch                              # fetch the works in fixtures/works.json from Aozora Bunko
uv run keikaku --cap 3 run sumiyaki               # one work through every stage, with a $3 run cap
uv run keikaku run sumiyaki --checkpoint          # stop before the draft for a person to steer it
uv run keikaku checkpoint sumiyaki                # write out the reading, the bible and the voices
uv run keikaku steer sumiyaki "make it plainer"   # a note in plain words; the house replies and redrafts page 1
uv run keikaku approve sumiyaki --voice 0         # then: uv run keikaku run sumiyaki --from draft
uv run keikaku fixture bansan                     # export a run to fixtures/<work>/ so it replays without a key
uv run keikaku audit bansan --runs 1 2 --baseline --readable  # blind audits of runs 1 and 2 beside a one-shot
```

[AGENTS.md](AGENTS.md) walks a coding assistant through steering a run on someone's behalf.

`keikaku add <aozora url>` adds a work that passes the rights rule; `keikaku wish <url>` puts one on the wishlist. `keikaku serve` without `--replay` serves the live database, with the recorded runs loaded into it once. `keikaku invite "Name"` makes an invite link to the editors' desk with an allowance on it.

Every run is priced before it starts and refused if the estimate won't fit its cap or what's left of the daily and total caps (`--cap`, or `KEIKAKU_CAP_RUN`, `KEIKAKU_CAP_DAILY` and `KEIKAKU_CAP_TOTAL`). 「晩餐」 estimates at about $1.25. `HOUSE_OPEN=false` stops all live calls. Runs on an editor's own key are held to the run cap only.

The site runs as one service from the `Dockerfile`, with the database on a volume at `KEIKAKU_DATA_DIR`; `bin/serve.sh` starts it under Litestream when a backup bucket is set. Every setting is listed in `.env.example`.

## Which Meta model does what

Two models, both through the Meta Model API (the Responses API, with the OpenAI SDK pointed at Meta's endpoint). No other provider's model runs anywhere in this repo.

- **`muse-wonder-1.0`** forms the house's reading of the text and checks it, reads the editor's notes at the checkpoint, decides at the desk, does the final read and runs the audits.
- **`muse-spark-1.3`** divides the text into parts, writes the story bible, drafts, reads as both readers, copy-edits, writes the translator's notes, screens comments and describes new works from Aozora.

`keikaku run` takes `--draft-model`, `--reader-model`, `--desk-model` and `--final-model` (`spark` or `wonder`); the defaults are the best set-up the experiments found.

## Docs

- [Architecture](docs/ARCHITECTURE.md): the parts of the system, the data model, models, cost and hosting.
- [Stages](docs/STAGES.md): the exact order the orchestrator runs, and the limits code enforces.
- [Story state](docs/STORY-STATE.md): how the house remembers a text: the reading, the story bible and what each call sees.
- [Prompts](docs/PROMPTS.md): every prompt, who calls it on which model, and how they're written.
- [The editors' desk](docs/EDITORS-DESK.md): steering a run: invites and own keys, the checkpoint, approval, editing an edition.
- [The site](docs/SITE.md): every page, comments and moderation, accounts.
- [Conventions](docs/CONVENTIONS.md): repo layout, tests, fixtures, configuration.
- [From translators](docs/FROM-TRANSLATORS.md): what we took from how literary translators and editors work.
- [Experiments](docs/experiments/README.md): what we tried while building the house, the numbers, and what changed because of them.
- [References](docs/REFERENCES.md): the papers and books the design draws on.

## Licence

The code, prompts and docs are AGPL-3.0-or-later: if you run a changed version as a service, you share your changes. The English keikaku produces, and the recorded runs in `fixtures/`, are CC BY-SA 4.0. See `LICENSE`.
