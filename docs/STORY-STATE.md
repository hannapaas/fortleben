# keikaku — story state: how the house remembers a text

This is the long-context design: what every call knows about the rest of the text, and how that knowledge is built, kept consistent and checked. `STAGES.md` has the stages that build and use it.

## The problem

Japanese literary prose drops subjects, leaves speakers unattributed and shifts tense freely. A model translating one passage at a time guesses who is speaking or acting, and the guess reads perfectly well in English while being wrong. Over a long text, names, address terms, honorific choices and repeated images drift.

## What the research says (and why we don't use big overlaps)

- **Paragraph-sized units beat sentences**, but critical errors and omissions remain (Karpinska & Iyyer 2023), and models skip more as the output gets longer. So the translator drafts **about a page at a time** (~650 characters, ~1k source tokens): several whole paragraphs, never splitting one, breaking at scene breaks where it can. Bigger isn't automatically better: a longer draft hides more dropped sentences, and checking and redoing a page is precise and cheap. Continuity comes from the context in §3, not from a longer draft.
- **A small curated memory beats a big raw history.** DelTA (ICLR 2025) keeps proper-noun records, a bilingual summary and retrieved earlier pairs, and improves consistency. Loong (2026) finds that unfiltered context, including full history, sometimes scores *below* no context at all.
- **Models use long contexts worse than their windows suggest.** Information in the middle is used worst (Liu et al. 2024); when the link isn't a literal word match, most long-context models lose half their accuracy by ~32K tokens (NoLiMa 2025).

So we don't feed large raw overlaps (say, the previous two chapters) into every call. That is the "big history" the evidence warns against: it costs tokens, buries the current passage in the middle of the prompt, and still leaves the model to work out who's who by itself. Instead the house reads the whole text first and writes down what it understands, and every call gets that plus a short window of real text either side. Full references are in `REFERENCES.md`.

## 0. The first read: forming a reading

Most literary translators read the whole book before translating a word, often twice. The first time they're not taking notes on names; they're forming a reading: what the book is doing, how it sounds, where it turns, what the ending does to everything before it. Every later choice (how formal, how much to explain, when a repetition matters) comes from that reading. A model translating page by page never has one unless we give it one.

So before anything else, **Wonder reads the whole source once and writes the house's reading**: plain prose, not a form to fill in. It reads the whole book whatever its length, so a novel gets a whole-book reading, not a chapter-by-chapter one.

**The reading starts from the crux: what a translation of *this* text stands or falls on.** Every book has its own. In one, it's a narrator who has had almost no education: an English version that gives her an educated vocabulary has betrayed the book, however well it reads. In another it's a single word that changes meaning by the last page, or an irony that only works if the English stays deadpan, or a dialect that marks who belongs. The reading names the one to three things that matter most here and says why, in the text's own terms, and what each means for the English.

Beyond that, it covers whatever this text needs. Often that's tone and voice, the shape of the story, ambiguity the author left open, and where a fluent English draft is likely to go wrong. But those are what readings usually turn out to contain, not headings to fill in. A reading that dutifully covers every usual topic and misses the crux has failed. The prompt teaches what a reading is for and shows a couple of very different examples; it doesn't hand over a template. The reading also lists its open questions, and offers two or three **voice takes** for the English, the one it recommends first.

**A second, independent reader checks the crux.** A second Wonder call, with a different prompt, reads the text without seeing the first reading and answers one question: what does a translation of this stand or fall on? A third call compares the two. Where they name the same thing, the reading stands as it is. Where they differ, that's the first fork for the editor, at the point where a decision is cheapest and touches everything, and the second crux is added to the reading, marked as a second reader's, so every later call holds both. Nothing waits for the editor: until they rule, the first reading stands.

The reading is what turns the rest of the house from rule-followers into colleagues with judgement. Every call after it gets it, and the house brief every call carries says that when a decision isn't covered by a rule, the question is "what fits the reading?" The faithful reader and the final read check the crux first: a draft that is accurate line by line but gets the crux wrong is the most serious kind of error, because no single line looks wrong. It's also the editor's best point of leverage: a page to read at the checkpoint, and a note on it changes everything downstream. It's published with the edition as **the house's reading**, labelled as the house's and never presented as the author's view or as a human introduction.

