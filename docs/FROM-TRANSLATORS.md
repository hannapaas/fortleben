# keikaku — what we took from translators and editors

Written 30 Oct 2026. Most machine translation research treats translation as a sentence-level prediction problem. keikaku is modelled on something older: how literary translators and the publishing houses around them actually make a book. This is the map from their practice to our design, so it's clear which parts are borrowed and where they live.

## The practice, and where it is in keikaku

| How translators and editors work | In keikaku | Where |
|---|---|---|
| **Read the whole book first**, often twice, to form a reading before translating a word | The first read: Wonder writes the house's reading, starting from the crux of this particular text; a second reader checks the crux | `STORY-STATE.md` §0 |
| **Read around the book**: the author's other work, their life, the period | A short background brief (an intern with web search) on the author, period and reception, given to the first read | below |
| **Find the voice on the opening pages**, often drafting them several times before going on | A voice trial: the first page drafted two or three ways, from different readings of the voice; one is chosen and becomes the reference | below |
| **The sample translation** an acquiring editor reads before committing to a book | The editor's sample checkpoint on the first page | `BUILD-PLAN.md` M5 |
| **A fee per 1,000 words and a deadline**, so time is spent where the book is hard | 100 ink per manuscript sheet, triage into plain, tricky and hard | `RUNNING-A-TEXT.md` |
| **Draft fast, leaving alternatives in the line** ("glum/downcast/low") to settle later with more of the book in view | Translation may leave a few marked alternatives in a draft; revision settles them | below |
| **Bracket hard spots and come back to them** | Translator notes, hard-spot flags, and *flagged, unresolved* when the budget runs out | `RUNNING-A-TEXT.md` §1 |
| **Revise against the source** | Source check on every page, every change | `ARCHITECTURE.md` §1 |
| **Revise without the source, reading aloud** for voice and rhythm | Editorial reads the English alone, a scene at a time | `RUNNING-A-TEXT.md` pass 5 |
| **The editor's letter**: big-picture notes on the whole draft before any line edits | Wonder reads the whole English draft against the reading and writes a letter: where the voice drifts, where a character sounds wrong, where the crux slips | below |
| **The style sheet** a copy-editor builds | The ledger and style sheet in the story bible | `STORY-STATE.md` §1 |
| **Queries, not silent changes**; stet; the translator owns the wording | Query lifecycle; Translation owns the English; heads select, never merge | `ARCHITECTURE.md` §1 |
| **校閲 (kōetsu)**: Japanese houses' fact and continuity checkers, every query with its evidence | Fact-check and the whole-text continuity read; every query carries evidence | `ARCHITECTURE.md` §1 |
| **The translator's note or afterword**, the one place the translator is visible | The house's reading, published with the edition and labelled as the house's | `STORY-STATE.md` §0 |
| **Retranslation and second editions** | Versioned releases (v1, v1.1) with changelogs | `ARCHITECTURE.md` §2 |

## The additions in more detail

**Background brief.** Before the first read, an intern spends a few searches on the author's life, the period, the work's reception and anything the text alludes to. It's a page of notes with sources. It informs the reading; it's never presented as the author's view, and it doesn't reproduce the commentary in the source edition.

**Voice trial.** Translators often say the first pages are the hardest because that's where the voice is found, and they redo them until it settles. So Translation drafts the first page two or three ways, each from a different take on the voice that the reading allows (drier or warmer, plainer or more formal). Source check reads all of them. The head picks one, with a reason; it's the editor's sample checkpoint if the editor has time, and otherwise the head's pick stands. The chosen page then sits in every later call's context as the voice reference. It's a cheap way to make the voice a decision rather than an accident.

**Alternatives in the draft.** A drafting call that can't choose between two renderings without knowing what comes later may leave both, marked. Revision, with more of the text done, picks one. This keeps the first pass fast and stops the model committing early to a word the rest of the book will contradict.

**The editor's letter.** Span queries catch local problems. They don't catch a draft that is accurate line by line and still wrong as a whole: a narrator who sounds too educated, a character whose warmth has drained out, an ending that's been made more hopeful than the Japanese. A real editor's first response to a manuscript is a letter about exactly this. So after the first full draft, Wonder reads the whole English with the reading and writes a short letter. Translation answers it the way a translator answers an editor: accept, push back with a reason, or revise, and every revision goes back through Source check.

## A shared vocabulary for what goes wrong

Antoine Berman ("Translation and the Trials of the Foreign", 1985) listed the ways translations deform their originals, among them **rationalisation** (making the syntax tidier and more logical), **clarification** (spelling out what was left implicit), **expansion**, **ennoblement** (making it more elegant or literary than the original), **qualitative impoverishment** (swapping vivid words for flatter ones), **destroying rhythms**, **destroying the networks of repeated words** that tie a text together, and **flattening vernacular**. Forty years on, it reads like a description of a fluent language model.

We use it as a vocabulary, not a checklist. Critics can name what they're seeing ("this is ennoblement: she'd never say *melancholy*") and the reader sees the name in the margin with a one-line explanation. Which tendencies matter depends on the text; the reading says which ones to watch for in this one.

## What we haven't borrowed

- **Mapping Japanese dialect onto an English one.** Translators disagree; we mark dialect through rhythm and word choice instead, and say in a note which dialect it is.
- **Pastiche period English.** Formality follows the source; no fake-Victorian.
- **Silent improvements.** A translator sometimes quietly fixes an author's slip. We don't: it stays, with a note.

## Sources

- Daniel Hahn, *Catching Fire: A Translation Diary* (Charco Press, 2022).
- Edith Grossman, *Why Translation Matters* (Yale UP, 2010). Kate Briggs, *This Little Art* (Fitzcarraldo, 2017).
- Antoine Berman, "La traduction comme épreuve de l'étranger" (1985); in English as "Translation and the Trials of the Foreign", in Venuti (ed.), *The Translation Studies Reader*.
- Lawrence Venuti, *The Translator's Invisibility* (Routledge, 1995).
- Polly Barton, *Fifty Sounds* (Fitzcarraldo, 2021).
- Peter Ginna (ed.), *What Editors Do* (Chicago, 2017).
