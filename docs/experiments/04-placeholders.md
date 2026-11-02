# 4. The ledger placeholders

**Question.** With room for 20 notes per reader and Wonder at the desk, does the English loosen?

**Set-up.** Run 15: Spark drafting, Spark readers, a Wonder desk. The readers could now raise up to 20 notes per chapter.

## What happened

- **The readers raised 28 notes:** 17 faithful and 11 readable.
- **The desk couldn't apply about half of its edits.** 15 were refused, because the words they quoted weren't in the text the desk was editing, and 17 notes went unaddressed.
- **The cause was the ledger.** The bible's ledger was meant to hold terms, but it held whole phrases. The draft carried them as `{t:id}` placeholders, rendered differently for each edition:

| Placeholder | What it put into the sentence |
|---|---|
| `{t:rice}` | "freshly cooked rice, steaming" |
| `{t:storm}` | "storm; sound of rain and wind" |
| `{t:nursing}` | "put the baby to her breast and nursed her" |
| `{t:boya}` | "baby — see note; Curious/Student keep Bōya with note" |

- **The readers saw the rendered phrases; the desk saw the placeholders.** So the desk quoted words that weren't in its copy of the text.
- **The same placeholders had been causing stiffness all along.** "The father hurriedly put freshly cooked rice, steaming into the child's mouth" is the rice placeholder dropped into a sentence. They also produced "freshly cooked freshly cooked rice", and a policy note spoken in the dialogue. That made five bugs from one mechanism.

## What changed

- **We dropped the ledger.** The translator writes plain English. What stays in Japanese (Sensei, say, where the whole relationship is in that word) belongs to the style sheet, with its reason. The three editions share one English and differ in their notes.
- **We added a plain doubled-word check,** in place of the placeholder checks (later removed: the final read does it now).

Run 16, the same set-up without the ledger, ran cleanly. The readers raised 28 notes and the desk took 23 and declined 5. No edit failed and no note went unaddressed. A blind audit, beside the one-shot and run 13 (E2 from experiment 3):

| | Fidelity (critical / serious / minor) | Translationese (serious / minor) |
|---|---|---|
| Run 16 | 0 / 1 / 6 | 6 / 20 |
| One-shot | 0 / 2 / 13 | 2 / 14 |
| Run 13 | 2 / 2 / 7 | 9 / 20 |

- **Run 16 was the most faithful of the three.** It was the only version that rendered the story's rhetorical question as one: "What did the suffering and sorrow of each day matter?"
- **The one-shot still read best.** The auditor ranked it first, run 16 second and run 13 last.
