# Driving a run for someone

This is for a coding assistant asked to translate a story with keikaku on behalf of a person who isn't technical. They choose how the English should sound; you run the commands and relay what the house says. Everything below runs from the repo root.

## Before you start

- `uv sync` once. A live run needs `MODEL_API_KEY` in `.env` (a Meta Model API key). Without one, only a recorded story can be replayed: `bansan`, `shuchu`, `shiken` or `shokikan`.
- The works the house can translate are in `fixtures/works.json`; a run takes the work's id, such as `bansan`.
- Every run is priced before it starts and refused if it won't fit its cap. If it's refused, tell the person the estimate and ask before raising `--cap`.

## The steps

1. **Start the run with a checkpoint.** `uv run keikaku run <work> --checkpoint`. The house reads the story, writes its reading and the story bible, drafts the first page once in each voice it thinks the story allows, and stops. Nothing else is drafted yet.

2. **Write out the checkpoint.** `uv run keikaku checkpoint <work>` writes three files and prints their paths: `reading.md` (what the house thinks the story turns on), `bible.md` (who everyone is, the style, the repeated images, the hard spots) and `voices.md` (each voice's name and line, and page 1 in it). Under their titles, `reading.md` and `bible.md` are word for word what every later stage reads.

3. **Show the person what the house made, in plain words.** Read the files yourself and tell them, briefly, what the house thinks the story turns on. Then show them the voices as the actual English of page 1, side by side or one after the other, each with its one-line description, and say which one the house would pick (the first). Don't summarise the voices instead of showing them: the English is what they're choosing between. Offer the bible if they want detail; most people won't.

4. **Take their note in their own words.** Ask what they'd change, if anything. Whatever they say, pass it on verbatim: `uv run keikaku steer <work> "their note"`. Don't rephrase it, translate it into technical terms or add to it; the house is built to interpret a reader's words, and your paraphrase would be a second reader's.

5. **Show the reply and the new page.** The command prints the house's reply, what it changed, and any question it has, and updates the three files. Read the reply to them, and show page 1 again from the end of `voices.md`, so they see the effect as English rather than a description of it. If the house asked a question, put it to them and send their answer as the next note.

6. **Repeat until they're happy.** Each note is one more round: on a short story a round costs about a quarter of a dollar, and nothing else is drafted until they approve. If they want a different voice rather than a change to this one, that's a choice for the next step, not a note.

7. **Approve in the voice they chose.** `uv run keikaku approve <work> --voice N`, with N as `voices.md` numbers the voices (from 0).

8. **Carry on.** `uv run keikaku run <work> --from draft`. The rest of the run needs nobody. Tell them it is running, and that the finished edition will be in the data folder (`releases/`), and on the site if the site is served from this database.

## What not to do

- Don't steer on their behalf. If they have no note, approve; the house's choices stand.
- Edit `reading.md`, `bible.md` or a voice's heading and italic line in `voices.md` only when the person asks you to change those words themselves, and change exactly what they asked. The next `checkpoint`, `steer` or `approve` takes the edit and every later stage reads it; the rest of `voices.md` (the drafted pages, the notes) is never read back. For anything they say about how it should read, send a note instead.
- If a command says the run isn't waiting, it has been approved or never stopped at a checkpoint. Tell them so; don't start a new run without asking, because it costs money again.
- Every command acts on the latest run of the work; add `--run N` to pick another.
