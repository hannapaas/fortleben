# Experiments

What we tried while building the house, what happened, and what we changed because of it. One file per experiment, in the order we ran them. Each one names its question, the runs, the numbers, and what changed in the engine.

## How we test

- **One short text, 「晩餐」** (Shiraki Shizu, about 3,400 characters, 38 paragraphs). It's long enough to have a cast, a motif network and a vision scene, and short enough that a full run costs well under a dollar. We test short and design for long: the later stages work a part at a time, and a short story is usually one part (`STAGES.md`).
- **One change at a time.** The reading and the story bible come from the response cache unless the experiment is about them, so a comparison changes only what it means to change.
- **A one-shot baseline in every comparison:** Spark, given only "Translate the following Japanese text into English." If the house can't beat that, the house isn't worth its cost.
- **Blind audits.** The reviewer gets the Japanese and the versions, unlabelled and in shuffled order, with the same instructions for every version. It marks two things: fidelity slips (critical, serious, minor) and translationese, meaning sentences a literary editor would mark as reading like a translation rather than English. Precision over recall: only marks an editor would agree with.
- **We trust rankings more than counts.** The same version audited twice moves by about three serious marks. A ranking that holds across separate audits is a result; a difference of two or three marks is not.

## The experiments

| # | Question | Runs | What changed |
|---|---|---|---|
| [1](01-first-pipeline.md) | Does the first design, a critic plus a translator answering it, make good English? Does a sentence-by-sentence referent map help? | first session | Faithful but stiff. A misreading went into the bible and was enforced everywhere. We moved to two independent readers and one desk, and dropped the referent map |
| [2](02-who-drafts-who-edits.md) | Which model should draft, read and edit: Spark or Wonder? | 1–11 | No clear quality difference; Spark throughout costs about 30% less. The model became an option per stage |
| [3](03-stiffness.md) | Why is the English stiff, and do prompt fixes, a voice trial or a read-through cure it? | 11–14 | The fixes worked and the stiffness didn't go. The readable reader was capped at 8 notes and always hit the cap |
| [4](04-placeholders.md) | With room for more notes and a Wonder desk, does the English loosen? | 15–16 | Half the desk's edits failed. The cause was the ledger's `{t:id}` placeholders, so we dropped the ledger |
| [5](05-plain-first-draft.md) | Should the first draft be written as English, with fidelity restored afterwards? | 16–18 | Yes. The plain draft came out more faithful and less stiff, and ranked above the one-shot in two separate audits |
| [6](06-translator-notes-and-wonder-readers.md) | Does the desk do better with the translator's notes? Are Wonder readers better than Spark? | 18, A, B | The notes changed little, because the drafter writes few. Wonder readers ranked first and kept every one of her images. A desk answer that decides no notes is now asked for again |
| [7](07-readers-propose-rewrites.md) | If readers may propose rewritten sentences or passages, does the English loosen? | A, B | No improvement, and confounded by a new draft. Spark and Wonder readers came out level |
| [8](08-a-second-text.md) | Does the house hold up on a different text (「酒虫」, Akutagawa)? The first run of the lever, the estimate and the desk retry | 22 | It ranked first, above a 1930 human translation and well above the one-shot. The machinery worked; the lever's one finding was a false alarm. Its one serious slip was a prompt example taken as a rule |
| [9](09-kusamakura.md) | And on a third, two-voiced text: 『草枕』 chapter II, beside a 1927 human translation? | 32 | First again, ahead of the one-shot and Takahashi's abridged *Unhuman Tour*. The forks caught the three hardest questions; the mid-chapter dialogue is still stiff |
