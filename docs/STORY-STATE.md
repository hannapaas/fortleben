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

**A second, independent reader checks the crux.** Spark reads the text separately, without seeing Wonder's reading, and answers one question: what does a translation of this stand or fall on? It's a cheap call. Where the two agree, the crux goes straight into the reading. Where they disagree, that's the first and most important fork for the editor, at the point where a decision is cheapest and touches everything. As everywhere, the house doesn't wait: until the editor rules, Wonder's reading stands and the disagreement is shown. Any other open questions of interpretation the reading can't settle become forks too.

Wonder writes the reading because it's the strongest reader we have, and one call over the whole text is cheap (it's counted in the whole-text reads in `RUNNING-A-TEXT.md`). Its 1M-token context holds even a full novel, so a novel gets a whole-book first read too, not a chapter-by-chapter one.

The reading is what turns the rest of the house from rule-followers into colleagues with judgement. Every department gets it in its cached prefix, so a drafting call that meets something no rule covers can ask "what fits the reading?" Critics check the crux first: a draft that is accurate line by line but gets the crux wrong is the most serious kind of error, because no single line looks wrong. It's also the editor's best point of leverage: a page to read, and a comment on it changes everything downstream. As everywhere, nothing waits for that comment. And it's published with the edition as **the house's reading**, labelled as the house's and never presented as the author's view or as a human introduction.

## 1. The story bible (built from the reading)

The Analyst (Spark) then builds the bible, with the whole source and the reading in its cached prefix. All our texts fit: the longest, 「幻影の盾」, is ~22k characters, about 33k tokens. Cast, ledger, narration, motifs, style sheet and hard spots come from one call. The referent map is built paragraph by paragraph in a few further calls, because it's long and needs close attention to each line; each of those calls still sees the whole text. For a novel the Analyst works chapter by chapter, updating the same bible. It produces:

| Part | Holds | Why it matters |
|---|---|---|
| **Cast** | Per character: name in kanji and reading, romanisation, every form they're referred to or addressed by (先生, あなた, お前, kinship terms, nicknames), who uses which form, gender if the text shows it, role, relationships, first-person pronoun (私 / 僕 / 俺 / わたくし) and what it says about them, speech register (keigo level, dialect, 文語), first appearance | Keeps names, address and voice stable; tells the translator what 僕 vs 俺 is doing |
| **Ledger** | Places, objects, period terms, recurring phrases: the approved English per edition (Casual / Curious / Student), reading, rationale, status `proposed / approved / locked` | One rendering everywhere; editions differ by design, not by drift |
| **Referent map** | Per paragraph: the speaker of each line of dialogue and the implicit subject of each sentence that needs one, with confidence `high / medium / low`, and `deliberately ambiguous` where the original keeps it open | The single biggest JA→EN error source. Low-confidence entries steer Source check; deliberate ambiguity is preserved, not resolved |
| **Narration** | Narrator (first or third person, who), tense habits and the English default, frame and time structure, a short timeline | Stops tense flip-flopping and confused flashbacks |
| **Motifs and callbacks** | Repeated images, words and phrases the author uses deliberately, with segment IDs of each occurrence | Literary repetition must stay repetition in English; a fluent model "varies" it away |
| **Style sheet** | Register, honorific and name-order policy, ruby and italics policy, quotation conventions, notes on the author's voice, annotation density per edition, standing rules with their scope | The house style for this text; the editor approves it |
| **Hard spots** | Poems, wordplay, allusions, dialect passages, classical quotations, with segment IDs | Where heads may commission an intern; where Source check looks hardest |

The bible is one flat JSON file per work, with a schema, versioned and stored with the run. Code reads it for the checks in §4; prompts get it rendered as plain Markdown. Deliberately no knowledge graph, vector store or embeddings: a short story's cast and ledger fit in a few thousand tokens, and every extra layer is another place for errors to hide. We'd revisit that only for a house-wide memory across many works. A human-readable view of it is published with each edition: readers can see the cast and ledger the house worked from.

## 1a. The author file

Translators who do several books by one author build up a knowledge of that writer: favoured sentence shapes, the words she leans on, how she handles dialogue, where she's deliberately rough, how her recurring terms were rendered last time and why. Each new book is still read on its own terms; the knowledge is what lets the translator notice when the author has changed register.

