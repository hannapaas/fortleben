# keikaku — story state: how the house remembers a text

Written 28 Oct 2026. This is the long-context design: what every translation call knows about the rest of the text, and how that knowledge is built, kept consistent and checked. It's part of the M1 contract, because every department reads it.

## The problem

Japanese literary prose drops subjects, leaves speakers unattributed and shifts tense freely. A model translating one passage at a time guesses who is speaking or acting, and the guess reads perfectly well in English while being wrong. Over a long text, names, address terms, honorific choices and repeated images drift.

## What the research says (and why we don't use big overlaps)

- **Paragraph-sized units beat sentences**, but critical errors and omissions remain (Karpinska & Iyyer 2023), and models skip more as the output gets longer. So Translation drafts **about a page at a time** (~1k source tokens, ~650 characters): several whole paragraphs, never splitting one, and breaking at scene breaks where it can. Bigger isn't automatically better: a longer draft hides more dropped sentences, and checking and redoing a page is precise and cheap. Continuity comes from the context in §3 rather than from a longer draft.
- **A small curated memory beats a big raw history.** DelTA (ICLR 2025) keeps proper-noun records, a bilingual summary and retrieved earlier pairs, and improves consistency. Loong (2026) finds that unfiltered context, including full history, sometimes scores *below* no context at all.
- **Models use long contexts worse than their windows suggest.** Information in the middle is used worst (Liu et al. 2024); when the link isn't a literal word match, most long-context models lose half their accuracy by ~32K tokens (NoLiMa 2025).

So we don't feed large raw overlaps (say, the previous two chapters) into every call. That is the "big history" the evidence warns against: it costs tokens, buries the current passage in the middle of the prompt, and still leaves the model to work out who's who by itself. Instead, a source-side **Analyst** reads the whole text first and writes down the decisions explicitly, and every call gets those decisions plus a short window of real text either side.

## 0. The first read: forming a reading

Most literary translators read the whole book before translating a word, often twice. The first time they're not taking notes on names; they're forming a reading: what the book is doing, how it sounds, where it turns, what the ending does to everything before it. Every later choice (how formal, how much to explain, when a repetition matters) comes from that reading. A model translating paragraph by paragraph never has one unless we give it one.

So before anything else, **Wonder reads the whole source once and writes the house's reading**: a page of plain prose, not a form to fill in.

**The reading starts from the crux: what a translation of *this* text stands or falls on.** Every book has its own. In one, it's a narrator who has had almost no education: an English version that gives her an educated vocabulary has betrayed the book, however well it reads. In another it's a single word that changes meaning by the last page, or an irony that only works if the English stays deadpan, or a dialect that marks who belongs. The reading names the one or two things that matter most here and says why, in the text's own terms.

Beyond that, it covers whatever this text needs. Often that's tone and voice, the shape of the story, ambiguity the author left open, and where a fluent English draft is likely to go wrong. But those are what readings usually turn out to contain, not headings to fill in. A reading that dutifully covers every usual topic and misses the crux has failed. The prompt teaches what a reading is for and shows a couple of very different examples; it doesn't hand over a template.

**A second, independent reader checks the crux.** A second Wonder call, with a different prompt, reads the text separately, without seeing the first reading, and answers one question: what does a translation of this stand or fall on? It's a cheap call, and a third compares the two answers. Where the two agree, the crux goes straight into the reading. Where they disagree, that's the first and most important fork for the editor, at the point where a decision is cheapest and touches everything. As everywhere, the house doesn't wait: until the editor rules, the first reading stands and the disagreement is shown. Other open questions the reading can't settle are listed in it, so every later call sees them.

Wonder writes the reading because it's the strongest reader we have, and one call over the whole text is cheap (it's counted in the whole-text reads in `RUNNING-A-TEXT.md`). Its 1M-token context holds even a full novel, so a novel gets a whole-book first read too, not a chapter-by-chapter one.

