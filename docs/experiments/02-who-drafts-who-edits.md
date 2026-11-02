# 2. Who drafts, who reads, who edits

**Question.** Spark is cheaper, and Wonder is the stronger reader. Where does Wonder earn its price: drafting, or reading and editing?

**Set-up.** The readers-and-desk pipeline from experiment 1, with the model chosen per stage. In every run, Wonder makes the first read and the crux check, and Spark writes the bible.

| Version | Draft | Readers | Desk | Whole run |
|---|---|---|---|---|
| A | Wonder | Spark | Spark | $0.81 |
| B / D | Spark | Spark | Spark | $0.58 |
| C | Spark | Wonder | Wonder | $0.82 |

## What happened

- **No version was clearly better.** The audits were noisy, and their differences sat within it.
- **Wonder drafting didn't make the prose better.** Wonder reading and editing didn't catch more.
- **The p7 misreading from experiment 1 was gone in every version.** That's because the cast now describes people rather than lines.
- **Strict JSON schemas mattered for Wonder.** Without them it left fields empty or filled them with filler, which once produced a bogus fork in every run. Wonder now runs with strict schemas. Spark runs without them, so its prompt caching works, and the client checks its output instead.

## What changed

- **The model is a run option per stage** (`--draft-model`, `--reader-model`, `--desk-model`). The default is Spark, which costs about 30% less, with no quality difference we could find.
- **Wonder keeps the whole-text reads:** the first read and the crux check, where one strong pass over the whole story is worth it.
