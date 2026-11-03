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


# Measured dollars per 1,000 source characters, per stage and model, from runs on 晩餐.
# The chapter-by-chapter stages scale with length, so per-character rates carry over to long texts.
STAGE_RATES = {
    "first-read": {"wonder": 0.025}, "crux-check": {"wonder": 0.025}, "bible": {"spark": 0.015},
    "checkpoint": {"spark": 0.036, "wonder": 0.075},  # page 1 once per voice take: priced as CHECKPOINT_CHARS of draft
    "draft": {"spark": 0.036, "wonder": 0.075}, "readers": {"spark": 0.033, "wonder": 0.065},
    "desk": {"spark": 0.019, "wonder": 0.047}, "final-read": {"spark": 0.015, "wonder": 0.04},
    "notes": {"spark": 0.0075},
}
CHECKPOINT_CHARS = 3 * 650  # three voice takes of one page (pager.TARGET), whatever the length of the work
RUN_MARGIN = 1.5  # an estimate is meant to be high: a run that starts should not run out mid-way


def estimate_run(chars: int, chapters: int, options: dict) -> float:
    """What a whole run will cost, overestimated: every stage live (no cache), and every earlier
    chapter taken back to the desk once."""
    pick = {"draft": "draft_model", "checkpoint": "draft_model",
            "readers": "reader_model", "desk": "desk_model", "final-read": "final_model"}
    total = 0.0
    for stage, rates in STAGE_RATES.items():
        rate = rates.get(options.get(pick.get(stage, ""), "") or "spark") or next(iter(rates.values()))
        if stage == "checkpoint":
            total += rate * min(chars, CHECKPOINT_CHARS) / 1000 if options.get("checkpoint") else 0
            continue
        total += rate * chars / 1000
        if stage == "desk" and chapters > 1:
            total += rate * chars / 1000 * (chapters - 1) / chapters  # the emergency lever's pass back
    return round(total * RUN_MARGIN, 2)


def _cap(name: str, default: float) -> float:
    return float(os.environ.get(name) or default)


class Budget:
    """Caps for one process. The run cap is per run; daily and total are read from the ledger."""

    def __init__(self, conn: sqlite3.Connection, run_cap: float | None = None, own_key: bool = False):
        self.conn = conn
        self.own_key = own_key  # a client on an editor's own key: their run cap applies, the house's day and total don't
        self.cap_given = run_cap is not None  # False: the default, which a resumed run replaces with its own
        self.run_cap = run_cap if run_cap is not None else _cap("KEIKAKU_CAP_RUN", 3.0)
        self.daily_cap = _cap("KEIKAKU_CAP_DAILY", 10)
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
