"""The spend ledger, run estimates, caps and the kill switch.

Every call is priced from the API's own usage figures. Before a call, an estimate is
checked against the run, daily and total caps; a call that would pass a cap is refused.
The caps are code, not a request in a prompt (docs/STAGES.md, "What code enforces").
"""

import os
import sqlite3
from dataclasses import dataclass

# Dollars per million tokens: (input, cached input, output). Reasoning is billed as output.
PRICES = {
    "muse-spark-1.3": (1.25, 0.15, 4.25),
    "muse-wonder-1.0": (4.00, 0.20, 20.00),
}
WEB_SEARCH_USD = 2.50 / 1000



class CapExceeded(Exception):
    """A call was refused because it would pass a spend cap."""


class HouseClosed(Exception):
    """The kill switch is off: no live calls."""


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    web_searches: int = 0

    def cost(self, model: str) -> float:
        p_in, p_cached, p_out = PRICES[model]
        uncached = max(self.input_tokens - self.cached_tokens, 0)
        return (
            uncached * p_in + self.cached_tokens * p_cached + self.output_tokens * p_out
        ) / 1e6 + self.web_searches * WEB_SEARCH_USD



def estimate(model: str, input_chars: int, expected_output_tokens: int) -> float:
    """A cautious pre-call estimate: Japanese-heavy input at ~1.5 tokens a character, none of it cached."""
    p_in, _, p_out = PRICES[model]
    return (input_chars * 1.5 * p_in + expected_output_tokens * p_out) / 1e6


# What each stage's calls take in and give out, in tokens, fitted on eight runs on the defaults
# (3,400–19,500 characters: 晩餐, 草枕 II, 書記官, 雪景色, 死剣と生縄, 猫八; 4 Nov 2026).
# A call's input is a fixed part (the prompt, the reading, the bible) plus a part that grows with the
# source it sees; its output, reasoning included, stays about the same however long that source is.
# So a stage is priced per call: once for the whole text, once a part, or once a page.
# stage: (how often, model option or None, default model, input tokens per source character,
#         fixed input tokens, output tokens per call)
SHAPES = {
    "parts":      ("run",  None,            "spark",  0.26,  2_300,  1_500),
    "first-read": ("run",  None,            "wonder", 1.1,   2_100,  3_900),
    "crux-check": ("run",  None,            "wonder", 0.84,  4_400,  2_700),  # two calls; the head's sees no source
    "bible":      ("run",  None,            "spark",  0.86,  5_000,  None),   # output grows with the cast and parts
    "draft":      ("page", "draft_model",   "spark",  1.02,  8_600,  3_500),
    "readers":    ("part", "reader_model",  "spark",  6.7,     500, 25_000),  # two calls, one per reader
    "desk":       ("part", "desk_model",    "wonder", 2.86,  8_600,  6_500),
    "final-read": ("part", "final_model",   "wonder", 2.36,  7_200,  9_000),  # Wonder since experiment 10: 5,900–9,400 out over two turns
    "copy-desk":  ("turn", "copy_model",    "spark",  0.65, 14_000,  1_400),  # a tool loop: each turn resends the English, mostly cached
    "notes":      ("part", None,            "spark",  2.72,  8_400,  2_200),
}
PAGE_CHARS = 540  # source characters a drafting page came to on average (pager.TARGET is the most)
PART_CHARS = 20_000  # before the planner has run: it kept stories of 15–20k characters as one part, and keeps a book's parts under about 20,000
DRAFT_UNCACHED = 4_500  # a drafting call's own page; the reading, the bible and the source before it are cached
CHECKPOINT_PAGES = 3  # page 1 drafted once per voice take
RUN_MARGIN = 1.15  # the eight runs above came to 0.89–1.10 of the estimate before it
MODELS = {"spark": "muse-spark-1.3", "wonder": "muse-wonder-1.0"}


def _bible_output(chars: int) -> int:
    return min(5_000 + int(0.6 * chars), 32_000)


def _call(model: str, input_tokens: float, output_tokens: float, cached: float = 0) -> float:
    return Usage(int(input_tokens), int(cached), int(output_tokens)).cost(MODELS[model])


