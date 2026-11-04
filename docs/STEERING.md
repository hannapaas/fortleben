# keikaku — steering a run: who uses the house, and how

Written 3 Nov 2026. `EDITORS-DESK.md` says how a run works for the person paying for it; `STAGES.md` is the engine's view. This is about the two people a translation pipeline is useless without: the one who runs it and the one who reads the result.

## Why this matters more than the pipeline

An agent pipeline that translates well is one part of the problem, and on its own it serves nobody. The code could be open-sourced tomorrow and it would still be a confusing repo that only a programmer with a Meta key and an afternoon could use. So the submission has two goals that are not the engine:

1. **Someone can run it.** Not us: a reader, a student, a translator who wants a draft of a story to argue with. They are unlikely to be technical, and the house needs their taste, not only their money. The way in has to be a page, and the way to steer has to be plain words.
2. **Someone benefits from the output.** A reading experience good enough that a person would read a whole story on the site, not a demo of a pipeline. Everything in `SITE.md` is in service of that.

The engine is deliberately opinionated (`NORTH-STAR.md`): taste is the human's job, made into leverage, and nothing hangs on human review. Steering is where those two meet: a few decisions, made where being wrong is cheapest, that the house then carries through every page.

## What a person steering a run does

Optional at every point. A run with nobody steering it goes straight through and says so.

| When | What they see | What they can do |
|---|---|---|
| **Before the draft (the checkpoint)** | The house's reading: the crux (and a second reader's crux if the two disagreed), the voice takes, and the first page drafted in each voice; the story bible (cast, style sheet, motifs, hard spots). | Pick a voice. Write a note in plain words: anything from "the daughter is older than this reads" to "less formal". Or edit the files themselves (the reading, the voices, the analysis) by hand. Approve and let it run. |
| **After a note** | The house's reply: what it changed in the reading or the bible, what it didn't and why, and anything it needs to ask back; and the first page drafted again under the amended bible, so the effect is visible as English, not as a description of English. | Write another note, or approve. As many rounds as they like: a round costs a few cents, and not a line of the book is drafted until they approve. |
| **During the run** | What the house is doing now, stage by stage, and what each stage produced: the drafts as pages, the readers' notes, the desk's decisions. | Watch, or come back later. Pause or stop. |
| **At the end, and any time after** | The edition, published under their name, and the forks and final-read notes left to them. | Rule on a fork, or leave the house's choice standing. Change the English of any paragraph by hand, from the desk's *Edit it*. Read it on the site like anyone else. |

What happens to a note is the only new piece of engine. One call, to the model that wrote the reading, with the reading, the bible, the first page in each voice and the editor's words. It returns a reply for the editor, the bible and reading amended where the note changes them, and whether it has a question the editor needs to answer before the draft is worth starting. Code saves the new versions and shows the reply; the editor answers or approves. The loop ends when the editor approves, never on the house's decision. There is no agent choosing between "edit, ask, or translate": the house always amends and replies, and the person always decides when to go on. That is one prompt, one schema, and a status on the run.

Notes become house style, not instructions. A note like "I want the mother to sound colder" goes into the bible as what the text does ("the mother's speech is clipped; the English keeps it short and unsoftened"), never as "the editor wants", because every reader and the desk carries the bible and would otherwise parrot the editor into the margin.

A note like "this sounds too modern; I want the period to show more" is the ordinary case: the register and the style sheet change, the reading says what the period's plainness sounds like in English, the first page comes back in that English, and the person sees whether that is what they meant before anything else is spent. A misunderstanding costs one more note.

**Forks don't wait.** A fork is one line where the two readers wanted opposite things and the reading didn't settle it (at most five a run, by code, plus the crux if the two first readers disagreed); the desk's choice goes into the text and the run carries on, labelled as the house's pick. The person can rule on it afterwards, from the desk or the margin, and the other side goes in through one desk call; or never, and nothing is stuck. Nobody has to handle forks to get an edition.

**The reading and the bible are published with the edition**, as a section of it a reader can open: the crux, the voice, who everyone is, what the English does with the motifs. Under it, one line: if you'd read this story differently, start your own edition and steer it. That is the door from reader to editor, and the honest version of "this is one reading".