## 1. The story bible (built from the reading)

The Analyst (Spark) then builds the bible in one call, with the whole source and the reading in front of it, and, for a book in more than one part, the parts the planner chose. It holds:

| Part | Holds | Why it matters |
|---|---|---|
| **Cast** | Every person the text refers to, not only the principals: minor and unnamed figures get a handle ("the old man at the rice shop") and whatever the text shows (親爺, so male and elderly). Per entry: name in kanji and reading where there is one, romanisation, every form they're referred to or addressed by (先生, あなた, お前, kinship terms, nicknames), who uses which form, gender if the text shows it and the evidence, role, relationships, first-person pronoun (私 / 僕 / 俺 / わたくし) and what it says about them, speech register (keigo level, dialect, 文語), first appearance | Keeps names, address and voice stable; tells the translator what 僕 vs 俺 is doing |
| **Narration** | Narrator (first or third person, who), tense habits and the English default, frame and time structure, a short timeline | Stops tense flip-flopping and confused flashbacks |
| **Motifs and callbacks** | The images and key words the author repeats on purpose, with the paragraph IDs of each occurrence and how the English carries them; not phrases Japanese simply repeats as ordinary usage | Literary repetition must stay repetition in English; a fluent model "varies" it away |
| **Style sheet** | Register, honorifics and names, what to keep in Japanese and why (Sensei, say), ruby and italics, quotation conventions, notes on the author's voice, annotation density, standing rules | The house style for this text |
| **Hard spots** | Poems, wordplay, allusions, dialect passages, classical quotations, with paragraph IDs | Warns every call that meets them |
| **Part summaries** | For a book in more than one part, a few plain sentences per part: who appears, what happens, what is established or changes | What a call about one part knows of the others (§3) |

**The cast describes people, not lines.** Who acts or speaks in a particular sentence is worked out by whoever reads that sentence, with the text in front of them, the way a translator does. A claim about one line made at bible time gets carried into every later call as if it were settled: an early run kept a sentence-by-sentence referent map, and on 「晩餐」 a misreading in it (who hands the bowl to whom in p7) went into every call, the draft followed it and the reviewer enforced it, while the same pages drafted without the map read the same everywhere else. So there is no referent map, and a wrong subject is the faithful reader's to catch.

**No term ledger, no placeholders.** The style sheet says what stays in Japanese and why; the translator writes plain English. A list of approved phrases pasted into the draft made it stiff, doubled words and broke exact edits.

The bible is one flat JSON document per work, with a schema, versioned; every call gets it rendered as plain Markdown under a heading that calls it "the house's best understanding before drafting, which can be wrong". Deliberately no knowledge graph, vector store or embeddings: a short story's bible fits in a few thousand tokens, and every extra layer is another place for errors to hide. It's published with each release, so readers can see the cast and style sheet the house worked from.

## 2. Changing its mind

Translators' understanding of a book grows while they translate it; close work turns up things a read-through doesn't. Halfway through, a word turns out to echo something on page two, and the rendering chosen for page two now looks wrong. That's why translators draft the whole book before revising anything: late discoveries are cheap until the revision starts. The house works the same way. The reading and the bible are the best view at the start, not a verdict.

- **The view comes from the whole text, not the opening.** The first read and the bible see the whole book, so the reading and its voice takes aren't built on the first few pages.
- **The editor corrects it before the draft.** At the checkpoint (`STAGES.md`) the editor reads the reading, the bible and page 1 in each voice. A note goes back to the model that wrote the reading, which carries it into the reading and the bible and saves new versions where they change; or the editor rewrites either by hand, and every later call reads their version. Page 1 is drafted again, so the effect shows as English.
- **The passage wins.** The house brief and the bible's own heading tell every call that the bible can be wrong, and that when the passage says otherwise the passage wins and the call should say so. A reader or the desk that sees otherwise in the text goes by the text.
- **Changes reach backwards.** When the desk learns in one part something that changes an earlier one (who a character is, what a word means here), it says so; once every part has been through the desk, each earlier part goes back to it once with those findings (`STAGES.md`, the emergency lever). The up-front estimate pays for that pass back.
- **Old views are kept.** Every version of the reading and the bible stays in the record with the event that wrote it, and a hand edit keeps its before and after.

