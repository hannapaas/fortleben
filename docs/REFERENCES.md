# References

The papers, books and experiments behind the house's design, grouped by the decision each one bears on. Our own experiments are in `experiments/`.

## How much the drafter translates at once

- **Karpinska & Iyyer (2023)**, "Large language models effectively leverage document-level context for literary translation, but critical errors persist", WMT 2023. https://aclanthology.org/2023.wmt-1.41
  Translating whole paragraphs beats sentence by sentence (fewer mistranslations, fewer inconsistencies of grammar and style), but critical errors, omissions among them, remain. Japanese is among the source languages. → The drafter works a page of whole paragraphs at a time (`house/pager.py`), and the copy desk checks each paragraph's length against its Japanese.

## What the drafter is given

- **Liu et al. (2024)**, "Lost in the Middle: How Language Models Use Long Contexts", TACL. https://arxiv.org/abs/2307.03172
  Models use information at the start and end of a long context best, and the middle worst.
- **Modarressi et al. (2025)**, "NoLiMa: Long-Context Evaluation Beyond Literal Matching", ICML 2025. https://arxiv.org/abs/2502.05167
  When the link between a question and the passage that answers it isn't a literal word match, most long-context models fall to under half their short-context score by about 32,000 tokens.
- **Hong, Troynikov & Huber (2025)**, "Context Rot", Chroma technical report. https://research.trychroma.com/context-rot
  Reliability falls as input grows, even on trivial tasks.
- **Wang et al. (2025)**, "DelTA: An Online Document-Level Translation Agent Based on Multi-Level Memory", ICLR 2025. https://arxiv.org/abs/2410.08143
  A small memory (names as first translated, a running summary, retrieved earlier pairs) improves consistency across a long document.
- **Wang, Liu et al. (2026)**, "Loong: A Human-Like Long Document Translation Agent with Observe-and-Act Adaptive Context Selection". https://arxiv.org/abs/2605.30274
  Unfiltered context, including the full history, sometimes scores below no context at all.

→ The house reads the whole book once and writes down what matters (the reading and the story bible, `STORY-STATE.md`). Each drafting call gets that, the page, and a few paragraphs either side. The whole source goes in only for a short text (`context.WHOLE_TEXT_CHARS`); a long one gets its own part and a short summary of every other part.

## Translationese, and why the first draft is written as English

- **Li, Zhang et al. (2025)**, "Lost in Literalism: How Supervised Training Shapes Translationese in LLMs", ACL 2025. https://aclanthology.org/2025.acl-long.630
  Language models translate literally because the training data does; it's a default, not an accident of prompting.
- **Zhang, Zhao & Eger (2025)**, "How Good Are LLMs for Literary Translation, Really?", NAACL 2025. https://arxiv.org/abs/2410.18697
  The newest models are more literal and less varied than human translators; literalness, not fluency, is the gap.
- **Reinhart et al. (2025)**, "Do LLMs write like humans? Variation in grammatical and rhetorical styles", PNAS 122. https://arxiv.org/abs/2410.16107
  Instruction-tuned models keep a dense, noun-heavy, participial style even when imitating fiction, and the difference doesn't shrink with scale; asking for natural prose doesn't remove it.
- **Daniel Hahn**, *Catching Fire: A Translation Diary* (Charco Press, 2022).
  A working translator's account of several drafts: a fast first draft, revision against the source, then revision without it, reading the English alone.

→ The plain drafting prompt asks for English first (`prompts/translate-draft-plain.md`); the faithful reader then restores what was lost. Experiment 5 found the order mattered in our runs too.

## Who checks the draft

- **Xu et al. (2024)**, "Pride and Prejudice: LLM Amplifies Self-Bias in Self-Refinement", ACL 2024. https://arxiv.org/abs/2402.11436
  A model refining its own output favours it: scores rise without real gains.
- **Kamoi et al. (2024)**, "When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction", TACL. https://arxiv.org/abs/2406.01297
- **Chen, Guo, Haddow & Heafield (2024)**, "Iterative Translation Refinement with Large Language Models", EAMT 2024. https://arxiv.org/abs/2306.03856
  A revision pass makes English more natural, and it has to stay anchored to the source.
- **Wu et al. (2025)**, "(Perhaps) Beyond Human Translation: Harnessing Multi-Agent Collaboration for Translating Ultra-Long Literary Texts" (TransAgents), TACL 13. https://arxiv.org/abs/2405.11804
  Preferred by readers of the English alone, while drifting from the source.
