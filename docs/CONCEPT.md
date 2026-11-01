# keikaku — concept

Written 27 Oct 2026, the second day of the hackathon. Architecture: `ARCHITECTURE.md`. Order of work: `BUILD-PLAN.md`.

## Pitch

**keikaku is a small publishing house of Meta Muse agents, run by one human editor, that brings stories nobody has translated into English, starting with Japanese, and shows every doubt, argument and decision behind each line.**

Thousands of Japanese books are free to read on Aozora Bunko, and no translator is coming for most of them. Today an English reader who wants one gets Google Translate on a badly formatted page. keikaku gives them a readable, annotated edition, honest about being machine-made, with every decision behind it visible: a window into another world. And it's a starting point, not a final word: readers react, argue and propose fixes, the way Wikipedia articles and fan translations get better.

It's useful without anyone's sign-off. When a person does check a passage, the page says so; until then, it says it hasn't been.

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
| Student | **Student** edition: sourced notes, alternatives and decision history (a literal crib later). Parallel Japanese with furigana is a layout any edition can switch on. Browses the Catalogue for a text to study. It's an edition, not a tutor. |
| Translator | Browses the **Catalogue**. Reads the style sheet and queries. Finds something to pitch to a press. |
| Bilingual reader | Flags "I think this is wrong" with a reason; proposes a fix to a span. A bilingual reader who checks a passage against the Japanese can mark it *human-reviewed*, and their name goes on it. |
| The editor | Reviews the checkpoint before a full run (crux, reading, voice, key bible choices), decides forks, makes standing rules, locks lines, dictates notes, signs the edition. Only the checkpoint holds a run, and only when an editor is assigned; everywhere else, until the editor rules, the department head's pick stands and is labelled as such. A text with no editor runs straight through and says so. |

## The community concept

Built from publishing, fan translation, Wikipedia and web-fiction comments, all of it visible in the UI.

- **Editions, not versions.** One base translation and three presentations. Switching keeps your place and says what changed ("3 terms differ in this paragraph"), so the switch itself teaches.
- **Reactions on two axes.** *How it reads* (beautiful / confusing / sounds off / made me stop) is kept apart from *Is it right* (needs a reason). No counts as rankings. The editor sees a heatmap.
- **Proposals become queries.** Select a span, suggest a replacement, pick a reason. Accuracy goes to Source check, flow to Editorial, notes to Fact-check. The owner answers *accepted / stet / revised*. Rejections stay visible with a reason.
- **Talk starts from the record.** Each paragraph has a flat, pre-moderated comment thread that opens with the agents' original debate, so readers argue with the record rather than from scratch. Comments don't change the text; proposals can. Page by page, with moderation: `SITE.md`.
- **Trust ladder.** Reader → contributor → bilingual reviewer → editor. For now, the editor promotes people by hand.
- **Honest labels.** Every paragraph says in words how far it got: *draft* (one machine pass), *house-checked* (through Source check, Editorial and Fact-check), *editor-approved*, or *human-reviewed* (a bilingual reader checked it against the Japanese). People are round and named; agents are square and named by department, never given personas. A seal marks human sign-off. Credits and a colophon (奥付) are on every edition, with the Aozora Bunko attribution.

## What gets translated next

Readers help choose. The editor still decides.

- **"I'd read this"** on every Catalogue entry, one vote per reader. The Catalogue can sort by most wanted, but its default order isn't a leaderboard.
- **Request any text, from Aozora or beyond.** Search the Aozora index, or give a title, author and link. No uploads and no pasted text.
- **Rights first.** Aozora works show their status straight from the index. Requests from elsewhere go to Acquisitions: an agent checks the author's dates, first publication and any existing English translation, writes a short reader's report, and marks the request *eligible*, *in copyright* or *can't tell*. The editor confirms before anything is translated.
- **In-copyright books stay on the wanted list.** We never translate them, but the list shows what readers want brought into English, which is useful to translators and presses.
- Reasons attached to requests are pre-moderated and flat, like comments. Votes and requests are rate-limited.

## Scope

**By 4 Nov:** the showcase in Casual and Curious editions (Student if it holds); the experiments as labelled machine drafts, including the hard text's visible failures; the Setsu 1918 comparison; **the shelf**: as many of the short Catalogue titles as the budget allows, run through the house with no editor and labelled *house-checked*, so the library is something to browse rather than a promise; the Catalogue (~100–200 reader's reports generated on Meta models) with votes and requests; the live House on preset passages, with replay; reactions and proposals (pre-moderated); the evals; README and video.

**Later:** open accounts and a trust ladder with a calibration set; any Aozora text on request; longer works; funding targets for wanted books; EPUB and print; other source languages (the house is built per language; see `SITE.md`, "How it grows").

**Never:** ranking passages by popularity, AI personas with human names, or copy saying "human-quality" or "effortless".