The reading is what turns the rest of the house from rule-followers into colleagues with judgement. Every department gets it in its cached prefix, so a drafting call that meets something no rule covers can ask "what fits the reading?" The readers, the desk and the final read check the crux first: a draft that is accurate line by line but gets the crux wrong is the most serious kind of error, because no single line looks wrong. It's also the editor's best point of leverage: a page to read, and a comment on it changes everything downstream. As everywhere, nothing waits for that comment. And it's published with the edition as **the house's reading**, labelled as the house's and never presented as the author's view or as a human introduction.

## 1. The story bible (built from the reading)

The Analyst (Spark) then builds the bible, with the whole source and the reading in its cached prefix. All our texts fit: the longest, 「思い出の記」, is ~31k characters. Cast, narration, motifs, style sheet and hard spots come from one call. For a novel the plan is for the Analyst to work part by part, updating the same bible, and to write a one-line summary of each part (`chapter_summaries`) for the other parts' calls to carry; that isn't built (§5). It produces:

| Part | Holds | Why it matters |
|---|---|---|
| **Cast** | Every person the text refers to, not only the principals: minor and unnamed figures get a handle ("the old man at the rice shop") and whatever the text shows (親爺, so male and elderly). Per entry: name in kanji and reading where there is one, romanisation, every form they're referred to or addressed by (先生, あなた, お前, kinship terms, nicknames), who uses which form, gender if the text shows it, role, relationships, first-person pronoun (私 / 僕 / 俺 / わたくし) and what it says about them, speech register (keigo level, dialect, 文語), first appearance | Keeps names, address and voice stable; tells the translator what 僕 vs 俺 is doing |
| ~~**Ledger**~~ (*dropped 2 Nov; see §6*) | Was: places, objects, period terms and recurring phrases, with an approved English per edition, written into the draft as `{t:id}` placeholders | What it did is the style sheet's job (keep 先生 as Sensei, and why) |
| ~~**Referent map**~~ (*dropped 2 Nov after the first run; see below and §6*) | Was: per paragraph, the speaker of each line and the implicit subject of each sentence, with a confidence | The first run showed it adding nothing on clear sentences and carrying one misreading, at high confidence, into every later call |
| **Narration** | Narrator (first or third person, who), tense habits and the English default, frame and time structure, a short timeline | Stops tense flip-flopping and confused flashbacks |
| **Motifs and callbacks** | The images and key words the author repeats on purpose, with segment IDs of each occurrence; not phrases Japanese simply repeats as ordinary usage | Literary repetition must stay repetition in English; a fluent model "varies" it away |
| **Style sheet** | Register, honorifics and names, what to keep in Japanese and why, ruby and italics, quotation conventions, notes on the author's voice, annotation density per view, standing rules with their scope | The house style for this text; the editor approves it |
| **Hard spots** | Poems, wordplay, allusions, dialect passages, classical quotations, with segment IDs | Warns the drafter and the final read, which get the whole bible; later, where heads may commission an intern |

**The referent map has to earn its place.** The whole source is already in every call, so the map is belt and braces: the cast is cheap and obviously worth having (published, checkable, correctable), but a sentence-by-sentence map is the heaviest part of the bible, and if the drafter with the whole book already gets referents right it's a cost without a benefit. So the first run on 「晩餐」 drafts the same pages with and without the referent entries, and the editor reads both. Same result: drop the map, keep the cast. Helps only where the Japanese is genuinely unclear: shrink it to those sentences. Helps broadly: keep it. The design doesn't depend on which; the context order and the drafter's prompt work either way. **The result (1 Nov):** the same pages with and without the map read the same; at p7 both followed a misreading that the cast also carried. The map was dropped and the cast kept, describing people rather than lines (§6).

The bible is one flat JSON document per work, with a schema, versioned and stored with the run; prompts get it rendered as plain Markdown (the readers and the desk get only the cast). Deliberately no knowledge graph, vector store or embeddings: a short story's bible fits in a few thousand tokens, and every extra layer is another place for errors to hide. We'd revisit that only for a house-wide memory across many works. It's published with each release: readers can see the cast and style sheet the house worked from.

## 1a. The author file

