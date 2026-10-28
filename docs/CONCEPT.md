# keikaku — concept

Written 27 Oct 2026, the second day of the hackathon. Architecture: `ARCHITECTURE.md`. Order of work: `BUILD-PLAN.md`.

## Pitch

**keikaku is a small publishing house of Meta Muse agents, run by one human editor, that brings Japanese stories nobody has translated into English, and shows every doubt, argument and decision behind each line.**

Thousands of Japanese books are free to read in Japanese, on Aozora Bunko, and no translator is coming for most of them. keikaku doesn't claim to replace one. It produces honest, labelled, annotated editions, a window into another world, and shows its working.

## What it makes

| Part | What it is |
|---|---|
| **The Library** | A showcase edition plus experiments, each in reader editions, with every line's history a tap away |
| **The Catalogue** | Reader's reports on untranslated works: what each is about, why read it, how hard it is, and the evidence for "untranslated". Readers vote for what they'd read and request texts from Aozora or beyond |
| **The House** | The agents at work, live or replayed: departments, queries, forks, interns, budgets |
| **The Evals** | One-shot vs a translate–reflect–revise loop vs keikaku vs a 1918 human translation; a long-context test; honest losses |

## Who it's for, and what they do

| User | What they do on the site |
|---|---|
| Casual reader | Reads the **Casual** edition: clean text, no notes in the flow. Reacts to a paragraph. |
| Culturally curious reader | Switches to **Curious**: honorifics kept, ruby over key terms, two-sentence tap-notes. Taps a line to see the debate behind it. |
| Student | **Student** edition: parallel Japanese with furigana, a literal crib, sourced notes, decision history. Browses the Catalogue for a text to study. It's an edition, not a tutor. |
| Translator | Browses the **Catalogue**. Reads the style sheet and queries. Finds something to pitch to a press. |
| Bilingual reader / reviewer | Flags "I think this is wrong" with a reason; proposes a fix to a span. Invited reviewers mark segments *source-checked*, and their name goes on the seal. |
| The editor | Approves the style sheet, sets the sample checkpoint, decides forks, makes standing rules, locks lines, dictates notes, signs the edition. |

## The community concept

Built from publishing, fan translation, Wikipedia and web-fiction comments, all of it visible in the UI.

- **Editions, not versions.** One base translation and three presentations. Switching keeps your place and says what changed ("3 terms differ in this paragraph"), so the switch itself teaches.
- **Reactions on two axes.** *How it reads* (beautiful / confusing / sounds off / made me stop) is kept apart from *Is it right* (needs a reason). No counts as rankings. The editor sees a heatmap.
- **Proposals become queries.** Select a span, suggest a replacement, pick a reason. Accuracy goes to Source check, flow to Editorial, notes to Fact-check. The owner answers *accepted / stet / revised*. Rejections stay visible with a reason.
- **Talk starts from the record.** Each passage's thread opens with the agents' original debate, so readers argue with the record rather than from scratch.
- **Trust ladder.** Reader → contributor → bilingual reviewer → editor. For now, reviewers come in by invite.
- **Honest labels.** Every paragraph shows *machine draft / edited / source-checked / reviewed* in words. People are round and named; agents are square and named by department, never given personas. A seal marks human sign-off. Credits and a colophon (奥付) are on every edition, with the Aozora Bunko attribution.

## What gets translated next

Readers help choose. The editor still decides.

- **"I'd read this"** on every Catalogue entry, one vote per reader. The Catalogue can sort by most wanted, but its default order isn't a leaderboard.
- **Request any text, from Aozora or beyond.** Search the Aozora index, or give a title, author and link. No uploads and no pasted text.
- **Rights first.** Aozora works show their status straight from the index. Requests from elsewhere go to Acquisitions: an agent checks the author's dates, first publication and any existing English translation, writes a short reader's report, and marks the request *eligible*, *in copyright* or *can't tell*. The editor confirms before anything is translated.
- **In-copyright books stay on the wanted list.** We never translate them, but the list shows what readers want brought into English, which is useful to translators and presses.
- Reasons attached to requests are pre-moderated and flat, like comments. Votes and requests are rate-limited.

## Scope

**By 4 Nov:** the showcase in Casual and Curious editions (Student if it holds); the experiments as labelled machine drafts, including the hard text's visible failures; the Setsu 1918 comparison; the Catalogue (~100–200 reader's reports generated on Meta models) with votes and requests; the live House on preset passages, with replay; reactions, proposals (pre-moderated) and invited reviewers; the evals; README and video.

**Later:** open accounts and a trust ladder with a calibration set; any Aozora text on request; longer works; EPUB and print; other languages.

**Never:** ranking passages by popularity, AI personas with human names, or copy saying "human-quality" or "effortless".
