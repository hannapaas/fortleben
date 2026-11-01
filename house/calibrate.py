"""M0: the first real calls, and what reasoning actually costs.

Drafts the same ~1,000-character chunk of a work at low and at medium effort on Spark, makes
one Spark call with web search and one Wonder call, and reports input / cached / output /
reasoning tokens and dollars for each, from the API's own usage figures.
"""

import json
from pathlib import Path

from house import context
from house.client import SPARK, WONDER, Call, load_schema

ROOT = Path(__file__).resolve().parent.parent


def chunk(work, chars: int = 1000):
    out, n = [], 0
    for p in work.translatable():
        out.append(p)
        n += len(p.text)
        if n >= chars:
            break
    return out


def calls(work) -> list[tuple[str, Call]]:
    wid = work.meta["work_id"]
    paras = chunk(work)
    stable = context.join(context.work_card(work), context.source_text(work))
    after = next((p for p in work.translatable() if p.seq == paras[-1].seq + 1), None)
    draft_input = context.join(stable, context.window([], after), context.page(paras, None, False))
    key = f"{wid}:calibrate"
    return [
        ("Spark draft, low", Call("translate-draft", SPARK, "low", draft_input, load_schema("translate-draft"), key, stage="calibrate")),
        ("Spark draft, medium", Call("translate-draft", SPARK, "medium", draft_input, load_schema("translate-draft"), key, stage="calibrate")),
        ("Spark + web search, low", Call("background-brief", SPARK, "low", stable, load_schema("background-brief"), key, web_search=True, stage="calibrate")),
        ("Wonder crux check, low", Call("crux-check", WONDER, "low", stable, load_schema("crux-check"), f"{wid}:calibrate:wonder", stage="calibrate")),
    ]


def run(client, work) -> list[dict]:
    rows = []
    paras = chunk(work)
    chars = sum(len(p.text) for p in paras)
    for label, call in calls(work):
        res = client.call(call)
        u = res.usage
        visible = u.output_tokens - u.reasoning_tokens
        rows.append({
            "label": label, "model": res.model, "effort": res.effort,
            "input": u.input_tokens, "cached": u.cached_tokens, "output": u.output_tokens,
            "reasoning": u.reasoning_tokens, "visible": visible,
            "reasoning_per_visible": round(u.reasoning_tokens / visible, 2) if visible else None,
            "web_searches": u.web_searches, "usd": round(res.list_cost_usd, 5),
            "latency_s": res.latency_s, "from_cache": res.from_cache, "chunk_chars": chars,
            "chunk": f"{paras[0].id}–{paras[-1].id}", "data": res.data,
        })
    out = ROOT / "var" / "calibration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def table(rows: list[dict]) -> str:
    head = "| Call | Input | Cached | Output | of which reasoning | Reasoning ÷ visible | Searches | $ | s |\n|---|---|---|---|---|---|---|---|---|"
    lines = [head]
    for r in rows:
        lines.append(f"| {r['label']} | {r['input']:,} | {r['cached']:,} | {r['output']:,} | {r['reasoning']:,} |"
                     f" {r['reasoning_per_visible']} | {r['web_searches']} | {r['usd']:.4f} | {r['latency_s']} |")
    return "\n".join(lines)