## Three ways in, one engine

| | Terminal | A terminal driven by an assistant | The site |
|---|---|---|---|
| Who | A programmer | Anyone with a coding assistant and this repo | Anyone with a link |
| How it pauses | `keikaku run <work> --checkpoint` stops at the checkpoint, with page 1 drafted in each voice. `keikaku checkpoint <work>` writes the reading, the bible and the voices as Markdown files in the data folder (`checkpoints/<work>/`). `keikaku steer <work> "note"` sends a note, prints the reply and rewrites the files. `keikaku approve <work> --voice N` approves, and `keikaku run <work> --from draft` carries on. | The same commands, with the assistant reading the files aloud and relaying the person's answers; `AGENTS.md` tells an assistant how. | The desk page shows the same things as pages, with a note box and an approve button. |
| Where the result goes | The data folder, and the site if it's the site's database | Same | Published on the site under the person's name |

The terminal path is the minimum and it's cheap: the orchestrator already stops and resumes between any two stages, and a run already records everything it would show. The site path is the same state rendered by `/desk`. Nothing streams: the desk reads the record, as the House does.

## Paying: bring your own key

Allowances in drops (`EDITORS-DESK.md`) stay for invited editors, judges and reviewers: a link with an allowance on it and a short story it covers. For everyone else the site takes no payments; instead a person signs up with a name, an email address, a password and their own Meta Model API key, signs in with the email and password from then on, and their runs spend the key. Invite links still exist for editors we invite. The house still prices a run before it starts and refuses one its caps won't cover, so a run can't run away; but what a key can spend is set on Meta's side by its owner, which is where it belongs.

What that costs us: the key has to be held while a run goes, in the background, on our server. It's stored encrypted with the site secret, never logged, shown back only as its last four characters, and deletable from the desk; a run in flight uses it and nothing else does. Litestream backs up the database, so the backup holds the encrypted key and nothing readable. The person's name goes on the edition as *curated by &lt;name&gt; with keikaku*, which is also the honest line about whose models made it.

The sign-up page says it plainly: make a key for this, put on it only what you're willing to spend, start small, and turn off automatic top-up. A run that runs out of credit stops where it is, with every page and stage it finished committed; the person tops up and resumes it from there, and the response cache means nothing is paid for twice. The engine already works this way (`STAGES.md`, "Stop and resume"); the desk needs only the message and the button.

A handful of people at once is the capacity, and the page says so: a run starts only if the house has room, and otherwise says when to try again, rather than queueing silently or falling over.

What it buys: an answer to "who is this for" that a judge can test with their own key, no payments, and editions on the site that weren't ours.

## What the desk page becomes

Not a chat. The person doesn't converse with the house; they read what it made and leave notes at one point. The page has, down the left, the files a run has produced so far (the reading, the bible, the voices, the drafts by page, the readers' notes, the desk's log) and, in the middle, the thing that's open: the checkpoint when the run is waiting, the run's log while it's going, the edition when it's done. Opening a file from the left sets it beside what's open. On a phone it's one column.

## Not in this

No rounds of the house arguing with the editor; one reply per note. No steering after the draft starts, other than forks, final-read notes and pause: a note mid-draft would mean redrafting, and the checkpoint exists so that isn't needed. No editing someone else's English: for anyone but the edition's editor, that's a proposal in the margin, like any reader's. No payments. No private runs.

## Build order

Lanes that can go at once, each a branch of `public/`:

1. **Engine: the checkpoint.** Built 3 Nov (`house/stages/checkpoint.py`, `house/steer.py`, `prompts/steer.md`). A `checkpoint` stage between `bible` and `draft` that drafts the first page in each voice take (the trial from experiment 3, cheap, kept this time because a person is choosing), records them, and sets the run `waiting` when the run's options ask for a checkpoint; `steer` as a prompt, a schema and a command; `--voice` (built 3 Nov) carries the choice. Tests on the fixture.
2. **CLI and `AGENTS.md`.** Built 3 Nov. `keikaku checkpoint` and `keikaku steer`, writing and reading Markdown in the data folder, and a page telling an assistant how to drive a run for someone.
3. **Site: sign-up and keys.** A sign-up page (name, key), encrypted storage, the desk showing the key's last four and a delete, the live client taking a per-run key, the lock on one run at a time made per person rather than site-wide.
4. **Site: the desk page.** The files-and-open-thing layout, the checkpoint view with voices side by side and the note box, the run log, forks to rule on.
5. **Site: the edition's credit line** and the curated-by shelf on the home page.