The house keeps the same thing, as **an author file**: one per author, built only from completed runs, never written in advance. Each entry says where it came from (which work, which stage: a ledger rendering, a line from the editor's letter or final read, an editor's ruling scoped `author`) and whether the latest reading agreed with it.

- **It informs; it never binds.** The first read gets it as information to weigh. The reading of *this* text, starting from its crux, decides what applies; a habit list can't override that, and a reading that finds the author has changed says so and the file records the disagreement.
- **Rules can be scoped `author`**, alongside line / character / term / work / house. Like every rule they're visible and revocable, and a rule from one work never rewrites a locked line in another.
- **It's published**, on the author's page, with its provenance, the same way the bible is. It's also honest about size: with two works by one author it's a few entries, and the page says so rather than dressing it up.

For the hackathon the only author with two works is Shiraki Shizu (「晩餐」 then 「三十三の死」), which makes it a real but small piece of evidence that the house isn't translating each text cold. It should be described that way.


## 2. Changing its mind

Translators' understanding of a book grows while they translate it; close work turns up things a read-through doesn't. Halfway through, a word turns out to echo something on page two, and the rendering chosen for page two now looks wrong. That's why translators draft the whole book before revising anything: late discoveries are cheap until the revision starts. The house works the same way. The reading and the bible are the best view at the start, not a verdict.

- **The view comes from the whole text, not the opening.** The first read sees the whole book, so the reading and the voice trial aren't built on the first few pages alone. The voice trial is judged against the whole reading.
- **Anyone can propose a change**, and nobody makes one silently. Translation, Source check or Editorial can propose an amendment (a missed echo, a character the Analyst missed, a corrected reading, a better rendering) as a query to the Analyst. Accepted amendments bump the version. The reading can be amended the same way, through Wonder.
- **Changes reach backwards.** When a rendering changes, or a new motif is found, rule propagation (ARCHITECTURE §3) finds every earlier segment that used the old rendering or holds the motif and queues revisions, each going back through Source check. Locked items need the editor. The reserve in each text's budget is there partly to pay for this.
- **The editor's letter is the formal second look.** After the full draft, Wonder reads the whole English against the reading. Whatever the house has learned by then, including "the reading was wrong about this", comes out there, and the reading is updated before revision. The published reading is the final one, with a line on what changed.
- **Old views are kept.** Every version of the bible and the reading stays in the event log, so readers can see how the house's view changed and why.

A version bump changes the cache key, so amendments are batched at the end of each chunk, not applied mid-call.

## 3. What each translation call sees

In this order, stable first (cached) and the passage last (where models attend best):

1. House rules and the department prompt.
2. The house's reading (§0) and the whole bible: style sheet, cast, ledger, motifs, standing rules. A few thousand tokens for a short story.
3. **The whole source text.** Every text we run is under ~30k characters, which is cheap in the cached prefix and lets the model look anywhere in the book. E-long (b) checks that it helps.
4. The voice reference: the chosen first page.
5. **A window of real text either side:** the previous two paragraphs in Japanese and English, and **the next paragraph in Japanese, marked read-only** (Japanese often resolves a subject or speaker after the fact).
6. The passage itself, with its referent-map entries inline (`p12-s3: subject = narrator; speaker of 「…」 = Okinu (medium)`).

That's all. No rolling summary and no retrieval of earlier passages: with the whole source in the prefix and the bible carrying the decisions, both would be a second copy of what's already there. They come back only for novels (§5), where the whole source can't sit in the prefix.

## 4. Checking that it held

- **Ledger checker (code):** every cast name and ledger term in the English matches the approved rendering for that edition.
- **Voice checker (code + Glimmer):** first-person voice and address forms match the cast entry.
- **Callback checker (code):** every motif occurrence is rendered consistently, or carries a translator's note saying why not.
- **Omission guard (code):** length ratio per paragraph against the text's own baseline; outliers go to Source check.
- **Final read (Wonder):** once per release, the finished English read as a whole and then against the source: seams left by revision, voice drift, whether the crux holds, and continuity (contradictions, a speaker confused across scenes, a fact that changes).

## 5. Novels, later

Same machinery, chapter by chapter: the Analyst updates the bible per chapter, and the whole-source block becomes the current chapter plus short summaries of the neighbouring ones, which is where a rolling summary and retrieved earlier passages earn a place. Measured before it's claimed; not built for the hackathon.
