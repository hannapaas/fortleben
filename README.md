# keikaku

A human-directed translation house for untranslated Japanese literature, run by agents on Meta's models.

Work in progress for the Meta Global AI Developer Hackathon. Everything in this repo was written during the event (from 27 Oct 2026); the commit history is the record.

## Plans
- [Concept](docs/CONCEPT.md): what it is and who it's for.
- [Architecture](docs/ARCHITECTURE.md): departments, data model, which Meta model does what, cost.
- [Story state](docs/STORY-STATE.md): how the house remembers a text (the story bible and what each call sees).
- [Running a text](docs/RUNNING-A-TEXT.md): passes, difficulty triage and the budget per manuscript sheet.
- [Stages](docs/STAGES.md): the exact order the orchestrator runs, and the limits code enforces.
- [Conventions](docs/CONVENTIONS.md): repo layout, the contract between lanes, tests, git.
- [From translators](docs/FROM-TRANSLATORS.md): what we took from how literary translators and editors work, and where it lives in the design.
- [Prompts](docs/PROMPTS.md): every model call in the house, and when each is needed.
- [Build plan](docs/BUILD-PLAN.md): milestones, evals and the cut list.
