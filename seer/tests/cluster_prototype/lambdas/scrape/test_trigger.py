"""Checks of the scrape handler's wrapper (python -m pytest in the scrape image; scrape_edition is stubbed)."""

import json

import handler
import pytest


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kw):
        self.calls.append(kw)


@pytest.fixture
def fake(monkeypatch):
    lam = FakeLambda()
    monkeypatch.setattr(handler.boto3, "client", lambda name: lam)
    monkeypatch.setenv("BUILD_FUNCTION", "seer-build")
    monkeypatch.setattr(
        handler, "scrape_edition", lambda ed, event, ctx: {"edition": ed, "manifest_key": f"runs/{ed}/x.json"}
    )
    return lam


def test_two_editions_start_one_build(fake):
    out = handler.handler({"editions": ["mk", "fr"]}, None)
    assert out["build_started"] and out["failed"] == 0 and len(out["scrapes"]) == 2
    assert len(fake.calls) == 1 and fake.calls[0]["FunctionName"] == "seer-build"
    assert json.loads(fake.calls[0]["Payload"]) == {"manifest_keys": ["runs/mk/x.json", "runs/fr/x.json"]}


def test_single_edition_keeps_the_old_result_shape(fake):
    assert handler.handler({"edition": "mk"}, None) == {"edition": "mk", "manifest_key": "runs/mk/x.json"}


def test_no_build_is_started_without_build_function(fake, monkeypatch):
    monkeypatch.delenv("BUILD_FUNCTION")
    handler.handler({"editions": ["mk", "fr"]}, None)
    assert fake.calls == []


def test_one_failing_edition_does_not_stop_the_other(fake, monkeypatch):
    def scrape_edition(ed, event, ctx):
        if ed == "fr":
            raise RuntimeError("every source failed")
        return {"edition": ed, "manifest_key": f"runs/{ed}/x.json"}

    monkeypatch.setattr(handler, "scrape_edition", scrape_edition)
    out = handler.handler({"editions": ["fr", "mk"]}, None)
    assert out["failed"] == 1 and json.loads(fake.calls[0]["Payload"]) == {"manifest_keys": ["runs/mk/x.json"]}


def test_every_edition_failing_raises(fake, monkeypatch):
    monkeypatch.setattr(handler, "scrape_edition", lambda ed, event, ctx: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        handler.handler({"editions": ["mk", "fr"]}, None)
    assert fake.calls == []
