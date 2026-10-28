# keikaku — story state: how the house remembers a text

Written 28 Oct 2026. This is the long-context design: what every translation call knows about the rest of the text, and how that knowledge is built, kept consistent and checked. It's part of the M1 contract, because every department reads it.

## The problem

Japanese literary prose drops subjects, leaves speakers unattributed and shifts tense freely. A model translating one passage at a time guesses who is speaking or acting, and the guess reads perfectly well in English while being wrong. Over a long text, names, address terms, honorific choices and repeated images drift.

## What the research says (and why we don't use big overlaps)

- **Paragraph-sized units beat sentences**, but critical errors and omissions remain (Karpinska & Iyyer 2023). So we translate whole paragraphs and still check for omissions.
- **A small curated memory beats a big raw history.** DelTA (ICLR 2025) keeps proper-noun records, a bilingual summary and retrieved earlier pairs, and improves consistency. Loong (2026) finds that unfiltered context, including full history, sometimes scores *below* no context at all.
- **Models use long contexts worse than their windows suggest.** Information in the middle is used worst (Liu et al. 2024); when the link isn't a literal word match, most long-context models lose half their accuracy by ~32K tokens (NoLiMa 2025).

So we don't feed large raw overlaps (say, the previous two chapters) into every call. That is the "big history" the evidence warns against: it costs tokens, buries the current passage in the middle of the prompt, and still leaves the model to work out who's who by itself. Instead, a source-side **Analyst** reads the whole text first and writes down the decisions explicitly, and every call gets those decisions plus a short window of real text either side.

## 1. The story bible (built before any translation)

The Analyst reads the whole source in one call. All our texts fit: the longest, 「幻影の盾」, is ~22k characters, about 33k tokens. For a novel it works chapter by chapter, updating the same bible. It produces:

| Part | Holds | Why it matters |
|---|---|---|
| **Cast** | Per character: name in kanji and reading, romanisation, every form they're referred to or addressed by (先生, あなた, お前, kinship terms, nicknames), who uses which form, gender if the text shows it, role, relationships, first-person pronoun (私 / 僕 / 俺 / わたくし) and what it says about them, speech register (keigo level, dialect, 文語), first appearance | Keeps names, address and voice stable; tells the translator what 僕 vs 俺 is doing |
| **Ledger** | Places, objects, period terms, recurring phrases: the approved English per edition (Casual / Curious / Student), reading, rationale, status `proposed / approved / locked` | One rendering everywhere; editions differ by design, not by drift |
| **Referent map** | Per paragraph: the speaker of each line of dialogue and the implicit subject of each sentence that needs one, with confidence `high / medium / low`, and `deliberately ambiguous` where the original keeps it open | The single biggest JA→EN error source. Low-confidence entries steer Source check; deliberate ambiguity is preserved, not resolved |
| **Narration** | Narrator (first or third person, who), tense habits and the English default, frame and time structure, a short timeline | Stops tense flip-flopping and confused flashbacks |
| **Motifs and callbacks** | Repeated images, words and phrases the author uses deliberately, with segment IDs of each occurrence | Literary repetition must stay repetition in English; a fluent model "varies" it away |
| **Style sheet** | Register, honorific and name-order policy, ruby and italics policy, quotation conventions, notes on the author's voice, annotation density per edition, standing rules with their scope | The house style for this text; the editor approves it |
| **Hard spots** | Poems, wordplay, allusions, dialect passages, classical quotations, with segment IDs | Where heads may commission an intern; where Source check looks hardest |

The bible is JSON with a schema, versioned, and stored with the run. A human-readable view of it is published with each edition: readers can see the cast and ledger the house worked from.

## 2. Keeping it up to date

- **Nobody edits the bible silently.** Translation, Source check or Editorial can propose an amendment (a character the Analyst missed, a corrected reading, a better rendering) as a query to the Analyst. Accepted amendments bump the version.
- A version bump changes the cache key, so amendments are batched: at the end of each chunk, not mid-call.
- When a ledger rendering changes, rule propagation (ARCHITECTURE §3) finds every earlier segment that used the old one and queues revisions. Locked items need the editor.

## 3. What each translation call sees

In this order, stable first (cached) and the passage last (where models attend best):

1. House rules and the department prompt.
2. The style sheet, cast and ledger. For short texts, the whole bible (a few thousand tokens). For long ones, only the entries present in this passage, the previous two paragraphs and the next paragraph.
3. **The whole source text**, for texts up to ~30k characters (our default for now: cached at $0.15/M, so cheap, and it lets the model look anywhere). E3 tests whether this helps or hurts; if it hurts, we drop it.
4. The rolling summary (≤300 words: what has happened, who knows what).
5. 2–3 earlier approved passage pairs that share characters or address terms with this one.
6. **A window of real text either side:** the previous two paragraphs in Japanese and English, and **the next paragraph in Japanese, marked read-only** (Japanese often resolves a subject or speaker after the fact).
7. The passage itself, with its referent-map entries inline (`p12-s3: subject = narrator; speaker of 「…」 = Okinu (medium)`).

Everything except (3) stays under ~5k tokens.

## 4. Checking that it held

- **Ledger checker (code):** every cast name and ledger term in the English matches the approved rendering for that edition.
- **Voice checker (code + Glimmer):** first-person voice and address forms match the cast entry.
- **Callback checker (code):** every motif occurrence is rendered consistently, or carries a translator's note saying why not.
- **Omission guard (code):** length ratio per paragraph against the text's own baseline; outliers go to Source check.
- **Continuity read (Wonder):** once per release, one call over the whole source and translation, looking for contradictions, a speaker confused across scenes, a fact that changes.

## 5. Novels, later

Same machinery, chapter by chapter: the Analyst updates the bible per chapter, the rolling summary becomes chapter summaries, and the whole-source block becomes the current chapter plus neighbouring chapter summaries. E3 measures whether this keeps book-length consistency on a short-story budget before we claim it.
