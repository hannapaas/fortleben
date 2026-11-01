"""Deterministic checks: shared by Source check (which runs them first) and the copy desk."""

import re
import statistics

TOKEN = re.compile(r"\{t:([\w-]+)\}")
STRAY_SCRIPT = re.compile(r"[Ѐ-ӿ֐-׿؀-ۿ฀-๿가-힯]")
# A small sample tic list; a longer one can come from the private overlay.
TICS = [
    (re.compile(r"\bnot (?:just |merely |only )?\w+(?: \w+)?, but\b", re.I), "not X but Y"),
    (re.compile(r"\btapestry\b", re.I), "tapestry"),
    (re.compile(r"\btestament to\b", re.I), "testament to"),
    (re.compile(r"\bin a way that\b", re.I), "in a way that"),
    (re.compile(r"\ba sense of\b", re.I), "a sense of"),
    (re.compile(r"\bsomehow\b", re.I), "somehow"),
]


SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|[\"“‘'(])$")


def render(english: str, terms: dict, view: str = "casual") -> str:
    """The English as a view shows it: each {t:id} token replaced by that view's rendering,
    capitalised where the token starts a sentence."""
    def sub(m):
        if m.group(1) not in terms:
            return m.group(0)
        out = terms[m.group(1)][view]
        if out and SENTENCE_START.search(english[:m.start()]):
            out = out[0].upper() + out[1:]
        return out
    return TOKEN.sub(sub, english)


def ledger(english: str, terms: dict) -> list[str]:
    """Every token resolves, and no word is doubled where a token meets the words around it."""
    problems = [f"unknown ledger token {{t:{t}}}" for t in TOKEN.findall(english) if t not in terms]
    for view in ("casual", "curious", "student"):
        text = render(english, terms, view)
        for m in re.finditer(r"\b(\w+(?: \w+)?) \1\b", text, re.I):
            if m.group(1).lower() not in ("that", "had", "very"):
                problems.append(f"doubled “{m.group(0)}” in the {view} view where a token meets the text")
                break
    return problems


def stray_scripts(text: str) -> list[str]:
    found = sorted(set(STRAY_SCRIPT.findall(text)))
    return [f"characters from an unexpected script: {''.join(found)}"] if found else []


def tics(english: str) -> list[str]:
    return [f"tic: {name}" for rx, name in TICS if rx.search(english)]


def length_ratios(pairs: dict[str, tuple[str, str]]) -> dict[str, float]:
    """English characters per Japanese character, per paragraph."""
    return {pid: len(en) / max(len(ja.strip("　 ")), 1) for pid, (ja, en) in pairs.items()}


def omissions(pairs: dict[str, tuple[str, str]], low: float = 0.55) -> dict[str, str]:
    """The omission guard: paragraphs whose length ratio is well under the text's own baseline.
    Short paragraphs (a word of dialogue) are skipped; their ratio says nothing."""
    ratios = {pid: r for pid, r in length_ratios(pairs).items() if len(pairs[pid][0]) >= 25}
    if len(ratios) < 4:
        return {}
    base = statistics.median(ratios.values())
    return {pid: f"length ratio {r:.2f} against the text's median {base:.2f}: possible omission"
            for pid, r in ratios.items() if r < base * low}
