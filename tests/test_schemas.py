import json

import jsonschema
import pytest

from house import client as cl

SCHEMAS = sorted(cl.SCHEMAS.glob("*.json"))


def depth(node, d=0):
    if isinstance(node, dict):
        return max([d] + [depth(v, d + 1) for v in node.values()])
    if isinstance(node, list):
        return max([d] + [depth(v, d) for v in node])
    return d


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.stem)
def test_schema_is_valid_and_strict_ready(path):
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    s = cl.strict(schema)
    assert s["type"] == "object" and s["additionalProperties"] is False
    assert "say" in s["properties"], "every output has a say line for the House"
    assert (cl.PROMPTS / f"{path.stem}.md").exists(), "each schema belongs to a prompt"
    # Meta's strict mode: object nesting at most 10 deep (each level is properties + the object)
    assert depth(s) <= 21


def test_every_pipeline_prompt_has_a_schema():
    for name in ["parts", "first-read", "crux-check", "head-select", "analyst-bible", "translate-draft",
                 "reader-faithful", "reader-readable", "desk", "final-read", "notes"]:
        assert (cl.SCHEMAS / f"{name}.json").exists(), name
