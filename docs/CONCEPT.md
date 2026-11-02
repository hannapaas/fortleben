# Fortleben — concept

Written 27 Oct 2026, the second day of the hackathon. Architecture: `ARCHITECTURE.md`. Order of work: `BUILD-PLAN.md`.

## Pitch

**Fortleben is a platform for stories nobody has translated into English, starting with Japanese. Its translations are made by keikaku, a small publishing house of Meta Muse agents run by one human editor, and every doubt, argument and decision behind each line is a tap away.**

Thousands of Japanese books are free to read on Aozora Bunko, and no translator is coming for most of them. Today an English reader who wants one gets Google Translate on a badly formatted page. Fortleben gives them a readable, annotated edition, honest about being machine-made, with every decision behind it visible: a window into another world. And it's a starting point, not a final word: readers react, argue and propose fixes, the way Wikipedia articles and fan translations get better.

It's useful without anyone's sign-off. When a person does check a passage, the page says so; until then, it says it hasn't been.

## Words

- **Fortleben:** the platform and the project. German for living on; Walter Benjamin's word, in "The Task of the Translator", for the afterlife a work has in translation. The translations here aren't final texts; they go on changing.
- **keikaku:** the translation house inside it: the agents, departments, queries and editors' desk. Japanese for plan, from the fansub joke about a translator's note that explains nothing; the test every note here has to pass.
- **Work:** the original text, with its rights record. You browse by work, grouped by the language it was written in.
- **Edition:** one English translation of a work. Every edition says plainly whose it is: **the keikaku house** (machine-made, labelled paragraph by paragraph), **the house steered by a named editor**, or **a person's own translation**, shown with the translator's name and year. A person's translation is named and credited, and linked only if they're happy to be; it's hosted here only if it's public domain or its translator licenses it to us. Opening a work opens the house edition; the others are listed under the title, one tap away. A work with only the house edition shows no list.
- **View:** how you read an edition: **Clean** (like a printed novel, essential notes only), **Curious** (every note marked, each paragraph's status, the Japanese a tap away) or **Annotated** (side by side with the original, notes open). Views are presets over the same text; anything in them can be changed by hand. (Earlier drafts called the views Casual, Curious and Student and gave each its own rendering of key terms; that's gone: there's one English text per edition.)
- **Run:** one pass of a work through the house, producing or revising an edition. Each published version of an edition (v1, v1.1) is a **release**, a word for the record and the changelog rather than for readers.

## What it makes

| Part | What it is |
|---|---|
| **The Library** | A showcase edition, the shelf and the other texts (one deliberately hard), each in three views, with every line's history a tap away |
| **The Catalogue** | Reader's reports on untranslated works: what each is about, why read it, how hard it is, and the evidence for "untranslated". Readers vote for what they'd read and request texts from Aozora or beyond |
| **The House** | How the house works, walked through on one real run: the text's route through the stages, picked moments at each (queries, forks, the editor's rulings, revisions), and every stage's full output a click away |
| **The Exhibit** | Passages side by side with one-shot machine translation and, for one, a 1918 human translation, with arrows and margin notes saying in plain words what went wrong and why, ours included |

## Who it's for, and what they do

| User | What they do on the site |
|---|---|
| Casual reader | Reads the **Casual** view: clean text, no notes in the flow. Reacts to a paragraph. |
| Culturally curious reader | Switches to **Curious**: honorifics kept, ruby over key terms, two-sentence tap-notes. Taps a line to see the debate behind it. |
| Student | **Student** view: sourced notes, alternatives and decision history (a literal crib later). Parallel Japanese with furigana is a layout any view can switch on. Browses the Catalogue for a text to study. It's an edition, not a tutor. |
| Translator | Browses the **Catalogue**. Reads the style sheet and queries. Finds something to pitch to a press. |
| Bilingual reader | Flags "I think this is wrong" with a reason; proposes a fix to a span. Their comments sit in the margin with everyone else's. |
| The editor | Reviews the checkpoint before a full run (crux, reading, voice, key bible choices; not built yet), decides forks, makes standing rules, locks lines, writes notes, signs the edition. Only the checkpoint holds a run, and only when an editor is assigned; everywhere else, until the editor rules, the department head's pick stands and is labelled as such. A text with no editor runs straight through and says so. |