- **Ferstler, Podoxin, Brassington, Taboada, Karpinska & Grundkiewicz (2026)**, "AI translation of literary texts is 'fine', but readers still prefer human translations". https://arxiv.org/abs/2606.26040
  Agentic translation of novels, Japanese among them: metrics and an LLM judge preferred the machine translations, readers preferred the human ones. The Japanese problems readers flagged were speaker attribution, self-reference and sentence structure.

→ Two independent readers rather than a translator revising itself: one holds the Japanese, one holds the English, and neither sees the other's notes. The faithful reader is asked about subjects and speakers the text doesn't support. The audits always read against the Japanese, and we don't claim the house beats a human translator on a judge's say-so.

## Why the desk decides, with no rounds of debate

- **Wynn, Satija & Hadfield (2025)**, "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate". https://arxiv.org/abs/2509.05396
- **Yao et al. (2025)**, "Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate". https://arxiv.org/abs/2509.23055
- **Cemri et al. (2025)**, "Why Do Multi-Agent LLM Systems Fail?". https://arxiv.org/abs/2503.13657

→ One desk per part weighs both readers' notes once, gives a reason for every decision, and sends a real disagreement to the editor as a fork (`STAGES.md`, "How the readers and the desk work").

## How we judge the results

- **Panickssery, Bowman & Feng (2024)**, "LLM Evaluators Recognize and Favor Their Own Generations", NeurIPS 2024. https://arxiv.org/abs/2404.13076
- **Zheng et al. (2023)**, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena". https://arxiv.org/abs/2306.05685
  Judges favour their own output and are swayed by order and length.

→ Blind audits: versions unlabelled, shuffled, against the Japanese, beside a one-shot baseline and, where one exists, a published human translation; rankings trusted over counts (`experiments/README.md`).

## How publishing houses and fan translators divide the work

- **One owner per text, everyone else queries.** In a publishing house the translator owns the wording and editors, copy-editors and checkers raise queries; two translators' drafts are never blended (Clark & Phillips, *Inside Book Publishing*; Peter Ginna (ed.), *What Editors Do*, Chicago, 2017). → The desk is the only one who writes after the draft, and every note comes back taken, declined or forked; a head picks between options and never merges them (`prompts/head-select.md`).
- **Meaning and English are checked separately.** Bilingual reader and line editor in publishing; translation checker and editor in fan subtitling; proofing rounds and a final smooth read at Distributed Proofreaders (https://www.pgdp.net/wiki/Beginners%27_FAQ). → The faithful and the readable reader.
- **"Reviewed" means a second, different person.** Wikisource validates a page only when someone other than its proofreader checks it (https://wikisource.org/wiki/Help:Page_status). → The house labels what it did in words (*draft*, *house-checked*) and keeps *human-reviewed* for a person.
- **The keikaku test.** The house is named after a fansub joke: a translator's note explaining that "keikaku means plan" (https://fanlore.org/wiki/All_according_to_keikaku). → Footnotes only for what the sentence can't give the reader (`prompts/notes.md`).
- **Sensei, where the relationship is the word.** Both English translations of Sōseki's *Kokoro* keep "Sensei" (Edwin McClellan, 1957; Meredith McKinney, 2010). → The example the analyst is given for a style-sheet entry with its reason (`prompts/analyst-bible.md`).

## Rights

- **Aozora Bunko's terms for its files** (収録ファイルの取り扱い規準, https://www.aozora.gr.jp/guide/kijyunn.html): the texts may be copied, reformatted and translated, with the source credited and no claim of endorsement. → Every release carries the file's colophon, and every download adds that Aozora Bunko hasn't endorsed the edition (`house/stages/release.py`, `house/fixture.py`).
- **Japanese Copyright Act, art. 60:** an author's moral rights are protected after death, so nothing may be presented as the author's that the author didn't write. → Notes and the house's reading are labelled as the house's and are never voiced as the author (`prompts/notes.md`, `STORY-STATE.md` §0).
- **The works we translate:** the author died by 1931 (a few later, each with a stated reason) and the work was first published by 1930, so it's out of copyright in Japan and, by its date of publication, in the US (`fixtures/works.json` carries each work's rights record, and `house/works.py` refuses one that doesn't pass).

## Translation and publishing

- **Antoine Berman**, "La traduction comme épreuve de l'étranger" (1985); in English as "Translation and the Trials of the Foreign", in Venuti (ed.), *The Translation Studies Reader*. The names the readers use for what a translation does to a text (rationalisation, clarification, ennoblement, destroyed networks of repetition) come from here (`prompts/house-brief.md`).
- **Edith Grossman**, *Why Translation Matters* (Yale UP, 2010).
- How a translated book moves through a house (translator, editor, copy-editor, proofreader; the translator owns the wording, others query it) is described in `FROM-TRANSLATORS.md`.
