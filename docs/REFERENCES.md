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

→ Two independent readers rather than a translator revising itself: one holds the Japanese, one holds the English, and neither sees the other's notes. The audits always read against the Japanese.

## Why the desk decides, with no rounds of debate

- **Wynn, Satija & Hadfield (2025)**, "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate". https://arxiv.org/abs/2509.05396
- **Yao et al. (2025)**, "Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate". https://arxiv.org/abs/2509.23055
- **Cemri et al. (2025)**, "Why Do Multi-Agent LLM Systems Fail?". https://arxiv.org/abs/2503.13657

→ One desk per part weighs both readers' notes once, gives a reason for every decision, and sends a real disagreement to the editor as a fork (`STAGES.md`, "How the readers and the desk work").

## How we judge the results

- **Panickssery, Bowman & Feng (2024)**, "LLM Evaluators Recognize and Favor Their Own Generations", NeurIPS 2024. https://arxiv.org/abs/2404.13076
- **Zheng et al. (2023)**, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena". https://arxiv.org/abs/2306.05685
  Judges favour their own output and are swayed by order and length.

→ Blind audits: versions unlabelled, shuffled, against the Japanese, beside a one-shot baseline; rankings trusted over counts (`experiments/README.md`).

## Translation and publishing

- **Antoine Berman**, "La traduction comme épreuve de l'étranger" (1985); in English as "Translation and the Trials of the Foreign", in Venuti (ed.), *The Translation Studies Reader*. The names the readers use for what a translation does to a text (rationalisation, clarification, ennoblement, destroyed networks of repetition) come from here (`prompts/house-brief.md`).
- **Edith Grossman**, *Why Translation Matters* (Yale UP, 2010).
- How a translated book moves through a house (translator, editor, copy-editor, proofreader; the translator owns the wording, others query it) is described in `FROM-TRANSLATORS.md`.