## The community concept

Built from publishing, fan translation, Wikipedia and web-fiction comments, all of it visible in the UI.

- **Views, not rival translations.** One English text per edition and three views of it, from a clean page to a busy annotated one. Switching keeps your place. A second translation of the same work, by another editor or by a person, is a second edition, named as such.
- **Reactions on two axes.** *How it reads* (beautiful / confusing / sounds off / made me stop) is kept apart from *Is it right* (needs a reason). Readers can react to a paragraph, a note or an alternative in the debate. No counts as rankings, and a reaction never changes the text by itself. The editor sees a heatmap.
- **Proposals become queries.** Select a span, suggest a replacement, pick a reason. It goes to the desk as a note, beside the readers' (a note on a footnote goes to fact-check), and comes back *taken*, *declined* or *forked*, with the reason. Rejections stay visible with a reason. No person has to approve a comment or a proposal first; a model screens for abuse and the editor can remove (`SITE.md`).
- **Talk starts from the record.** Each paragraph has a flat comment thread, screened by a model rather than a person, that opens with the agents' original debate, so readers argue with the record rather than from scratch. Comments don't change the text; proposals can. Page by page, with moderation: `SITE.md`.
- **Trust ladder.** Reader → contributor → editor. For now, the editor promotes people by hand.
- **Honest labels.** Only finished house work is published, and each edition says once that it was translated and checked by agents. Paragraphs an editor has signed off say so in words: *editor-approved*. People are round and named; agents are square and named by department, never given personas. A seal marks human sign-off. Credits and a colophon (奥付) are on every edition, with the Aozora Bunko attribution.

## What gets translated next

Readers help choose. The editor still decides.

- **"I'd read this"** on every Catalogue entry, one vote per reader. The Catalogue can sort by most wanted, but its default order isn't a leaderboard.
- **Request any text, from Aozora or beyond.** Search the Aozora index, or give a title, author and link. No uploads and no pasted text.
- **Rights first.** Aozora works show their status straight from the index. Requests from elsewhere go to Acquisitions: an agent checks the author's dates, first publication and any existing English translation, writes a short reader's report, and marks the request *eligible*, *in copyright* or *can't tell*. The editor confirms before anything is translated.
- **Existing translations are recorded, and credited where that's welcome.** Before any edition is published, a search that includes fan and blog translations, recorded in the work's rights record. A published translation is credited on the work's page by name and year, and linked where it's freely available (Project Gutenberg); a hobbyist's is named only with their agreement. "Untranslated" is never claimed without that search, dated. (「晩餐」 has a hobbyist's translation from 2020, so its page names none and claims nothing.)
- **In-copyright books stay on the wanted list.** We never translate them, but the list shows what readers want brought into English, which is useful to translators and presses.
- Reasons attached to requests are screened and flat, like comments. Votes and requests are rate-limited.

## Scope

**By 4 Nov:** the showcase in Casual and Curious views (Student if it holds); the other texts as labelled machine drafts, including the hard text's visible failures; the Setsu 1918 comparison; **the shelf**: as many of the short Catalogue titles as the budget allows, run through the house with no editor and labelled *house-checked*, so the library is something to browse rather than a promise; the Catalogue (~100–200 reader's reports generated on Meta models) with votes and requests; the House walkthrough of the showcase run; reactions, comments and proposals (model-screened); the evals; README and video.

**Later:** open accounts and a trust ladder with a calibration set; any Aozora text on request; longer works; funding targets for wanted books; EPUB and print; other source languages (the house is built per language; see `SITE.md`, "How it grows").

**Never:** ranking passages by popularity, AI personas with human names, or copy saying "human-quality" or "effortless".