Translators who do several books by one author build up a knowledge of that writer: favoured sentence shapes, the words she leans on, how she handles dialogue, where she's deliberately rough, how her recurring terms were rendered last time and why. Each new book is still read on its own terms; the knowledge is what lets the translator notice when the author has changed register.

The house is meant to keep the same thing, as **an author file**: one per author, built only from completed runs, never written in advance. Not built yet: the table exists and nothing writes or reads it. Each entry would say where it came from (which work, which stage: a style-sheet choice, a line from the final read, an editor's ruling scoped `author`) and whether the latest reading agreed with it.

- **It informs; it never binds.** The first read gets it as information to weigh. The reading of *this* text, starting from its crux, decides what applies; a habit list can't override that, and a reading that finds the author has changed says so and the file records the disagreement.
- **Rules can be scoped `author`**, alongside line / character / term / work / house. Like every rule they're visible and revocable, and a rule from one work never rewrites a locked line in another.
- **It's published**, on the author's page, with its provenance, the same way the bible is. It's also honest about size: with two works by one author it's a few entries, and the page says so rather than dressing it up.

For the hackathon the only author with two works in the plan is Shiraki Shizu: 「晩餐」, the development text, and 「三十三の死」 if it runs as one of the other texts. Since the showcase moved to Nagatsuka's 「炭燒のむすめ」 (1 Nov, provisional), the author file is a small side piece rather than part of the showcase, and a real but small piece of evidence that the house isn't translating each text cold. It should be described that way.


## 2. Changing its mind

Translators' understanding of a book grows while they translate it; close work turns up things a read-through doesn't. Halfway through, a word turns out to echo something on page two, and the rendering chosen for page two now looks wrong. That's why translators draft the whole book before revising anything: late discoveries are cheap until the revision starts. The house works the same way. The reading and the bible are the best view at the start, not a verdict.

- **The view comes from the whole text, not the opening.** The first read sees the whole book, so the reading and its voice takes aren't built on the first few pages alone.
- **The passage wins.** Every prompt is told the bible is the house's best understanding before drafting and can be wrong; a reader or the desk that sees otherwise in the text goes by the text. Formal amendments to the bible (`analyst-amend`, a version bump) are planned, not built.
- **Changes reach backwards.** When the desk learns in one part something that changes an earlier one (who a character is, what a word means here), it says so; once every part has been through the desk, each earlier part goes back to it once with those findings (`STAGES.md`, the emergency lever). Rule propagation over every earlier segment (ARCHITECTURE §3) is planned, not built. The up-front estimate pays for the lever's pass back.
- **The editor's letter is the formal second look** (planned, not built). After the full draft, Wonder reads the whole English against the reading. Whatever the house has learned by then, including "the reading was wrong about this", comes out there, and the reading is updated before revision. The published reading is the final one, with a line on what changed.
- **Old views are kept.** Every version of the bible and the reading stays in the event log, so readers can see how the house's view changed and why.

A bible version bump changes the cache key, so amendments would be batched, not applied mid-stage.

## 3. What each translation call sees

In this order, stable first (cached) and the passage last (where models attend best):

1. House rules and the department prompt.
2. The house's reading (§0), the voice (the first voice take the reading offers) and the whole bible: style sheet, cast, narration, motifs, hard spots. A few thousand tokens for a short story.
3. **The source, scoped by length.** Up to 50,000 characters the whole source goes in: cheap in the cached prefix, and the model can look anywhere in the book. Above that, a call about a page gets **its own part in full and every other part as one line** (the Analyst's summary when there is one, else the heading or first words). The parts are the planner's (stage 1), checked by code; if its answer fails the check, code cuts them at headings where the text has them, else at scene breaks merged to at least 4,000 characters, never over 25,000. This is where the length of a work changes what a call sees (`house/context.py`), and it is what keeps the cost of a call flat: a novel costs its pages, not its pages times its length. The first read, the crux check and the bible still get the whole book; the final read gets the whole text up to 50,000 characters and a part at a time above that.
4. The voice reference: the house's first page, from page 2 on.
5. **A window of real text either side:** the previous two paragraphs in Japanese and English, and **the next paragraph in Japanese, marked read-only** (Japanese often resolves a subject or speaker after the fact).
6. The passage itself, as whole paragraphs with their IDs (numbered sentences invite a sentence-by-sentence draft). Who speaks and who acts the drafter works out from the text, the cast and the window either side, the way a translator does; where the Japanese genuinely leaves it open, the drafting prompt teaches the model not to commit a pronoun the text doesn't support.

That's all. No rolling summary and no retrieval of earlier passages: with the source (or the part) in the prefix and the bible carrying the decisions, both would be a second copy of what's already there. The part summaries (not built yet) are the one concession for long works, and they are a line each, not a history.

## 4. Checking that it held

- **The readers:** the faithful reader catches a wrong subject or speaker, a lost image, a varied repetition, the crux slipping; the readable reader catches English no good writer would sign. Both work a part at a time with the reading and the cast.
- **Omission guard (code, at the copy desk):** length ratio per paragraph against the text's own median; outliers become queries.
- **Final read (Spark by default):** once per run, the finished English read as a whole and then against the source: seams left by revision, voice drift, whether the crux holds, and continuity (contradictions, a speaker confused across scenes, a fact that changes, a word an edit doubled). It fixes the clear cases as exact edits and sends the rest to the editor.

A voice checker (first-person voice and address forms against the cast) and a callback checker (every motif occurrence rendered consistently) were planned and aren't built; for now the readers and the final read do that work.

## 5. Short texts and novels: one pipeline

There is no novel mode. The stages, the prompts and the limits are the same for a 3,000-character story and a 300,000-character novel; only two things read the length of the work: what a per-page call sees of the source (§3, point 3) and whether the final read takes the text whole or a part at a time. The first run on 「晩餐」 (1 Nov) showed why that line matters: with the whole text in every call, a call's input grows with the book, so a novel would have cost hundreds of dollars for *worse* attention (the research above). With the part in the call instead, a 200k-character novel costs roughly its pages times the per-page cost measured on short texts, a few tens of dollars. The Analyst's part summaries are not built yet; until they are, the other parts appear as their headings or first words, which is honest and cheap. Measured before it's claimed.

## 6. What the first run taught, and what changed (2 Nov)

The recorded run on 「晩餐」 (1 Nov) raised 18 queries and the translator accepted 17; fourteen re-checks by Wonder then confirmed what code could see, that the fix was in. Every query pulled the English towards the Japanese and nothing pulled it towards good English, so the result was faithful and stiff. And one misreading at the first read (in p7 the father hands the bowl to the mother, not the baby) went into the cast and the referent map, the draft followed it, and the critic enforced it. The design changed on 2 Nov, in four ways:

- **Two readers and a desk, instead of a critic and a translator answering.** A faithful reader and a readable reader read each part independently and leave margin notes or none; the desk is the only one who changes the text, and declines with a reason. There are no rounds and no re-checks (`STAGES.md`, "How the readers and the desk work").
- **No referent map.** The drafter works out who speaks and acts from the text, the cast and the paragraphs either side; a wrong subject is the faithful reader's to catch. The cast describes people, not individual sentences, because a claim about one line made at bible time gets carried into every call as if it were settled.
- **The bible is evidence, not law.** Every prompt is told it's the house's best understanding before drafting and can be wrong, and that the passage in front of it wins. Mechanical faults (a doubled "the dark the dark" left by an edit) are the final read's to catch, not the readers'.

- **No ledger, no placeholders.** The ledger had become a list of whole phrases ("freshly cooked rice, steaming", "storm; sound of rain and wind") pasted into the English through `{t:id}` placeholders: it caused some of the stiffness itself, produced doubled words and a policy note in the dialogue, and broke the desk, whose edits quoted text it couldn't see. The translator now writes plain English; what to keep in Japanese, such as Sensei, is the style sheet's, with its reason. The three editions share one English and differ in their notes.

Whether this produces better English is what the experiments on 「晩餐」 measured: who drafts, who reads and edits, and how the first draft is written (`experiments/`).
