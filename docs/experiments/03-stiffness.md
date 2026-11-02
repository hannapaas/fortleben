# 3. Why is the English stiff?

**Question.** By now the house's English was accurate but stiff: built clause by clause in the shape of the Japanese. Could we fix that?

**Set-up.** Spark throughout, as version D of experiment 2. Three variants, each audited with the repo's audit prompts (`audit-spans` for fidelity, `audit-readable` for translationese) beside the one-shot:

- **E1, four fixes:**
  - the first read must fill every field;
  - the drafter gets whole paragraphs, not numbered sentences;
  - the drafting prompt is rebalanced, asking two questions of every sentence (does it do what the Japanese does, and would a good writer have written it?);
  - the style sheet gives guidance with reasons, not rules.
- **E2, = E1 plus two steps:**
  - a voice trial, which drafts page 1 in each voice the reading offers and picks one;
  - a read-through, in which the translator reads its own chapter before the readers see it.
- **E3, = E2 with Wonder drafting.**

| Version | Fidelity notes (serious) | Translationese marks (serious) | Whole run |
|---|---|---|---|
| D, before | 5 (4) | 19 (8) | $0.58 |
| E1 | 7 (0) | 26 (10) | $0.52 |
| E2 | 5 (1 critical) | 16 (7) | $0.64 |
| E3 | 6 (2) | 19 (10) | $1.01 |
| One-shot | 11 (3) | 11 (6) | $0.03 |

## What happened

- **The fixes did their own jobs.** The reading's fields were full and the crux check agreed with it. The style sheet stopped inventing rules.
- **The stiffness didn't go.** Our versions differed within the noise, and the one-shot still read most like English.
- **The voice trial picked the voice the reading lists first.** So E1 and E2 drafted the same page 1.
- **Wonder drafting cost 1.6 times as much and read no better.**
- **The readable reader was capped at 8 notes per chapter, and it hit the cap in every run.** The audit found 16 to 26 problems in the chapter, so most of what the readable reader saw could never reach the desk.
- **Every step after the draft makes small edits a span at a time.** That's right for fidelity. But a stiff sentence needs rebuilding, and no step was placed to rebuild one.

## What changed

- **The readers' cap went from 8 to 20 notes per chapter.** A limit stays, so the readers can't spiral.
- **The voice trial and the read-through stay as options** (`--voice-trial`, `--read-through`), off by default (both later removed: neither had helped).
- **The question for the next experiments became where sentences get rebuilt.**
