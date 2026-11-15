"""Offline checks for the control Lambda: python -m pytest lambdas/control (no AWS, boto3 is stubbed)."""

# flake8: noqa: E501

import hashlib
import json
import os
import sys
import time
import types

import pytest

TOKEN = "test-token"
os.environ.update(
    SCRAPE_FUNCTION="seer-scrape",
    EDITIONS="mk,fr",
    SCRAPE_LOG_GROUP="/aws/lambda/scrape",
    BUILD_LOG_GROUP="/aws/lambda/build",
    TOKEN_SHA256=hashlib.sha256(TOKEN.encode()).hexdigest(),
    COOLDOWN_SECONDS="900",
    MAX_STARTS_PER_DAY="4",
)


class NotFound(Exception):
    pass


class FakeLogs:
    exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)

    def __init__(self):
        self.events = {}

    def filter_log_events(self, logGroupName, startTime, endTime, filterPattern, nextToken=None):
        evs = [e for e in self.events.get(logGroupName, []) if startTime <= e["timestamp"] <= endTime]
        if filterPattern == '"START RequestId"':
            evs = [e for e in evs if e["message"].startswith("START")]
        return {"events": evs}


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kw):
        self.calls.append(kw)


sys.modules["boto3"] = types.SimpleNamespace(client=lambda name: FakeLogs() if name == "logs" else FakeLambda())
sys.path.insert(0, os.path.dirname(__file__))
import handler  # noqa: E402


@pytest.fixture(autouse=True)
def fresh():
    handler.logs, handler.lam, handler._last_sync = FakeLogs(), FakeLambda(), 0.0


def ev(ts, msg, stream="s1"):
    return {"timestamp": int(ts * 1000), "message": msg, "logStreamName": stream}


def call(method, path, token=TOKEN, query=None):
    return handler.handler(
        {
            "requestContext": {"http": {"method": method}},
            "rawPath": path,
            "headers": {"x-seer-token": token},
            "queryStringParameters": query,
        },
        None,
    )


def test_rejects_wrong_token():
    assert call("POST", "/system/control/sync", token="nope")["statusCode"] == 401
    assert call("GET", "/system/control/cost", token="")["statusCode"] == 401


def test_cost_parses_ok_error_and_timeout():
    t = time.time() - 600
    handler.logs.events["/aws/lambda/build"] = [
        ev(t, "START RequestId: a Version: $LATEST\n"),
        ev(t + 1, "[INFO]\t2026\ta\tbuild 20261115T183156Z-fr: {'edition': 'fr'}"),
        ev(t + 2, "END RequestId: a\n"),
        ev(
            t + 2,
            "REPORT RequestId: a\tDuration: 1000.00 ms\tBilled Duration: 1000 ms\tMemory Size: 3008 MB\tMax Memory Used: 700 MB\tInit Duration: 5.00 ms\t\n",
        ),
        ev(t + 10, "START RequestId: b Version: $LATEST\n"),
        ev(t + 11, "[ERROR] FileNotFoundError: boom\nTraceback..."),
        ev(
            t + 12,
            "REPORT RequestId: b\tDuration: 2000.00 ms\tBilled Duration: 2000 ms\tMemory Size: 3008 MB\tMax Memory Used: 700 MB\t\n",
        ),
        ev(t + 20, "START RequestId: c Version: $LATEST\n"),
        ev(
            t + 500,
            "REPORT RequestId: c\tDuration: 900000.00 ms\tBilled Duration: 900000 ms\tMemory Size: 3008 MB\tMax Memory Used: 2999 MB\tStatus: timeout\n",
        ),
    ]
    handler.logs.events["/aws/lambda/scrape"] = [
        ev(t, "START RequestId: d Version: $LATEST\n", "s2"),
        ev(t + 1, "[ERROR]\t2026\td\tlefigaro.fr: failed: HTTPStatusError", "s2"),
        ev(t + 1, "[INFO]\t2026\td\tTOTAL: edition=mk sources=10 records=5", "s2"),
        ev(
            t + 2,
            "REPORT RequestId: d\tDuration: 8000.00 ms\tBilled Duration: 9000 ms\tMemory Size: 512 MB\tMax Memory Used: 170 MB\t\n",
            "s2",
        ),
    ]
    body = json.loads(call("GET", "/system/control/cost", query={"days": "1"})["body"])
    by = {i["request_id"]: i for i in body["invocations"]}
    assert (by["a"]["status"], by["a"]["edition"], by["a"]["run_id"]) == ("ok", "fr", "20261115T183156Z-fr")
    assert (by["b"]["status"], by["c"]["status"], by["d"]["edition"]) == ("error", "timeout", "mk")
    assert by["b"]["error"].startswith("[ERROR] FileNotFoundError")
    assert by["d"]["status"] == "ok"  # a logged outlet error is not a failed invocation
    gb_s = 1.0 * 3008 / 1024
    assert by["a"]["usd"] == pytest.approx(gb_s * handler.PRICE_GB_S + handler.PRICE_REQUEST)
    assert body["by_function"]["build"]["failed"] == 2
    assert body["failed_usd"] == pytest.approx(by["b"]["usd"] + by["c"]["usd"])
    assert body["total_usd"] == pytest.approx(sum(i["usd"] for i in body["invocations"]))
    assert body["sync"]["scrape_starts_24h"] == 1


def test_sync_starts_every_edition_then_cools_down():
    r = call("POST", "/system/control/sync")
    assert r["statusCode"] == 202
    assert [json.loads(c["Payload"])["edition"] for c in handler.lam.calls] == ["mk", "fr"]
    assert all(c["InvocationType"] == "Event" for c in handler.lam.calls)
    again = call("POST", "/system/control/sync")
    assert again["statusCode"] == 429 and json.loads(again["body"])["error"] == "cooldown"
    assert len(handler.lam.calls) == 2


def test_sync_respects_scrape_started_elsewhere_and_daily_limit():
    now = time.time()
    handler.logs.events["/aws/lambda/scrape"] = [ev(now - 60, "START RequestId: x Version: $LATEST\n")]
    assert json.loads(call("POST", "/system/control/sync")["body"])["error"] == "cooldown"
    handler.logs.events["/aws/lambda/scrape"] = [
        ev(now - 3600 * (i + 1), f"START RequestId: {i} Version: $LATEST\n") for i in range(4)
    ]
    assert json.loads(call("POST", "/system/control/sync")["body"])["error"] == "daily_limit"
    assert handler.lam.calls == []