1 and 2 share the engine and go first or together; 3 and 4 depend on the checkpoint's states but can be built against the fixture's record; 5 is small. Testing is where the time goes: a run that waits in a background thread across a restart, a key that must never appear in a log, a note that changes the bible and the draft that follows it.

## The contract between lanes (3 Nov)

Four lanes build this at once. Each codes against this section and the fixtures, never against another lane's unfinished work (`CONVENTIONS.md`).

**Run options.** `checkpoint: true` makes the run pause after the bible. `voice: N` (from 0) is the voice take the draft is written in; the editor's pick, else 0.

**The checkpoint stage** (`house/stages/checkpoint.py`, between `bible` and `draft` in `orchestrator.STAGES`, name `checkpoint`). With `checkpoint` off it does nothing and the run goes on. With it on: it drafts the first page (`pager.pages(...)[0]`) once per voice take, with the drafting prompt and model the run uses, saves the document `checkpoint` (`ctx.save`, kind `checkpoint`), sets the run's `status` to `waiting` and `stage` to `checkpoint`, emits `checkpoint.waiting`, and the orchestrator returns without running further stages. The document:

```
{"takes": [{"label": "...", "line": "...", "english": [[pid, english], ...]}, ...],   # one per voice take, page 1
 "rounds": [{"note": "...", "reply": "...", "changed": ["..."], "question": "..." | null,
             "reading_version": n, "bible_version": n, "english": [[pid, english], ...]}, ...]}
```

**Steering** (`house/steer.py`):
- `steer(conn, client, run_id, note: str) -> dict`: one call (`prompts/steer.md`, `house/schemas/steer.json`, the model that wrote the reading) with the reading, the bible, page 1 in the current voice and the editor's note. It returns `reply`, `changed` (what it altered, a line each), `question` (or null), and the amended reading and bible, which are saved as new versions (`reading` and `bible` documents) only where they differ; then page 1 is drafted again in the current voice under the amended bible. The round is appended to the `checkpoint` document; `checkpoint.steered` is emitted with the round. Returns the round. The run stays `waiting`.
- `approve(conn, run_id, voice: int) -> None`: records `voice` in the run's options, emits `checkpoint.approved`, sets `status` to `queued`. Whoever called it then resumes the run from `draft` (`orchestrator.run(..., run_id=..., from_="draft")`, or `desk.resume`).
Notes become house style, never instructions: the steer prompt turns "I want the mother colder" into what the text does, so nothing in the bible says "the editor wants".

**Events** (`house/events.py`): `checkpoint.waiting` (the takes), `checkpoint.steered` (the round), `checkpoint.approved` (the voice).

**Statuses.** `run.status` gains `waiting`. `desk.resume` treats `waiting` like `interrupted`: resumable from `draft` once approved (status `queued`). A run that stopped because its key or cap ran out is `failed` with the error in its options, resumable as today; the desk says what to do in plain words.

**CLI.** `keikaku run <work> --checkpoint` pauses at the checkpoint and prints where the files are. `keikaku checkpoint <work>` writes `reading.md`, `bible.md` and `voices.md` (page 1 in each take, with the rounds so far) into the data folder under `checkpoints/<work>/` and prints their paths. `keikaku steer <work> "note"` runs one round and prints the reply. `keikaku approve <work> --voice N` approves. A file edited by hand since it was written is taken by the next `checkpoint`, `steer` or `approve` as the editor's version (below), and `keikaku run <work> --from draft` carries on. `AGENTS.md` at the repo root tells a coding assistant how to drive this for a person.

