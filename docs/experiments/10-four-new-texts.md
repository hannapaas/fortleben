# 10. Four new texts, and why misreadings survive

**Question.** On four texts the house hadn't seen, what goes wrong, and which stage should have caught it? The texts: 「雪景色」 (Makino Shin'ichi, 1927, 11,346 characters), 「書記官」 (Kawakami Bizan, 1895, 18,184), 「死剣と生縄」 (Emi Suiin, 1925, 15,104) and 「猫八」 (Iwano Hōmei, 1918, 19,513). A modernist comedy, Meiji literary prose, a period sword story and a comic performer's patter: four different registers.

**Set-up.** The house on its defaults: plain drafting on Spark, Spark readers, a Wonder desk, a Spark final read. Each text was then audited against the Japanese, paragraph by paragraph. This audit was not blind and had no one-shot beside it: it asked what was wrong, not which version was best.

## How the runs went

| Text | Cost | Parts | Paragraphs | Forks | Final-read fixes |
|---|---|---|---|---|---|
| 雪景色 | $1.44 | 1 | 212 | 0 | 4 |
| 書記官 | $1.82 | 1 | 132 | 1 | 0 |
| 死剣と生縄 | $1.77 | 1 | 224 | 2 | 4 |
| 猫八 | $2.09 | 1 | 188 | 1 | 3 |

- **No paragraph went missing,** no Japanese was left in the English, and no markup leaked. The planner kept each text as one part.
- **The final read called all four "Ready".**

## What the audit found

On every text:
- **Every plot came through.**
- **Each had five to ten real misreadings** that a reader would believe:
  - **A dropped subject given to the wrong person.** In 雪景色 the wife's remark that *he* never borrows money became her own habit. In 書記官 a daughter's father was called her "uncle" three times, because the speaker was his nephew.
  - **Reported speech read as the speaker's own.** 旅へ行きたいてえから, "*she* says she wants a trip", became "since we want to go".
  - **Set phrases read word by word, or backwards.** 掛値なし ("no exaggeration") became "without fee". 油切ってる ("greasy") became "lost its oil". 肩が抜けた ("a weight off") became "the strength had gone". 山の神 (slang for a wife) became "mountain goddess".
  - **Common nouns taken as places.** 那須野 is a koto piece, and 高市 is a fair.
- **Names misread although the ruby was there.** 生縄《いきなわ》 became "Ikina" and 阿波《あんば》 "Abawa". The first reading wrote "Ikina", the bible put it in the cast, and every page followed the bible.
- **Stiff dialogue, as on every text so far.** Brawlers speak like clerks, and a performer's patter is flattened.
- **Mechanical inconsistency:**
  - quote styles that change between sections;
  - "--" and "——" beside "—";
  - Ryūjirō and Ryujiro;
  - color and colour;
  - one nickname in five forms.

## Which stage should have caught them

We traced 16 of the audited misreadings through the run record:

| What happened to the misreading | Count |
|---|---|
| Never raised by either reader, the desk or the final read | 12 |
| Raised, but for a different fault in the same paragraph; the desk fixed that and kept the misreading | 4 |

There were two reasons:
- **No stage was aimed at plain sense.** The faithful reader looked for style losses: explanation added, repetition varied, tone shifted. It was told that five notes beat twenty, and it raised 6–15 notes per text. The final read was aimed at seams and continuity, and was told that a clean final read is the expected result. The desk acts only on notes.
- **The model.** A prompt aimed only at misreadings, run on Spark in 3,000-character windows, still caught few. Spark's notes are accurate when it raises one; it raises too few.

| Sense check, against 9 known misreadings per text | 猫八 | 雪景色 | Cost |
|---|---|---|---|
| Spark, 3,000-character windows | 2 | 0 | $0.55 for both |
| Spark, whole text in one call | 1 | — | $0.18 |
| Wonder, 3,000-character windows | — | about 3, plus 9 more real ones | $0.65 |
| Wonder, whole text in one call | — | 0 (4 notes) | $0.26 |

The final read with a sense pass added to its prompt, the whole text in one call:

| Final read | 猫八 | 雪景色 | Cost per text |
|---|---|---|---|
| Old prompt, Spark (the released runs) | 0 | 0 | about $0.17 |
| New prompt, Spark | 1 | 2 | $0.17 |
| New prompt, Wonder | 3 | 1 | $0.31 |

