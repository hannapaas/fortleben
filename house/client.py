"""One model client for the whole house.

Every call goes to a Meta model on the Meta Model API's Responses API. The instructions are
always the house brief followed by one department prompt from prompts/; nothing in house/
contains prompt text. Output is strict JSON against the prompt's schema in house/schemas/.

Each call is priced from `usage` into the spend ledger (the `call` table). Responses are kept
in a cache keyed on (model, effort, prompt hash, input hash, schema hash, tools), so a rerun or
a replay costs nothing. FakeClient serves the same cache from fixtures/ and never needs a key.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import jsonschema

from house import budget
from house.budget import Usage

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
SCHEMAS = Path(__file__).resolve().parent / "schemas"
CACHE = ROOT / "var" / "cache" / "responses"
FIXTURES = ROOT / "fixtures"
BASE_URL = "https://api.meta.ai/v1"

SPARK = "muse-spark-1.3"
WONDER = "muse-wonder-1.0"


class SchemaError(Exception):
    """The model's output didn't validate, twice."""


class FixtureMissing(Exception):
    """FakeClient has no recorded response for this call."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def instructions(prompt: str) -> str:
    """The house brief, then the department prompt. Both are files; neither is edited here."""
    brief = (PROMPTS / "house-brief.md").read_text(encoding="utf-8")
    if prompt == "house-brief":
        return brief
    return brief + "\n\n---\n\n" + (PROMPTS / f"{prompt}.md").read_text(encoding="utf-8")


def load_schema(prompt: str) -> dict | None:
    path = SCHEMAS / f"{prompt}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def strict(schema: dict) -> dict:
    """Make a schema acceptable to strict mode: every object closed and every key required.
    Optional fields are written as nullable types in the schema files."""
    schema = json.loads(json.dumps(schema))

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                props = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(props)
            for key in ("properties", "$defs", "definitions"):
                for child in node.get(key, {}).values():
                    walk(child)
            for key in ("items", "anyOf"):
                child = node.get(key)
                if isinstance(child, list):
                    for c in child:
                        walk(c)
                elif child is not None:
                    walk(child)

    walk(schema)
    return schema


@dataclass
class Result:
    data: object  # parsed JSON, or text when the prompt has no schema
    model: str
    effort: str
    usage: Usage
    cost_usd: float  # what this call cost now; 0 from the cache
    list_cost_usd: float  # what it cost when first made
    from_cache: bool
    response_key: str
    call_id: int | None = None
    response_id: str | None = None
    latency_s: float | None = None
    citations: list = field(default_factory=list)


@dataclass
class Call:
    """Everything that defines one model call."""

    prompt: str  # file name in prompts/, without .md
    model: str
    effort: str
    input: str  # the assembled input, stable blocks first, the passage last
    schema: dict | None = None
    cache_key: str | None = None  # prompt_cache_key: one per work + style-sheet version
    web_search: bool = False
    expected_output_tokens: int = 4000
    max_output_tokens: int = 32000
    run_id: int | None = None
    stage: str | None = None

    def instructions(self) -> str:
        return instructions(self.prompt)

    def response_key(self) -> str:
        parts = {
            "model": self.model,
            "effort": self.effort,
            "prompt": sha(self.instructions()),
            "input": sha(self.input),
            "schema": sha(json.dumps(self.schema, sort_keys=True)) if self.schema else None,
            "web_search": self.web_search,
        }
        return sha(json.dumps(parts, sort_keys=True))


