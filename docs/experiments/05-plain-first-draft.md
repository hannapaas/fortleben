# 5. A plain first draft

**The hypothesis.** The two kinds of fault cost different amounts to fix:
- **A fidelity loss is a few words:** a lost image, a varied repetition, something said that the author left unsaid. The faithful reader can point the desk at it.
- **A stiff sentence needs a new sentence,** and after the draft nobody writes whole sentences.

So the first draft should be written as English, and fidelity restored afterwards. That's also how translators describe their own drafts.

**Set-up.** The same reading and bible (from the cache), Spark readers and a Wonder desk throughout. Only the drafting prompt changes:

| Run | Drafting prompt |
|---|---|
| 16 | `translate-draft`: written to be faithful first, then English |
| 17 | `translate-draft-plain`, first version: a short prompt of principles that says why the draft is written as English |
| 18 | `translate-draft-plain`, shorter still |

## What happened

**Two separate blind audits:**

| Audit | Version | Fidelity (critical / serious / minor) | Translationese (serious / minor) | Rank |
|---|---|---|---|---|
| A | Run 17 | 0 / 0 / 5 | 6 / 16 | 1 |
| A | Run 16 | 0 / 0 / 9 | 3 / 25 | 2 |
| A | One-shot | 0 / 3 / 9 | 3 / 13 | 3 |
| B | Run 17 | 0 / 0 / 7 | 5 / 14 | 1 |
| B | Run 18 | 0 / 1 / 8 | 5 / 9 | 2 |
| B | One-shot | 0 / 3 / 10 | 5 / 11 | 3 |

- **The plain draft came out more faithful, not less.** Run 17 had the fewest fidelity slips of any version, and no serious one in either audit. It kept the story's key pair of words, なつかしみと許し, as "nostalgia and forgiveness" throughout. The one-shot turned them into "tenderness and forgiveness", which breaks the link back to the "nostalgic dream" earlier in the story.
- **It's the first of our versions to rank above the one-shot,** and it did so in both audits.
- **The two plain prompts are level within the noise.** Run 18 had fewer stiff spots (14 against 19) and one more serious fidelity slip.
- **The audits counted 19 to 22 stiff-sentence marks on the plain draft,** against 16 for the one-shot. The serious ones are a handful of long sentences that every version, the one-shot included, still builds in Japanese order (p5, p8, p13).

**Four versions of two paragraphs.** In p11 the potato tastes wrong, and her heart turns away:

> 彼女はふと驚いたやうに黙って前歯でかみなほしたが、彼女の心は、いつか淋しくうつむいてしまってゐた。

| Run 16 | Run 17 | Run 18 | One-shot |
|---|---|---|---|
| …but her heart had already bowed down, lonely. | …but her heart had already sunk, lonely and downcast. | …but her heart had already sunk, lonely. | …but her heart had already sunk into lonely dejection. |

In p20 the vision's refrain ends on a shrug, "what do they matter":

> 一日々々の苦しみや悲しみがなんだらう。一日々々の疲れやなやみがなんだらう。

| Run 16 | Run 17 | Run 18 | One-shot |
|---|---|---|---|
| What did the suffering and sorrow of each day matter? What did the weariness and trouble of each day matter? | What is the suffering and sorrow of each day? What is the weariness and trouble of each day? | What of the suffering and sorrow of each day? What of the weariness and trouble of each day? | What are the suffering and sorrow of each day? What are the weariness and trouble of each day? |

The faithful-first draft (run 16) keeps her image of the heart that bows its head, and it's the only version that gets the shrug right. The plain drafts read better around those two lines, and lose a little of each. Those small losses are exactly what the faithful reader is there to catch.

## What changed

- **`translate-draft-plain` is the drafting prompt to beat,** chosen with `--draft-prompt`.
- **The reason sits in the code,** at the top of `house/stages/draft.py`.
- **What's left is a few long sentences per text built in Japanese order.** Every version, the one-shot included, gets them wrong.
