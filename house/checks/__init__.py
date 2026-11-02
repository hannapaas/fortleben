"""Deterministic checks the copy desk and the desk's edits run: no stray script, no paragraph far
shorter than its Japanese."""

import re
import statistics

STRAY_SCRIPT = re.compile(r"[Ѐ-ӿ֐-׿؀-ۿ฀-๿가-힯]")
def stray_scripts(text: str) -> list[str]:
    found = sorted(set(STRAY_SCRIPT.findall(text)))
    return [f"characters from an unexpected script: {''.join(found)}"] if found else []


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