**The desk** (`house/desk.py`, `house/web.py`, `site/templates/desk.html`, `site/static/desk.js`): runs start with `checkpoint: true`. A `waiting` run shows the checkpoint: the reading, the voices with page 1 under each, the bible, the rounds so far, a note box and an approve button with the voice chosen. Routes: `POST /desk/<token>/runs/<id>/steer` (`{"note": ...}`, runs `steer` in the background, the page polls), `POST /desk/<token>/runs/<id>/approve` (`{"voice": N}`, approves and resumes). One run at a time per person, not per site; the page says when the house has no room.

**Accounts and keys** (`house/accounts.py`, `site/templates/signup.html`, `db/schema.sql`): `person` gains `api_key` (encrypted with `KEIKAKU_SECRET`, Fernet or equivalent in the standard library) and `key_tail`. `GET/POST /signup` makes a person from a name, an email address, a password and a key, and signs them in to `/desk`; `/login`, `/logout` and `/reset` do the rest (`EDITORS-DESK.md`, "As built"). Invited editors keep their links, which sign them in the same way. A person with a key has no allowance: their runs are capped by the run cap only, and the desk shows what the run spent in words, not drops. `desk.go` builds the client with that person's key (`make_client(conn, run_cap=..., api_key=...)`). The key is never logged or shown except as its last four characters; the desk has a delete-key button, and a person whose key is gone adds a new one there. The sign-up copy: make a key for this, put on it only what you're willing to spend, start small, turn off automatic top-up.

**The edition** (`house/edition.py`, `site/templates/read.html`): the reading and the bible are published with the edition as a section a reader can open, with one line under it inviting them to start their own edition from `/signup`. The notes stage (`house/stages/notes.py`, `prompts/notes.md`) also sees, for its part, the readers' notes the desk declined and the disagreements it recorded, so a note on the site can draw on the road not taken.

## The editor's own hand (4 Nov)

Notes are one way to steer; the other is to change the words directly. Both are recorded, and on the site both are published, so whatever an editor did to a translation, a reader can see it was them.

**The files, at the checkpoint.** Every stage after the checkpoint reads three things before its own input: the reading (`context.reading`), the voice (its name and line) and the bible (`context.bible`). Those are the files, word for word. An edit of the reading or the bible is kept as the document's `edited_text` and read in place of the stored fields; the voices are parsed back into the reading's `voice_takes` (`## Voice N: name`, then the line). Each edit is a new version of the document with a `document.edited` event holding before, after and who (`house/steer.py`, `edit`). A run nobody edits sends exactly what it did before, so the recordings still replay. A note sent after an edit is read against the edited version, and the amended reading or bible it returns replaces it; that replacement is recorded too, as keikaku's, so the appendix shows what the note did to the edit. Page 1 in the picked voice can be rewritten too, paragraph by paragraph (`edit_page`, kept in the checkpoint document, with a `document.edited` event, file `page`): approved in that voice, the draft takes it as its first page instead of drafting it, and every later page is told to match it; a note that redrafts that page replaces the edit, and says so in the record. Edits go in only while the run waits; once it is approved the files are what it was drafted from, and the analysis page publishes every edit as a diff, under the editor's name and the date. On the desk the files sit on the translation's own page while it waits, each shown once as text you can type in, as tall as itself; a change is saved with *Save* or Ctrl/Cmd-S, before a note or the approval goes, and when the page is left. In the terminal they are the files `keikaku checkpoint` writes; the next `checkpoint`, `steer` or `approve` takes what was changed since, for that run only, and an edit it can't take (the files were written for another run, or the run was approved) is said so and kept aside as `<name>.unused.md`, never written over. Nothing extra is logged for the terminal: a run on someone's own machine is theirs.

**The English, after publication.** The edition's editor, signed in, can change any paragraph from the reading page (`?edit=1`, linked from the desk as *Edit it*), at any time. Each change is a revision of the run's English with a `revision.created` event, cause `editor`, keeping before, after and who (`house/edition.py`, `edit`). The page shows the latest over the release; under the paragraph's `*`, each change comes first, marked as a person's (round), with the date and what it struck out and put in, and keikaku's own work follows, labelled as keikaku's. An edited paragraph carries a small round mark in every view, and the closing line says how many paragraphs the editor changed. Section headings aren't edited, and one editor can save at most 120 changes an hour. Nobody else can edit an edition, and the house's own editions can't be edited from the site.

