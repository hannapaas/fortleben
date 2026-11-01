# keikaku

A human-directed translation house for literature nobody has translated into English, run by agents on Meta's models. Japanese first.

Work in progress for the Meta Global AI Developer Hackathon. Everything in this repo was written during the event (from 27 Oct 2026); the commit history is the record.

## Plans
- [Concept](docs/CONCEPT.md): what it is and who it's for.
- [Architecture](docs/ARCHITECTURE.md): departments, data model, which Meta model does what, cost.
- [Story state](docs/STORY-STATE.md): how the house remembers a text (the story bible and what each call sees).
- [Running a text](docs/RUNNING-A-TEXT.md): passes, difficulty triage and the budget per manuscript sheet.
- [The site](docs/SITE.md): every page, what a reader can do there, how it grows.
- [The editors' desk](docs/EDITORS-DESK.md): how a run works for the person steering it: estimates, the checkpoint, what's committed and published when, running out, samples.
- [Stages](docs/STAGES.md): the exact order the orchestrator runs, and the limits code enforces.
- [Conventions](docs/CONVENTIONS.md): repo layout, the contract between lanes, tests, git.
- [From translators](docs/FROM-TRANSLATORS.md): what we took from how literary translators and editors work, and where it lives in the design.
- [Prompts](docs/PROMPTS.md): every model call in the house, and when each is needed.
- [Build plan](docs/BUILD-PLAN.md): milestones, evals and the cut list.

## Running it

Setup steps, the keyless replay of recorded runs, and how to add a Meta Model API key will be here once the engine exists (`docs/BUILD-PLAN.md`, "The judge path"). Every model this repo calls is a Meta model; the README will list which one does what and where it runs.

## Licence

The code is published to be read and run for evaluation; it isn't open source at this stage, and may become so later. Other people run the house on the site, signed in as editors. The English the house produces is CC BY-SA 4.0. See `LICENSE`.
