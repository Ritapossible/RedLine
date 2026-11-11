"""The escrow ledger, with the watcher that is already deployed.

The ledger holds no money: it runs a cover under RedLine's rules and
publishes a ruling for an escrow held on another chain. These tests deploy
the unchanged watcher build beside it - the readable builds and the deployed
``*.min.py`` bytes, which must agree - and check that:

- a ruling is final only once the cover has closed, and then its two amounts
  add up to the escrow, to the unit;
- a cut right splits the escrow at the check that found it; terms that hold
  pay the vendor in full; a cover that never started returns everything;
- the ledger and the treasury reach the same split for the same cover;
- nothing but the watcher can report, and only the vendor can accept.
"""

import json
import os

import pytest
from conftest import BUYER, OTHER, PASSAGES, VENDOR, page, scripted_model

from genvm_stub import Runtime, deploy, load

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, "contracts", "build")
L = "0x00000000000000000000000000000000000000e5"  # the escrow ledger
T = "0x00000000000000000000000000000000000000e0"  # the treasury, for comparison
W = "0x00000000000000000000000000000000000000f0"  # the watcher
APPEAL, COVER, GAP, ACCEPT = 300, 3000, 600, 1800
AMOUNT = 500_000_000_000_000  # 0.0005 ETH, in wei
CHAIN = 84532
ESCROW = "0x" + "ab" * 32
FULFILLMENT = "0x" + "cd" * 32
ARBITER = "0x264fefd1b4af4ca3bfc094ebf1ea24e45f71cbc5"
URL = "https://acme.test/terms/%d"


class World:
    def __init__(self, suffix):
        self.rt = rt = Runtime()
        rt.jury = scripted_model
        rt.model = lambda prompt: rt.jury(prompt)
        deploy(rt, load(os.path.join(BUILD, "redline_watcher" + suffix), rt), "RedLineWatcher", W)
        deploy(rt, load(os.path.join(BUILD, "redline_escrow" + suffix), rt), "RedLineEscrow", L, W, APPEAL)
        deploy(rt, load(os.path.join(BUILD, "redline" + suffix), rt), "RedLine", T, W, APPEAL)
        self.ledger, self.treasury = rt.contracts[L], rt.contracts[T]
        rt.balances[BUYER] = 10 * AMOUNT

    def call(self, address, method, *args, sender):
        return self.rt.call(address, method, *args, sender=sender)

    def open(self, n, first="terms-v1.html", **kw):
        self.rt.web[URL % n] = page(first)
        args = dict(vendor=VENDOR, url=URL % n, passages=json.dumps(PASSAGES), amount=AMOUNT, chain=CHAIN,
                    escrow=ESCROW, arbiter=ARBITER)
        args.update(kw)
        return self.call(L, "open_cover", args["vendor"], args["url"], args["passages"], args["amount"], COVER, ACCEPT,
                         GAP, args["chain"], args["escrow"], args["arbiter"], sender=BUYER)

    def active(self, n):
        i = self.open(n)
        self.call(L, "accept", i, FULFILLMENT, sender=VENDOR)
        return i

    def ruling(self, i):
        return json.loads(self.ledger.ruling_of(i))

    def settle(self, i):
        self.call(L, "settle", i, sender=OTHER)
        return self.ruling(i)


@pytest.fixture(params=[".py", ".min.py"], ids=["readable", "deployed"])
def world(request):
    return World(request.param)


def test_a_cut_right_splits_the_escrow_at_the_check_that_found_it(world):
    i = world.active(1)
    world.rt.now += 1000  # a third of the cover
    world.rt.web[URL % 1] = page("terms-narrowed.html")
    world.call(W, "check", L, i, sender=OTHER)
    r = world.settle(i)
    assert not r["final"] and r["vendor_amount"] == 0 and r["buyer_amount"] == 0  # inside the appeal window
    world.rt.now += APPEAL
    r = world.settle(i)
    assert r["final"] and r["state"] == "breached" and r["started"]
    assert r["vendor_amount"] == AMOUNT * 1000 // COVER
    assert r["vendor_amount"] + r["buyer_amount"] == AMOUNT == r["amount"]
    assert (r["chain_id"], r["escrow"], r["arbiter"], r["fulfillment"]) == (CHAIN, ESCROW, ARBITER, FULFILLMENT)
    assert (r["vendor"], r["buyer"]) == (VENDOR, BUYER)
    world.rt.now += 10_000
    assert world.settle(i) == r  # a final ruling never changes


