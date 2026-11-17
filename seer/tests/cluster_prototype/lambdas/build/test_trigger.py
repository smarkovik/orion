"""Checks of the build handler's wrapper (python -m pytest in the build image; build_one is stubbed)."""

import json

import handler
import pytest


class Ctx:
    function_name = "seer-build"

    def __init__(self, left_s):
        self.left_s = left_s

    def get_remaining_time_in_millis(self):
        return int(self.left_s * 1000)


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kw):
        self.calls.append(kw)


@pytest.fixture
def fake(monkeypatch):
    lam = FakeLambda()
    monkeypatch.setattr(handler.boto3, "client", lambda name: lam)
    monkeypatch.setattr(handler, "build_one", lambda key, event, ctx: {"manifest": key})
    return lam


def test_s3_event_builds_one_manifest_and_returns_its_result(fake):
    event = {"Records": [{"s3": {"object": {"key": "runs/mk/a.json"}}}]}
    assert handler.handler(event, Ctx(900)) == {"manifest": "runs/mk/a.json"}
    assert fake.calls == []


def test_all_manifests_build_in_one_invocation(fake):
    out = handler.handler({"manifest_keys": ["runs/mk/a.json", "runs/fr/b.json"]}, Ctx(900))
    assert out == {"builds": [{"manifest": "runs/mk/a.json"}, {"manifest": "runs/fr/b.json"}]}
    assert fake.calls == []


def test_rest_goes_to_a_new_invocation_when_time_is_short(fake):
    out = handler.handler({"manifest_keys": ["runs/mk/a.json", "runs/fr/b.json", "runs/xx/c.json"]}, Ctx(100))
    assert out["builds"][-1] == {"deferred": ["runs/fr/b.json", "runs/xx/c.json"]}
    assert len(fake.calls) == 1 and fake.calls[0]["InvocationType"] == "Event"
    assert fake.calls[0]["FunctionName"] == "seer-build"
    assert json.loads(fake.calls[0]["Payload"]) == {"manifest_keys": ["runs/fr/b.json", "runs/xx/c.json"]}


def test_a_failing_manifest_does_not_stop_the_next_and_is_raised(fake, monkeypatch):
    def build_one(key, event, ctx):
        if "mk" in key:
            raise RuntimeError("boom")
        return {"manifest": key}

    seen = []
    monkeypatch.setattr(handler, "build_one", lambda key, event, ctx: seen.append(key) or build_one(key, event, ctx))
    with pytest.raises(RuntimeError):
        handler.handler({"manifest_keys": ["runs/mk/a.json", "runs/fr/b.json"]}, Ctx(900))
    assert seen == ["runs/mk/a.json", "runs/fr/b.json"]