The reading and the bible change only before the draft. A new bible version starts a new cached prefix, so changing it mid-stage would cost every later call its cache; after the checkpoint, what the house learns goes into the English through the desk, not back into the bible.

## 3. What each translation call sees

In this order, stable first (cached) and the passage last (where models attend best):

1. The house brief and the department prompt.
2. The house's reading (§0), the voice the run drafts in, and the whole bible (§1). A few thousand tokens for a short story.
3. **The source, scoped by length.** Up to 15,000 characters the whole source goes in: cheap in the cached prefix, and the model can look anywhere in the text. Above that, a call about a page gets **its own part in full and one line on every other part**: the bible's summary of it, or its heading or first words if the bible has none. The parts are the planner's, checked by code, with a fallback split when its answer fails the check (`STAGES.md`). This is the one place the length of a work changes what a drafting call sees (`house/context.py`), and it is what keeps the cost of a call flat: a novel costs its pages, not its pages times its length.
4. The voice reference: the house's first page (or the editor's own page 1, if they rewrote it), from page 2 on.
5. **A window of real text either side:** the previous two paragraphs in Japanese and English, and **the next paragraph in Japanese, marked read-only** (Japanese often resolves a subject or speaker after the fact).
6. The page itself, as whole paragraphs with their IDs (numbered sentences invite a sentence-by-sentence draft). Who speaks and who acts the drafter works out from the text, the cast and the window either side, as a translator must.

That's all. No rolling summary and no retrieval of earlier passages: with the source (or the part) in the prefix and the bible carrying what the house understands, both would be a second copy of what's already there.

The other calls see:

| Call | Sees |
|---|---|
| First read, crux check | the work's card and the whole source |
| Bible | the whole source, the reading, and the parts |
| Readers | the reading, the bible, the part in both languages (the faithful reader meets the Japanese first, the readable reader the English) |
| Desk | as the readers, plus the translator's notes, what the desk learned in earlier parts, and both readers' notes |
| Final read | the reading, the bible, and the whole text in both languages up to 15,000 characters; above that a part at a time, with a line on each other part, so a contradiction between parts can still be seen |
| Copy editor | the bible, the two lists code makes (spelling variants, names against their ruby), and the whole English up to 200,000 characters |
| Notes | the reading, the bible, the source scoped as for a drafting call, the part in both languages with the translator's notes, and the readers' notes the desk declined and the disagreements it recorded |

## 4. Checking that it held

- **The readers:** the faithful reader catches a wrong subject or speaker, a lost image, a varied repetition, the crux slipping; the readable reader catches English no good writer would sign. Both work a part at a time with the reading and the whole bible.
- **The final read (Wonder by default):** once per run, the finished English read as a whole and then against the source: sense first, then seams left by revision, voice drift, whether the crux holds, and continuity (contradictions, a speaker confused across scenes, a fact that changes, a word an edit doubled). It fixes the clear cases with the edit tool and sends the rest to the editor.
- **The copy desk:** code lists the words the English spells more than one way and the names whose spelling doesn't match the reading the ruby gives; the copy editor makes them consistent. Code's omission guard then compares each paragraph's length ratio with the text's own median, and outliers become queries.

## 5. Short texts and novels: one pipeline

There is no novel mode. The stages, the prompts and the limits are the same for a 3,000-character story and a 300,000-character novel; only two things read the length of the work: what a per-page call sees of the source (§3, point 3) and whether the final read takes the text whole or a part at a time. That line matters: with the whole text in every call, a call's input grows with the book, so a novel would cost hundreds of dollars for *worse* attention (the research above). With the part in the call instead, the up-front estimate for a 200,000-character novel comes to about $30, every call priced live with no cache, from token counts measured on texts up to about 20,000 characters (`house/budget.py`).