def test_terms_that_hold_pay_the_vendor_in_full(world):
    i = world.active(2)
    world.rt.now += 1000
    world.rt.web[URL % 2] = page("terms-v1-rebuilt.html")
    world.call(W, "check", L, i, sender=OTHER)
    world.rt.now += COVER + APPEAL
    r = world.settle(i)
    assert r["final"] and r["state"] == "completed"
    assert (r["vendor_amount"], r["buyer_amount"]) == (AMOUNT, 0)


def test_a_cover_the_vendor_never_accepted_returns_everything(world):
    i = world.open(3)
    world.rt.now += ACCEPT + 1
    r = world.settle(i)
    assert r["final"] and r["state"] == "refunded" and not r["started"]
    assert (r["vendor_amount"], r["buyer_amount"], r["fulfillment"]) == (0, AMOUNT, "")


def test_a_page_gone_three_checks_running_refunds_from_when_it_went(world):
    i = world.active(4)
    world.rt.now += 600
    del world.rt.web[URL % 4]
    for _ in range(3):
        world.call(W, "check", L, i, sender=OTHER)
        world.rt.now += GAP
    world.rt.now += APPEAL
    r = world.settle(i)
    assert r["final"] and r["state"] == "breached"
    assert r["vendor_amount"] == AMOUNT * 600 // COVER and r["vendor_amount"] + r["buyer_amount"] == AMOUNT


def test_the_ledger_and_the_treasury_reach_the_same_split(world):
    """The same cover, once with the money in the treasury and once in an escrow."""
    i = world.active(5)
    world.rt.web[URL % 6] = page("terms-v1.html")
    j = world.rt.call(T, "open_cover", VENDOR, URL % 6, json.dumps(PASSAGES), COVER, ACCEPT, GAP, sender=BUYER, value=AMOUNT)
    world.call(T, "accept", j, sender=VENDOR)
    world.rt.now += 1234
    for n in (5, 6):
        world.rt.web[URL % n] = page("terms-narrowed.html")
    world.call(W, "check", L, i, sender=OTHER)
    world.call(W, "check", T, j, sender=OTHER)
    world.rt.now += APPEAL
    r = world.settle(i)
    world.call(T, "settle", j, sender=OTHER)
    assert r["final"]
    assert (r["vendor_amount"], r["buyer_amount"]) == (world.treasury.owed_to(VENDOR), world.treasury.owed_to(BUYER))


@pytest.mark.parametrize("field,value,reason", [
    ("escrow", "0x1234", "escrow id"),
    ("escrow", "0x" + "zz" * 32, "escrow id"),
    ("arbiter", "0x12", "arbiter"),
    ("chain", 0, "chain id"),
    ("amount", 0, "prepay"),
    ("url", "https://acme.test/terms?token=s3cret", "query"),
    ("vendor", BUYER, "differ"),
    ("passages", "not json", "JSON"),
])
def test_a_bad_opening_is_refused_with_a_reason(world, field, value, reason):
    assert world.open(9, **{field: value}) == -1
    assert reason in json.loads(world.ledger.refusal_of(BUYER))["reason"]
    assert json.loads(world.ledger.status())["covers"] == 0


def test_only_the_watcher_reports_and_only_the_vendor_accepts(world):
    i = world.open(7)
    now = world.rt.now
    for sender, method, args in [
        (BUYER, "note_check", (i, 1, "breach", now, now)),
        (VENDOR, "note_pin", (i, True, now, "")),
        (BUYER, "accept", (i, FULFILLMENT)),
        (VENDOR, "accept", (i, "0x12")),
        (VENDOR, "cancel", (i,)),
    ]:
        with pytest.raises(Exception, match="EXPECTED"):
            world.call(L, method, *args, sender=sender)
    assert world.ruling(i)["state"] == "offered"
    world.call(L, "cancel", i, sender=BUYER)
    r = world.ruling(i)
    assert r["final"] and (r["vendor_amount"], r["buyer_amount"]) == (0, AMOUNT)


def test_the_ledger_holds_no_money(world):
    i = world.active(8)
    world.rt.now += COVER + APPEAL
    world.settle(i)
    assert world.rt.balances.get(L, 0) == 0 and not any(L in (a, b) for a, b, _ in world.rt.transfers)
