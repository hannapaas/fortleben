# keikaku — what we took from translators and editors

Most machine translation research treats translation as a sentence-level prediction problem. keikaku is modelled on something older: how literary translators and the publishing houses around them actually make a book. This is the map from their practice to our design, so it's clear which parts are borrowed and where they live.

## The practice, and where it is in keikaku

| How translators and editors work | In keikaku | Where |
|---|---|---|
| **Read the whole book first**, often twice, to form a reading before translating a word | The first read: Wonder writes the house's reading, starting from the crux of this particular text; a second reader checks the crux | `STORY-STATE.md` |
| **Find the voice on the opening pages**, often drafting them several times before going on | The reading offers voice takes; at the checkpoint the first page is drafted in each and a person picks one. The house's first page becomes the voice reference for every later page | below |
| **The sample translation** an acquiring editor reads before committing to a book | The checkpoint after the bible: the editor reads the reading, the bible and the first page in each voice, steers with notes, and approves before the rest is drafted | `EDITORS-DESK.md` |
| **A fee per 1,000 words and a deadline**, so time is spent where the book is hard | A run is estimated and reserved before it starts, from an allowance counted in drops of ink per manuscript sheet (400 characters of the original); the desk works only where the readers found something | `EDITORS-DESK.md` |
| **Draft fast, leaving alternatives in the line** ("glum/downcast/low") to settle later with more of the book in view | The drafter writes English first and leaves a choice it can't settle in a translator's note, which the desk sees | below |
| **Bracket hard spots and come back to them** | The bible's hard spots, and the translator's notes the desk sees | `STORY-STATE.md` |
| **Revise against the source** | The faithful reader on every part, meeting the Japanese first; the desk decides | `STAGES.md` |
| **Revise without the source, reading aloud** for voice and rhythm | The readable reader meets the English first, the Japanese to hand; the final read's first pass reads the English as a whole | `STAGES.md` |
| **The style sheet** a copy-editor builds | The style sheet in the story bible, and the copy desk that holds names, terms and italics to it | `STORY-STATE.md` |
| **Queries, not silent changes**; stet | Readers' margin notes; the desk takes, declines or forks each, with a reason, and every note is accounted for; heads select, never merge | `STAGES.md` |
| **校閲 (kōetsu)**: Japanese houses' fact and continuity checkers, every query with its evidence | The final read's continuity pass over the whole text; every reader's note quotes the Japanese | `STAGES.md` |
| **The translator's note or afterword**, the one place the translator is visible | The house's reading, published with the edition and labelled as the house's | `STORY-STATE.md` |
| **Retranslation and second editions** | Versioned releases (v1, v1.1) with changelogs | `ARCHITECTURE.md` |

## The additions in more detail

**Finding the voice.** Translators often say the first pages are the hardest because that's where the voice is found, and they redo them until it settles. The reading offers two or three takes on the voice (drier or warmer, plainer or more formal). At the checkpoint the first page is drafted once in each, and the editor reads them, steers with notes and picks one; the house's first page then sits in every later call as the voice reference. A model picking between the same trials didn't help: it picked the voice the reading listed first and the English was no better (`experiments/03-stiffness.md`). A person choosing is different, and a page in each voice is the cheapest point at which to be wrong.

**Alternatives in the draft.** A drafting call that can't choose between two renderings without knowing what comes later says so in a translator's note, with both readings and what would settle it. The desk sees those notes; the readers don't, so their first reaction is uncoached.

**The whole-text look.** Margin notes catch local problems. They don't catch a draft that is accurate line by line and still wrong as a whole: a narrator who sounds too educated, a character whose warmth has drained out, an ending that's been made more hopeful than the Japanese. A real editor's first response to a manuscript is a letter about exactly this. In keikaku the final read does that job: it reads the finished English whole, as a reader, before it reads it against the Japanese.

## A shared vocabulary for what goes wrong

Antoine Berman ("Translation and the Trials of the Foreign", 1985) listed the ways translations deform their originals, among them **rationalisation** (making the syntax tidier and more logical), **clarification** (spelling out what was left implicit), **expansion**, **ennoblement** (making it more elegant or literary than the original), **qualitative impoverishment** (swapping vivid words for flatter ones), **destroying rhythms**, **destroying the networks of repeated words** that tie a text together, and **flattening vernacular**. Forty years on, it reads like a description of a fluent language model.

We use it as a vocabulary, not a checklist. The readers can name what they're seeing ("this is ennoblement: she'd never say *melancholy*") and the reader sees the name in the margin with a one-line explanation. Which tendencies matter depends on the text; the reading says which ones to watch for in this one.

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