- **Spark spent 6 of its 9 fixes on italics and dashes.**
- **Wonder found real misreadings the audit hadn't listed.** In 猫八, 腹を痛める means spending his own money, the point of the lamp episode, and 産湯 is a claim about where his wife was born.
- **These are one call per model per text,** so they only show a direction.

**A third text, and every fix judged blind.** To settle Spark against Wonder, we ran the new final read twice more per model on 「死剣と生縄」. Then all 66 fixes from the eight reads were judged blind, shuffled and unlabelled. Each was marked as a real meaning fix, a consistency fix (names, italics, dashes, grammar), harmless polish, or wrong.

| Final read, new prompt | Reads | Fixes | Meaning | Consistency | Polish | Wrong | Cost per read |
|---|---|---|---|---|---|---|---|
| Spark | 4 | 43 | 5 | 23 | 11 | 4 | $0.10–0.17 |
| Wonder | 4 | 23 | 10 | 7 | 4 | 2 | $0.07–0.35 |

- **Wonder made twice as many meaning fixes from half as many edits,** and on every text. In 猫八 it made 2 to Spark's 1, in 雪景色 2 to 1, and in 死剣と生縄 6 to 3.
- **Spark's read is mostly a copy-edit:** macrons, italics, one term for one thing.
- **Both vary a lot between reads.** Spark's two reads of 死剣と生縄 made 0 and 3 meaning fixes; Wonder's made 6 and nothing at all. A read that returns nothing on a 15,000-character text isn't always a clean bill.

## What it shows

- **Misreadings are the main quality gap, and they're local.** Each sits in a sentence. None needed anything from the far end of the text to see.
- **Each layer catches different ones.** Wonder's windowed check and Wonder's final read caught mostly different misreadings. Layers with different seams (pages for the drafter, parts for the readers and the desk, the whole text for the final read) should add up better than any one of them.
- **Asking for a check helps only if the model can do it.** The sense pass took Spark's final read from 0 to 1–2 of 9; Wonder reached 1–3. About two-thirds of what a careful bilingual reader finds is still left for the editor.
- **One big call finds less than several small ones.** Wonder found 12 problems in four windows of 雪景色 and 4 in one call on the whole text.
- **Tool calls work on Meta's API.** A function-tool loop ran on Spark through the OpenAI SDK. `tool_choice` takes `"auto"` only, so a call can't be forced, but a tool works alongside a structured answer.

## What changed

- **Note counts are now up to the part.** The readers no longer hear that fewer notes are better: some parts get none and some need many. The final read no longer hears that a clean read is expected.
- **The faithful reader and the final read check sense first:**
  - a dropped subject;
  - a kinship term from the wrong side;
  - reported speech;
  - a set phrase or period word taken literally;
  - a negation or question turned round.
- **A voice take is now a label and a few sentences:** the narration, how the main speakers sound and differ, and what English would be wrong. A one-line take left every character talking alike.

## Decided

- **The final read moves to Wonder and works on meaning.** It costs about $0.20 more per 20,000 characters, about $1.40 more on a 135,000-character book. When it returns nothing it's asked again once, as the desk already is.
- **A new Spark copy editor takes the consistency work:** macrons, name forms, italics, one term for one thing. It gets a code-made list of every word spelled more than one way, and the name readings the ruby gives.
- **Code makes the mechanical choices that need no judgement:** one quote style, one dash, British spelling.
- **One shared edit tool serves the desk, the final read and the copy editor.** An edit whose words aren't found exactly once comes back to the model with the matches, instead of being dropped.

## First runs of what was built

- **The final read with the edit tool, on Wonder, on 「雪景色」:** two turns, 5 meaning fixes, none refused, $0.33. The fixes:
  - who was to call him;
  - the 鬨の声 roar;
  - a tattoo that contradicted an earlier paragraph;
  - 鈍えや as "slowpokes";
  - chanting in time.
- **The copy editor on 「死剣と生縄」 took three tries to get right:**
  - **First,** without the English (the text is just over the length that's sent whole), it fixed the macrons and left the misread names alone. It said it couldn't check them blind.
  - **Then,** with the English, it ran out of turns at 12.
  - **With 30 turns** and several edits allowed per turn, it fixed every name the ruby contradicted: Ikinawa, Anba, Shiizuka, Iioka, Imabori, Edozaki, Ashihara. It made Ryūjirō one form throughout. That came to 62 paragraphs, for $0.32, with 96% of its input served from the cache.
