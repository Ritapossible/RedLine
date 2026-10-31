"""The server end to end, offline: the PayPal stand-in behind the real
RestPayPal client, the stand-in panel, and a clock the tests move.

Every demo terms version is run through a whole cover and settled; the
money must always add up: captured + released == held.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from redline_paypal.config import App
from redline_paypal.core import core
from redline_paypal.covers import CoverError
from redline_paypal.offline import FakeSandbox
from redline_paypal.paypal_api import RestPayPal
from redline_paypal.web import create_app

T0 = 1_800_000_000


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


def make(clock=None, sandbox=None, models=None):
    clock = clock or Clock()
    sandbox = sandbox or FakeSandbox(clock=clock)
    paypal = RestPayPal("id", "secret", transport=httpx.MockTransport(sandbox), sleep=lambda s: None)
    app = App({"REDLINE_OFFLINE": "1", "REDLINE_DB": ":memory:"}, clock=clock, paypal=paypal, models=models)
    return app, clock, sandbox


def suggested(app, vendor, ids=("refund", "deletion")):
    return [{"id": s["id"], "text": s["text"], "label": s["label"]}
            for s in app.vendors.suggestions(vendor["token"], app.read_page) if s["id"] in ids]


def opened(app, clock):
    v = app.vendors.create_demo()
    c = app.covers.start_checkout(v, suggested(app, v))
    c = app.covers.pay_with_test_card(c["token"], app.card)
    assert c["state"] == core.COVER_ACTIVE
    return v, c["token"]


def run_out(app, clock, token, step=None, until=None):
    """Tick the clock in check gaps until the cover is settled."""
    step = step or app.covers.load(token)["extra"]["gap_seconds"]
    for _ in range(40):
        clock.t += step
        app.covers.tick()
        c = app.covers.load(token)
        if c["extra"].get("settlement"):
            return c
    raise AssertionError("the cover never settled")


def money_adds_up(app, sandbox, c):
    s = c["extra"]["settlement"]
    assert s["vendorCents"] + s["releasedCents"] == c["amount_cents"]
    auth = sandbox.auths[c["authorizations"][-1]["id"]]
    assert auth["captured"] == s["vendorCents"]
    assert auth["status"] == ("CAPTURED" if s["releasedCents"] == 0 else "VOIDED")
    return s


@pytest.mark.parametrize("version", ["original", "rebuilt"])
def test_unchanged_terms_are_kept_by_code(version):
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], version)
    c = run_out(app, clock, token)
    assert c["state"] == core.COVER_COMPLETED
    s = money_adds_up(app, sandbox, c)
    assert (s["vendorCents"], s["releasedCents"], s["reason"]) == (2000, 0, "held")
    view = app.covers.view(c)
    assert view["checks"] and all(ch["decidedBy"] == "code" and ch["kind"] == "kept" for ch in view["checks"])
    assert view["paypal"]["capture"]["amountCents"] == 2000 and "void" not in view["paypal"]


def test_reworded_is_read_by_the_panel_and_kept():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "reworded")
    c = run_out(app, clock, token)
    assert c["state"] == core.COVER_COMPLETED
    assert money_adds_up(app, sandbox, c)["vendorCents"] == 2000
    panel = [ch for ch in app.covers.view(c)["checks"] if ch["decidedBy"] == "panel"]
    assert panel and all(ch["reading"] == "same" and ch["kind"] == "kept" for ch in panel)


@pytest.mark.parametrize("version,passage", [
    ("narrowed", "refund"), ("injected", "refund"), ("voided", "refund"), ("hidden", "refund"),
    ("hidden-style", "refund"), ("deletion-removed", "deletion")])
def test_a_cut_is_suspected_confirmed_and_settled_as_of_the_first_check(version, passage):
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    clock.t += 120
    app.covers.tick()  # a kept check: the vendor accrues 2 minutes of 10
    app.vendors.set_version(v["token"], version)
    clock.t += 60
    app.covers.tick()  # suspected
    view = app.covers.view(app.covers.load(token))
    first = view["checks"][-1]
    assert first["kind"] == "breach" and first["suspected"] and view["state"] == "active"
    assert {p["id"]: p["status"] for p in view["passages"]}[passage] == "suspected"
    assert view["earnedCents"] == 2000 * 180 // 600  # frozen at the suspected check
    clock.t += 60
    app.covers.tick()  # confirmed
    c = app.covers.load(token)
    assert c["state"] == core.COVER_BREACHED
    s = money_adds_up(app, sandbox, c)
    assert s["asOf"] == first["at"] and s["reason"] == "cut"
    assert (s["vendorCents"], s["releasedCents"]) == (600, 1400)
    view = app.covers.view(c)
    assert view["checks"][-1]["confirms"] == first["seq"]
    assert {p["id"]: p["status"] for p in view["passages"]}[passage] == "cut"
    assert view["paypal"]["capture"]["amountCents"] == 600 and view["paypal"]["void"]["status"] == "VOIDED"


def test_a_suspected_cut_not_confirmed_is_dropped():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    clock.t += 60
    app.covers.tick()
    app.vendors.set_version(v["token"], "original")
    clock.t += 60
    app.covers.tick()
    view = app.covers.view(app.covers.load(token))
    assert view["state"] == "active" and view["checks"][-1]["kind"] == "kept"
    assert "Not confirmed" in view["checks"][-1]["note"]
    assert all(p["status"] == "holding" for p in view["passages"])
    c = run_out(app, clock, token)
    assert money_adds_up(app, sandbox, c)["vendorCents"] == 2000


def test_a_page_taken_down_is_gone_after_three_checks():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    clock.t += 60
    app.covers.tick()
    app.vendors.set_version(v["token"], "down")
    down_at = clock.t + 60
    c = run_out(app, clock, token)
    assert c["state"] == core.COVER_BREACHED
    s = money_adds_up(app, sandbox, c)
    assert s["reason"] == "gone" and s["asOf"] == down_at
    kinds = [ch["kind"] for ch in app.covers.view(c)["checks"]]
    assert kinds[-3:] == ["absent", "absent", "gone"]


def test_a_cut_suspected_at_the_last_check_is_still_confirmed():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    clock.t += 540
    app.covers.tick()
    app.vendors.set_version(v["token"], "narrowed")
    clock.t += 59
    app.covers.check_now(token)  # suspected, a second before the end
    clock.t += 30  # past the end
    app.covers.tick()
    c = app.covers.load(token)
    assert c["state"] == core.COVER_BREACHED
    assert money_adds_up(app, sandbox, c)["vendorCents"] == 2000 * 599 // 600


def test_check_now_is_rate_limited():
    app, clock, _ = make()
    v, token = opened(app, clock)
    clock.t += 5
    app.covers.check_now(token)
    clock.t += 1
    with pytest.raises(CoverError) as e:
        app.covers.check_now(token)
    assert e.value.status == 429


def test_pins_must_be_on_the_page_word_for_word():
    app, clock, _ = make()
    v = app.vendors.create_demo()
    problems = app.covers.pin_problems(v, [{"id": "own", "text": "We refund everything forever, whatever happens, always."}])
    assert problems and "word for word" in problems[0]["message"]
    assert app.covers.pin_problems(v, [{"id": "a", "text": "too short"}])
    with pytest.raises(CoverError):
        app.covers.start_checkout(v, [{"id": "own", "text": "We refund everything forever, whatever happens, always."}])


def test_settlement_is_journaled_and_never_sent_twice():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    clock.t += 60
    app.covers.tick()
    real_void = sandbox.route

    def flaky(method, path, body):  # the void fails (twice: one tick tries twice), after the capture went through
        if path.endswith("/void") and flaky.failures < 2:
            flaky.failures += 1
            return httpx.Response(500, json={"name": "INTERNAL_SERVER_ERROR", "message": "x"})
        return real_void(method, path, body)
    flaky.failures = 0
    sandbox.route = flaky
    app.covers.paypal.tries = 1
    clock.t += 60
    app.covers.tick()
    c = app.covers.load(token)
    assert c["state"] == core.COVER_BREACHED and not c["extra"].get("settlement")
    captured_once = len(sandbox.captures)
    clock.t += 15
    app.covers.tick()
    c = app.covers.load(token)
    assert c["extra"]["settlement"] and len(sandbox.captures) == captured_once == 1
    money_adds_up(app, sandbox, c)
    states = [r[0] for r in app.db.execute("SELECT state FROM paypal_ops WHERE cover_token = ?", (token,)).fetchall()]
    assert states and all(s == "done" for s in states)


def test_a_capture_after_the_honor_period_reauthorizes_first():
    app, clock, sandbox = make()
    v = app.vendors.create_demo()
    app.db.execute("UPDATE vendors SET cover_seconds = ?, gap_seconds = ? WHERE token = ?", (5 * 86400, 86400, v["token"]))
    v = app.vendors.get(v["token"])
    c = app.covers.start_checkout(v, suggested(app, v))
    token = app.covers.pay_with_test_card(c["token"], app.card)["token"]
    first_auth = app.covers.load(token)["authorizations"][0]["id"]
    for _ in range(3):
        clock.t += 86400
        app.covers.tick()
    app.vendors.set_version(v["token"], "narrowed")
    c = run_out(app, clock, token)
    assert len(c["authorizations"]) == 2 and c["authorizations"][0]["id"] == first_auth
    assert sandbox.auths[first_auth]["status"] == "VOIDED"
    s = money_adds_up(app, sandbox, c)
    assert s["vendorCents"] == 2000 * 4 // 5 and s["releasedCents"] == 400


def test_an_orphaned_authorization_is_voided_by_the_sweep():
    app, clock, sandbox = make()
    v = app.vendors.create_demo()
    c = app.covers.start_checkout(v, suggested(app, v))
    real_open = app.covers.open

    def crash(*a, **k):
        raise RuntimeError("crashed after PayPal authorized")
    app.covers.open = crash
    with pytest.raises(RuntimeError):
        app.covers.pay_with_test_card(c["token"], app.card)
    app.covers.open = real_open
    order = app.covers.load(c["token"])["order_id"]
    auth_id = sandbox.orders[order]["purchase_units"][0]["payments"]["authorizations"][0]["id"]
    clock.t += 601
    app.covers.tick()
    assert app.covers.load(c["token"])["state"] == "abandoned"
    assert sandbox.auths[auth_id]["status"] == "VOIDED"


def test_a_failing_panel_never_cuts():
    def broken(prompt):
        raise RuntimeError("model down")
    app, clock, sandbox = make(models={"A": broken, "B": broken})
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    c = run_out(app, clock, token)
    assert c["state"] == core.COVER_COMPLETED and money_adds_up(app, sandbox, c)["vendorCents"] == 2000


def test_a_split_panel_is_contested_and_kept():
    yes = lambda p: json.dumps({"reading": "narrowed", "confidence": 95, "reason": ""})  # noqa: E731
    no = lambda p: json.dumps({"reading": "same", "confidence": 95, "reason": ""})  # noqa: E731
    app, clock, sandbox = make(models={"A": yes, "B": no, "C": yes})
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    clock.t += 60
    app.covers.tick()
    ch = app.covers.view(app.covers.load(token))["checks"][-1]
    assert ch["kind"] == "kept" and ch["contested"] and len(ch["votes"]) == 3


def test_the_log_chains_and_holds_no_paypal_bodies():
    app, clock, sandbox = make()
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    run_out(app, clock, token)
    assert app.ledger.verify() == (True, None)
    kinds = [e["kind"] for e in app.ledger.entries()]
    assert kinds[0] == "checkout_opened" and "authorized" in kinds and kinds[-1] == "settled"
    text = json.dumps(app.ledger.entries())
    for leak in ("purchase_units", "payment_source", "4111", "links", "payer"):
        assert leak not in text


# ------------------------------------------------------------------ HTTP
@pytest.fixture
def http():
    clock = Clock()
    sandbox = FakeSandbox(clock=clock)
    paypal = RestPayPal("id", "secret", transport=httpx.MockTransport(sandbox), sleep=lambda s: None)
    api = create_app({"REDLINE_OFFLINE": "1", "REDLINE_DB": ":memory:", "REDLINE_TICK": "0"}, clock=clock, paypal=paypal)
    with TestClient(api) as client:
        client.clock = clock
        yield client


def test_http_routes_follow_the_web_contract(http):
    assert http.get("/api/health").json()["mode"] == "preview"
    v = http.post("/api/demo/vendors").json()
    assert v["priceCents"] == 2000 and v["version"] == "original" and v["termsUrl"].endswith("/terms")
    page = http.get("/api/vendors/%s/terms" % v["token"]).json()
    assert page["title"] and {b["kind"] for b in page["blocks"]} >= {"title", "heading", "text", "chrome"}
    assert len(http.get("/api/demo/terms-versions").json()) == 10
    sug = http.get("/api/vendors/%s/suggestions" % v["token"]).json()
    assert {s["id"] for s in sug} == {"refund", "deletion", "availability", "notice"}
    pins = [{k: s[k] for k in ("id", "text", "label")} for s in sug[:2]]
    assert http.post("/api/vendors/%s/pins/verify" % v["token"], json={"passages": pins}).json() == []
    r = http.post("/api/checkout", json={"vendor": v["token"], "passages": pins}).json()
    assert r["cover"]["state"] == "opening" and r["orderId"]
    cover = http.post("/api/covers/%s/test-card" % r["cover"]["token"]).json()
    assert cover["state"] == "active" and cover["paypal"]["authorizations"][0]["status"] == "CREATED"
    assert http.put("/api/demo/vendors/%s/version" % v["token"], json={"version": "narrowed"}).json()["version"] == "narrowed"
    http.clock.t += 5
    c = http.post("/api/covers/%s/check" % cover["token"]).json()
    assert c["checks"][-1]["suspected"]
    r429 = http.post("/api/covers/%s/check" % cover["token"])
    assert r429.status_code == 429 and "detail" in r429.json()
    http.clock.t += 5
    c = http.post("/api/covers/%s/check" % cover["token"]).json()
    assert c["state"] == "breached" and c["settlement"]["reason"] == "cut"
    assert c["settlement"]["vendorCents"] + c["settlement"]["releasedCents"] == 2000
    assert http.get("/api/vendors/%s/covers" % v["token"]).json()[0]["token"] == cover["token"]
    log = http.get("/api/log?tail=5").json()
    assert log["verifies"] and len(log["entries"]) == 5 and log["head"] >= 5
    assert http.get("/demo/v/%s/terms" % v["token"]).status_code == 200
    assert http.get("/api/covers/nope").status_code == 404


def test_http_down_page_and_errors(http):
    v = http.post("/api/demo/vendors").json()
    http.put("/api/demo/vendors/%s/version" % v["token"], json={"version": "down"})
    assert http.get("/demo/v/%s/terms" % v["token"]).status_code == 503
    assert http.get("/api/vendors/%s/terms" % v["token"]).status_code == 503
    assert http.put("/api/demo/vendors/%s/version" % v["token"], json={"version": "bogus"}).status_code == 422
    assert http.post("/api/checkout", content=b"[1]", headers={"Content-Type": "application/json"}).status_code == 400


def test_a_seat_that_fails_is_reported_as_doubt_not_as_same():
    def broken(prompt):
        raise RuntimeError("404 model not found")
    yes = lambda p: json.dumps({"reading": "narrowed", "confidence": 100, "reason": ""})  # noqa: E731
    app, clock, sandbox = make(models={"A": yes, "B": broken})
    v, token = opened(app, clock)
    app.vendors.set_version(v["token"], "narrowed")
    clock.t += 60
    app.covers.tick()
    ch = app.covers.view(app.covers.load(token))["checks"][-1]
    assert ch["kind"] == "kept" and "did not answer" in ch["note"] and "still given" not in ch["note"]
