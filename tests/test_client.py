import json
from types import SimpleNamespace

import pytest

from house import client as cl
from house.budget import CapExceeded, Usage
from house.db import connect

SCHEMA = {"type": "object", "properties": {"say": {"type": "string"}}}


class LyingAPI:
    """Returns valid output but reports whatever usage it's told to."""

    def __init__(self, usage: Usage, text='{"say": "Nothing to change here."}'):
        self.u, self.text, self.calls = usage, text, 0
        self.responses = self

    def create(self, **req):
        self.calls += 1
        u = self.u
        return SimpleNamespace(
            id=f"resp_{self.calls}", status="completed", incomplete_details=None,
            usage=SimpleNamespace(
                input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                input_tokens_details=SimpleNamespace(cached_tokens=u.cached_tokens),
                output_tokens_details=SimpleNamespace(reasoning_tokens=u.reasoning_tokens)),
            output=[SimpleNamespace(type="message", content=[
                SimpleNamespace(type="output_text", text=self.text, annotations=[])])],
        )


def live_client(tmp_path, monkeypatch, usage, run_cap=1.0, text='{"say": "Nothing to change here."}'):
    conn = connect(":memory:")
    c = cl.ModelClient.__new__(cl.ModelClient)
    cl.BaseClient.__init__(c, conn, cache_dirs=[cl.cache_dir()], run_cap=run_cap)
    c.api = LyingAPI(usage, text)
    return c


def make_call(text="p1 晩餐", run_id=1):
    return cl.Call(prompt="crux-check", model=cl.SPARK, effort="low", input=text,
                   schema=SCHEMA, run_id=run_id, expected_output_tokens=100)


def test_cost_is_priced_from_usage():
    u = Usage(input_tokens=10_000, cached_tokens=8_000, output_tokens=2_000)
    assert u.cost(cl.SPARK) == pytest.approx((2_000 * 1.25 + 8_000 * 0.15 + 2_000 * 4.25) / 1e6)


def test_second_identical_call_is_free(tmp_path, monkeypatch):
    c = live_client(tmp_path, monkeypatch, Usage(1000, 0, 500, 400))
    a = c.call(make_call())
    b = c.call(make_call())
    assert c.api.calls == 1
    assert a.cost_usd > 0 and b.cost_usd == 0 and b.from_cache
    assert b.data == {"say": "Nothing to change here."}
    rows = c.conn.execute("SELECT from_cache, cost_usd FROM call ORDER BY id").fetchall()
    assert [r["from_cache"] for r in rows] == [0, 1]


def test_run_cap_stops_a_client_that_lies_about_usage(tmp_path, monkeypatch):
    # Each call reports $0.85 of output against a $1 run cap. The check runs before a call,
    # so one call can overshoot; the next is refused.
    c = live_client(tmp_path, monkeypatch, Usage(0, 0, 200_000, 0))
    c.call(make_call("one"))
    c.call(make_call("two"))
    with pytest.raises(CapExceeded):
        c.call(make_call("three"))


def test_invalid_output_is_retried_once_then_fails(tmp_path, monkeypatch):
    c = live_client(tmp_path, monkeypatch, Usage(10, 0, 10, 0), text='{"say": 3}')
    with pytest.raises(cl.SchemaError):
        c.call(make_call())
    assert c.api.calls == 2


def test_fake_client_serves_recorded_responses(tmp_path, monkeypatch):
    live = live_client(tmp_path, monkeypatch, Usage(10, 0, 10, 0))
    live.call(make_call())
    fake = cl.FakeClient(connect(":memory:"), cache_dirs=[cl.cache_dir()])
    assert fake.call(make_call()).data == {"say": "Nothing to change here."}
    with pytest.raises(cl.FixtureMissing):
        fake.call(make_call("something never recorded"))


def test_prompts_are_files_not_code():
    text = cl.instructions("first-read")
    assert text.startswith("# The house brief")
    assert "# First read" in text


def test_strict_closes_every_object():
    s = cl.strict({"type": "object", "properties": {"a": {"type": "array", "items": {
        "type": "object", "properties": {"b": {"type": "string"}}}}}})
    assert s["additionalProperties"] is False and s["required"] == ["a"]
    inner = s["properties"]["a"]["items"]
    assert inner["additionalProperties"] is False and inner["required"] == ["b"]
    json.dumps(s)


def test_a_valid_answer_whose_log_sentence_is_junk_counts_as_broken():
    from house.client import looks_broken
    schema = {"type": "object", "properties": {"fixes": {"type": "array"}, "say": {"type": "string"}}}
    assert looks_broken({"fixes": [], "say": "safdsdfkjjhjk"}, schema)
    assert looks_broken({"fixes": [], "say": "׳"}, schema)
    assert not looks_broken({"fixes": [], "say": "A clean chapter; nothing to change."}, schema)
    assert not looks_broken({"fixes": [], "say": None}, schema)
    assert not looks_broken({"fixes": [], "say": "None."}, schema)
    assert not looks_broken({"fixes": [], "say": "Strengths and rhythms intact."}, schema)
    assert not looks_broken("plain text", None)
