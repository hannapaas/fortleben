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
- [Stages](docs/STAGES.md): the exact order the orchestrator runs, and the limits code enforces.
- [Conventions](docs/CONVENTIONS.md): repo layout, the contract between lanes, tests, git.
- [From translators](docs/FROM-TRANSLATORS.md): what we took from how literary translators and editors work, and where it lives in the design.
- [Prompts](docs/PROMPTS.md): every model call in the house, and when each is needed.
- [Build plan](docs/BUILD-PLAN.md): milestones, the exhibit (passages side by side with margin notes, the project's proof), and the cut list.
- [Experiments](docs/experiments/README.md): what we tried while building the house, the numbers, and what changed because of them.
- [References](docs/REFERENCES.md): the papers and books the design draws on, by the decision each bears on.

## Running it

The engine runs from the command line. The site, the House walkthrough and the exhibit aren't built yet.

You need Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
uv run keikaku --replay run bansan      # replay the recorded run of 「晩餐」: no key, no network, no spend
uv run pytest                           # the tests, also keyless
```

`--replay` serves every call from the recorded responses in `fixtures/bansan/`. Without a key the house replays anyway; only 「晩餐」 has a recording.

To run live, copy `.env.example` to `.env` and set `MODEL_API_KEY` (a Meta Model API key). Then:

```sh
uv run keikaku fetch                    # fetch the works in fixtures/works.json from Aozora Bunko
uv run keikaku --cap 3 run sumiyaki     # one work through every stage, with a $3 run cap
uv run keikaku --cap 2 run bansan --to bible   # stop after a stage
uv run keikaku run bansan --from desk   # resume the latest run from a stage (--run N for another)
uv run keikaku fixture bansan           # export a run to fixtures/<work>/ so it replays without a key
uv run keikaku audit bansan --runs 1 2 --baseline --readable  # blind audits of runs 1 and 2 beside a one-shot
```

`keikaku run` takes `--draft-model`, `--reader-model`, `--desk-model` and `--final-model` (`spark` or `wonder`) and `--draft-prompt` (`translate-draft-plain` or `translate-draft`); the defaults are the best set-up the experiments found. A run is estimated before it starts, high on purpose, and refused if the estimate won't fit its cap or what's left of the daily and total caps. The run cap is `--cap`, which goes before the command, or `KEIKAKU_CAP_RUN` (default $3, enough for a short story: 「晩餐」 estimates at about $1, 「炭燒のむすめ」 at about $2.50). `HOUSE_OPEN=false` stops all live calls.

Which Meta model does what: `muse-spark-1.3` plans the parts, writes the story bible, drafts, reads, does the final read and writes the notes; `muse-wonder-1.0` writes the house's reading, checks the crux, edits at the desk and runs the audits. Both are called through the Meta Model API. No other provider's model runs anywhere in this repo. The stages are in [docs/STAGES.md](docs/STAGES.md); what we tried and why the defaults are what they are is in [docs/experiments/](docs/experiments/README.md).

## Licence

The code is published to be read and run for evaluation; it isn't open source at this stage, and may become so later. Other people run the house on the site, signed in as editors. The English the house produces is CC BY-SA 4.0. See `LICENSE`.
