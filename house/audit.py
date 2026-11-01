"""The blind audit behind the exhibit (docs/BUILD-PLAN.md, "The exhibit"). Each version of a text,
the house's runs and the one-shot baseline alike, goes to the same audit call with the same
reading and bible, as plain paragraphs with no labels or IDs, so the auditor can't tell which is
which. The one-shot baseline is Spark given the bare prompt and the Japanese, nothing else."""

import json
from pathlib import Path
from types import SimpleNamespace

from house import checks, context
from house.client import SPARK, WONDER, Call, load_schema
from house.stages import Ctx
from house.stages.common import latest_units

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "var" / "audit"


def baseline(client, work) -> str:
    text = "\n".join(p.text.strip("　 ") for p in work.translatable())
    return client.call(Call("baseline-oneshot", SPARK, "medium", text, None, f"{work.meta['work_id']}:baseline",
                            stage="audit")).data


def run_english(conn, run_id: int) -> str:
    """A run's English as the Casual view renders it, one paragraph per line, grouped units once."""
    work_id = conn.execute("SELECT work_id FROM run WHERE id=?", (run_id,)).fetchone()[0]
    t = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM term WHERE work_id=?", (work_id,))}
    units = sorted(latest_units(SimpleNamespace(conn=conn, run_id=run_id)).items(), key=lambda kv: int(kv[0][0][1:]))
    return "\n\n".join(checks.render(en, t, "casual") for _, en in units)


def audit(client, conn, work, label: str, english: str) -> dict:
    ctx = Ctx(conn, client, work, None)
    inp = context.join(
        context.reading(ctx.latest("reading")), context.bible(ctx.latest("bible")),
        context.block("The passage in Japanese", "\n".join(p.text.strip("　 ") for p in work.translatable())),
        context.block("One English version", english),
    )
    res = client.call(Call("audit-spans", WONDER, "medium", inp, load_schema("audit-spans"),
                           f"{work.meta['work_id']}:audit", expected_output_tokens=4000, strict=True, stage="audit"))
    OUT.mkdir(parents=True, exist_ok=True)
    record = {"label": label, "english": english, "audit": res.data, "usd": res.list_cost_usd}
    (OUT / f"{work.meta['work_id']}-{label}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def summary(record: dict) -> dict:
    notes = record["audit"]["notes"]
    by = lambda key: {v: sum(1 for n in notes if n[key] == v) for v in sorted({n[key] for n in notes})}  # noqa: E731
    return {"label": record["label"], "notes": len(notes), "severity": by("severity"), "kinds": by("kind"),
            "overall": record["audit"]["overall"], "usd": round(record["usd"], 4)}
