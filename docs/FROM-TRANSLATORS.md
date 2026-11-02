# keikaku — what we took from translators and editors

Written 30 Oct 2026. Most machine translation research treats translation as a sentence-level prediction problem. keikaku is modelled on something older: how literary translators and the publishing houses around them actually make a book. This is the map from their practice to our design, so it's clear which parts are borrowed and where they live.

## The practice, and where it is in keikaku

| How translators and editors work | In keikaku | Where |
|---|---|---|
| **Read the whole book first**, often twice, to form a reading before translating a word | The first read: Wonder writes the house's reading, starting from the crux of this particular text; a second reader checks the crux | `STORY-STATE.md` §0 |
| **Read around the book**: the author's other work, their life, the period | A short background brief (web search) on the author, period and reception, given to the first read. Not built yet | below |
| **Find the voice on the opening pages**, often drafting them several times before going on | The reading offers voice takes and the drafter writes in the first; the house's first page becomes the voice reference for every later page. A voice trial (the first page drafted in each voice, one picked) was tried and dropped | below |
| **The sample translation** an acquiring editor reads before committing to a book | The editor's checkpoint after the brief. Not built yet | `RUNNING-A-TEXT.md` §4 |
| **A fee per 1,000 words and a deadline**, so time is spent where the book is hard | A run priced before it starts; effort goes where the readers find problems. The allowance per manuscript sheet and the tiers are planned | `RUNNING-A-TEXT.md` |
| **Draft fast, leaving alternatives in the line** ("glum/downcast/low") to settle later with more of the book in view | The drafter writes English first and leaves a choice it can't settle in a translator's note, which the desk sees | below |
| **Bracket hard spots and come back to them** | Translator notes, hard-spot flags, and *flagged, unresolved* when the budget runs out | `RUNNING-A-TEXT.md` §1 |
| **Revise against the source** | The faithful reader on every part, meeting the Japanese first; the desk decides | `STAGES.md` |
| **Revise without the source, reading aloud** for voice and rhythm | The readable reader meets the English first, the Japanese to hand; the final read's first pass reads the English as a whole | `RUNNING-A-TEXT.md` §3 |
| **The editor's letter**: big-picture notes on the whole draft before any line edits | Wonder reads the whole English draft against the reading and writes a letter: where the voice drifts, where a character sounds wrong, where the crux slips. Not built yet | below |
| **The style sheet** a copy-editor builds | The style sheet in the story bible | `STORY-STATE.md` §1 |
| **Queries, not silent changes**; stet | Readers' margin notes; the desk takes, declines or forks each, with a reason, and every note is accounted for; heads select, never merge | `STAGES.md` |
| **校閲 (kōetsu)**: Japanese houses' fact and continuity checkers, every query with its evidence | The final read's continuity pass over the whole text; every reader's note quotes the Japanese. Fact-check is planned | `STAGES.md` |
| **The translator's note or afterword**, the one place the translator is visible | The house's reading, published with the edition and labelled as the house's | `STORY-STATE.md` §0 |
| **Retranslation and second editions** | Versioned releases (v1, v1.1) with changelogs | `ARCHITECTURE.md` §2 |

## The additions in more detail

**Background brief** (not built). Before the first read, a few searches on the author's life, the period, the work's reception and anything the text alludes to. It's a page of notes with sources. It informs the reading; it's never presented as the author's view, and it doesn't reproduce the commentary in the source edition.

**Finding the voice.** Translators often say the first pages are the hardest because that's where the voice is found, and they redo them until it settles. The reading offers two or three takes on the voice (drier or warmer, plainer or more formal), the drafter writes in the first, and the house's first page then sits in every later call as the voice reference. We also tried a voice trial, drafting the first page in each voice and picking one: it picked the voice the reading listed first and the English was no better, so it was dropped (`experiments/03-stiffness.md`).

**Alternatives in the draft.** A drafting call that can't choose between two renderings without knowing what comes later says so in a translator's note, with both readings and what would settle it. The desk sees those notes; the readers don't, so their first reaction is uncoached.

**The editor's letter** (not built). Margin notes catch local problems. They don't catch a draft that is accurate line by line and still wrong as a whole: a narrator who sounds too educated, a character whose warmth has drained out, an ending that's been made more hopeful than the Japanese. A real editor's first response to a manuscript is a letter about exactly this. So after the first full draft, Wonder would read the whole English with the reading and write a short letter, which the desk acts on. Until then, the final read is the whole-text look.

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