class BaseClient:
    """Shared by the live client and FakeClient: cache lookup, ledger rows, validation."""

    def __init__(self, conn: sqlite3.Connection, cache_dirs: list[Path] | None = None, run_cap=None):
        self.conn = conn
        self.cache_dirs = cache_dirs if cache_dirs is not None else [CACHE, *sorted(FIXTURES.glob("*/responses"))]
        self.budget = budget.Budget(conn, run_cap)

    def lookup(self, key: str) -> dict | None:
        for d in self.cache_dirs:
            path = d / f"{key}.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def store(self, key: str, record: dict) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    def ledger(self, call: Call, res: Result, ok=True, error=None) -> int:
        u = res.usage
        cur = self.conn.execute(
            """INSERT INTO call (run_id, stage, prompt, model, effort, input_tokens, cached_tokens,
               output_tokens, reasoning_tokens, web_searches, cost_usd, list_cost_usd, from_cache,
               prompt_hash, input_hash, cache_key, response_key, response_id, latency_s, ok, error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (call.run_id, call.stage, call.prompt, call.model, call.effort, u.input_tokens,
             u.cached_tokens, u.output_tokens, u.reasoning_tokens, u.web_searches, res.cost_usd,
             res.list_cost_usd, int(res.from_cache), sha(call.instructions()), sha(call.input),
             call.cache_key, res.response_key, res.response_id, res.latency_s, int(ok), error),
        )
        self.conn.commit()
        return cur.lastrowid

    def from_record(self, record: dict, key: str) -> Result:
        return Result(
            data=record["data"], model=record["model"], effort=record["effort"],
            usage=Usage(**record["usage"]), cost_usd=0.0, list_cost_usd=record["list_cost_usd"],
            from_cache=True, response_key=key, response_id=record.get("response_id"),
            latency_s=record.get("latency_s"), citations=record.get("citations", []),
        )

    def call(self, call: Call) -> Result:
        key = call.response_key()
        record = self.lookup(key)
        if record is not None:
            res = self.from_record(record, key)
        else:
            res = self.live(call, key)
        res.call_id = self.ledger(call, res)
        return res

    def live(self, call: Call, key: str) -> Result:
        raise NotImplementedError


class FakeClient(BaseClient):
    """Serves recorded responses from fixtures/ (and the local cache). Never needs a key."""

    def live(self, call: Call, key: str) -> Result:
        raise FixtureMissing(f"no recorded response for {call.prompt} ({call.model}, key {key[:12]})")


class ModelClient(BaseClient):
    """The live client: Meta Model API, Responses API."""

    def __init__(self, conn, cache_dirs=None, run_cap=None, api_key=None, base_url=None):
        super().__init__(conn, cache_dirs, run_cap)
        from openai import OpenAI

        self.api = OpenAI(
            api_key=api_key or os.environ["MODEL_API_KEY"],
            base_url=base_url or os.environ.get("MODEL_API_BASE") or BASE_URL,
            timeout=900,
            max_retries=4,  # 429 and 5xx, with backoff (the SDK honours Retry-After)
        )

    def request(self, call: Call) -> dict:
        req = {
            "model": call.model,
            "instructions": call.instructions(),
            "input": call.input,
            "reasoning": {"effort": call.effort},
            "max_output_tokens": call.max_output_tokens,
            "store": False,
        }
        if call.cache_key:
            req["prompt_cache_key"] = call.cache_key
            req["prompt_cache_retention"] = "24h"
        if call.schema:
            # strict: False on purpose. With strict: True, Meta's API serves no prompt-cache hits
            # (measured 1 Nov); non-strict output still follows the schema, and parse() validates it.
            req["text"] = {"format": {"type": "json_schema", "name": call.prompt.replace("-", "_"),
                                      "schema": strict(call.schema), "strict": False}}
        if call.web_search:
            req["tools"] = [{"type": "web_search"}]
        return req

    def live(self, call: Call, key: str) -> Result:
        est = budget.estimate(call.model, len(call.instructions()) + len(call.input), call.expected_output_tokens)
        last_error = None
        for attempt in range(2):  # a schema failure is retried once (docs/STAGES.md)
            self.budget.check(est, call.run_id)
            t0 = time.monotonic()
            resp = self.api.responses.create(**self.request(call))
            latency = time.monotonic() - t0
            usage = self.usage(resp)
            text, citations = self.output(resp)
            cost = usage.cost(call.model)
            res = Result(data=None, model=call.model, effort=call.effort, usage=usage,
                         cost_usd=cost, list_cost_usd=cost, from_cache=False, response_key=key,
                         response_id=resp.id, latency_s=round(latency, 2), citations=citations)
            try:
                if resp.status != "completed":
                    raise SchemaError(f"response {resp.status}: {resp.incomplete_details}")
                res.data = self.parse(text, call.schema)
            except (SchemaError, json.JSONDecodeError, jsonschema.ValidationError) as e:
                last_error = f"{type(e).__name__}: {str(e)[:500]}"
                self.ledger(call, res, ok=False, error=last_error)
                continue
            self.store(key, {
                "prompt": call.prompt, "model": call.model, "effort": call.effort,
                "data": res.data, "usage": asdict(usage), "list_cost_usd": cost,
                "response_id": resp.id, "latency_s": res.latency_s, "citations": citations,
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            return res
        raise SchemaError(f"{call.prompt}: output failed twice; last error {last_error}")

    @staticmethod
    def parse(text: str, schema: dict | None):
        if schema is None:
            return text
        data = json.loads(text)
        jsonschema.validate(data, strict(schema))  # every key present, nothing extra
        return data

    @staticmethod
    def usage(resp) -> Usage:
        u = resp.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
        searches = sum(1 for item in resp.output if item.type == "web_search_call")
        return Usage(u.input_tokens, cached, u.output_tokens, reasoning, searches)

    @staticmethod
    def output(resp) -> tuple[str, list]:
        """The final answer. With tools on, Meta also sends 'commentary' messages between
        searches; those are skipped, and their citations kept."""
        final, citations = "", []
        for item in resp.output:
            if item.type != "message":
                continue
            texts = []
            for part in item.content or []:
                if part.type == "output_text":
                    texts.append(part.text)
                    for a in part.annotations or []:
                        if getattr(a, "type", None) == "url_citation":
                            citations.append({"url": a.url, "title": getattr(a, "title", None)})
            if getattr(item, "phase", None) != "commentary":
                final = "".join(texts)
        return final, citations


def make_client(conn, replay: bool = False, run_cap=None) -> BaseClient:
    """The live client when there's a key and replay isn't asked for; FakeClient otherwise."""
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    if replay or not os.environ.get("MODEL_API_KEY"):
        return FakeClient(conn, run_cap=run_cap)
    return ModelClient(conn, run_cap=run_cap)