def estimate_run(chars: int, chapters: int | None, options: dict) -> float:
    """What a whole run should cost, every call live (no cache), with every earlier part taken back to
    the desk once by the emergency lever. A short text is seen whole by every page; a long one, a part
    at a time (house/context.py). `chapters` is the planner's count of parts, or None before it has run."""
    from house.context import WHOLE_TEXT_CHARS
    chapters = max(chapters or -(-chars // PART_CHARS), 1)
    part = chars / chapters
    seen = chars if chars <= WHOLE_TEXT_CHARS else part  # what a drafting page sees of the source
    pages = max(1, round(chars / PAGE_CHARS))
    total = 0.0
    for stage, (per, option, default, per_char, fixed, out) in SHAPES.items():
        model = (options.get(option) if option else None) or default
        if stage == "bible":
            out = _bible_output(chars)
        if per == "run":
            total += _call(model, fixed + per_char * chars, out)
        elif per == "turn":  # the copy editor sends the English whole up to about 50,000 tokens, then works from lists
            inp = fixed + min(per_char * chars, 50_000)
            turns = min(30, 2 + chars // 600)  # its cap is 30: 晩餐 took 1 turn ($0.015), 死剣と生縄 (15,104 characters) all 30 ($0.32)
            total += turns * _call(model, inp, out, cached=max(inp - DRAFT_UNCACHED, 0))
        elif per == "part":
            calls = chapters + (chapters - 1 if stage == "desk" else 0)  # the lever's pass back
            total += calls * _call(model, fixed + per_char * part, out)
        else:
            n = pages + (CHECKPOINT_PAGES if options.get("checkpoint") else 0)
            inp = fixed + per_char * seen
            total += n * _call(model, inp, out, cached=max(inp - DRAFT_UNCACHED, 0))
    return round(total * RUN_MARGIN, 2)


def _cap(name: str, default: float) -> float:
    return float(os.environ.get(name) or default)


class Budget:
    """Caps for one process. The run cap is per run; daily and total are read from the ledger."""

    def __init__(self, conn: sqlite3.Connection, run_cap: float | None = None, own_key: bool = False):
        self.conn = conn
        self.own_key = own_key  # a client on an editor's own key: their run cap applies, the house's day and total don't
        self.cap_given = run_cap is not None  # False: the default, which a resumed run replaces with its own
        self.run_cap = run_cap if run_cap is not None else _cap("KEIKAKU_CAP_RUN", 30.0)  # a novel fits (docs/ARCHITECTURE.md, "Cost model")
        self.daily_cap = _cap("KEIKAKU_CAP_DAILY", 30)
        self.total_cap = _cap("KEIKAKU_CAP_TOTAL", 100)

    def room(self) -> float:
        """The most a new run may spend: its own cap, or less if the day's or the total's is nearer."""
        return min(self.run_cap, self.daily_cap - self.spent(today=True), self.total_cap - self.spent())

    def spent(self, run_id: int | None = None, today: bool = False) -> float:
        """What one run spent, or, with no run, what the house's own key spent: a run on an editor's
        own key (options.own_key) counts against its run cap only, never the house's daily or total."""
        sql, args = "SELECT COALESCE(SUM(cost_usd), 0) FROM call WHERE 1=1", []
        if run_id is not None:
            sql += " AND run_id = ?"
            args.append(run_id)
        else:
            # run_id IS NULL first: a call outside any run (a comment screened, an audit) is the house's,
            # and NULL NOT IN (...) would leave it out
            sql += " AND (run_id IS NULL OR run_id NOT IN (SELECT id FROM run WHERE json_extract(options, '$.own_key') = 1))"
        if today:
            sql += " AND date(created_at) = date('now')"
        return self.conn.execute(sql, args).fetchone()[0]

    def check(self, est_usd: float, run_id: int | None) -> None:
        if os.environ.get("HOUSE_OPEN", "true").lower() == "false":
            raise HouseClosed("HOUSE_OPEN=false: the house is closed to live calls")
        checks = [] if self.own_key else [("total", self.spent(), self.total_cap),
                                          ("daily", self.spent(today=True), self.daily_cap)]
        if run_id is not None:
            checks.append(("run", self.spent(run_id), self.run_cap))
        for name, spent, cap in checks:
            if spent + est_usd > cap:
                raise CapExceeded(
                    f"{name} cap ${cap:.2f}: spent ${spent:.4f}, this call ~${est_usd:.4f}"
                )
