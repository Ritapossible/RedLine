"""RedLine end to end, through the two contracts themselves.

Deploys the watcher and the treasury - the readable builds and the deployed
``*.min.py`` bytes - in the GenVM stand-in (genvm_stub.py), drives real
entrypoints, requires both builds to behave identically, and checks the four
transactions the product rests on, plus every way a cover can end:

1. The page rebuilt (new build id, nonce, date) but no pinned word changed:
   kept, no model, the prepay keeps accruing.
2. A pinned passage reworded, the right kept: the jury says same; no refund.
3. "30 days" becomes "7 days, less a fee": narrowed. The buyer gets back what
   the vendor had not earned. Run on three fresh covers.
4. The page answers 404 three checks running: gone, no model, refund.
5. A pinned promise deleted: removed.
6. A page that tries to answer for the jury: still narrowed.
7. Pinning: a passage that is not on the page refuses the cover at once; a
   page that does not answer pins nothing, and the cover refunds at its
   acceptance deadline. Not accepted, or cancelled: refunded whole.
8. A cover nobody finds fault with: the vendor is paid the whole prepay.
9. The watcher becomes unreadable after reporting a breach: the treasury
   still refunds on its own clock. With nothing reported: the vendor is paid.
10. A page absent once, then back: accrual pauses and resumes.
11. Validators that disagree record nothing.
Every GEN funded ends credited exactly once, and is withdrawn.
"""

import json
import os

import pytest
from conftest import BUYER, DELETION, GEN, OTHER, PASSAGES, REFUND, VENDOR, page, scripted_model

from genvm_stub import Runtime, deploy, load

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, "contracts", "build")
T = "0x00000000000000000000000000000000000000e0"  # the treasury
W = "0x00000000000000000000000000000000000000f0"  # the watcher
APPEAL = 300
COVER = 3000  # coverage seconds
GAP = 600  # check gap seconds
AMOUNT = 300 * GEN


def url(n):
    return "https://acme.test/terms/%d" % n


def scenario(suffix):
    rt = Runtime()
    calls = []

    def model(prompt):
        calls.append(prompt)
        return rt.jury(prompt)

    rt.jury = scripted_model
    rt.model = model
    ns_w = load(os.path.join(BUILD, "redline_watcher" + suffix), rt)
    deploy(rt, ns_w, "RedLineWatcher", W)
    ns_t = load(os.path.join(BUILD, "redline" + suffix), rt)
    deploy(rt, ns_t, "RedLine", T, W, APPEAL)
    t = rt.contracts[T]
    w = rt.contracts[W]
    out = {}

    def tx(label, address, method, *args, sender, value=0):
        try:
            r = rt.call(address, method, *args, sender=sender, value=value)
            out[label] = "ok" if r is None else r
        except Exception as exc:
            out[label] = "refused: " + str(exc)
        return out[label]

    def cover(i):
        return json.loads(t.get_cover(i))

    def record(i):
        return json.loads(w.record_of(T, i))

    def owed():
        return {"buyer": t.owed_to(BUYER), "vendor": t.owed_to(VENDOR)}

    def open_cover(label, n, passages=PASSAGES, value=AMOUNT, accept=1800):
        return tx(label, T, "open_cover", VENDOR, url(n), json.dumps(passages), COVER, accept, GAP, sender=BUYER, value=value)

    def active(label, n, first="terms-v1.html"):
        """Fund, pin (sent by the treasury itself) and accept one cover."""
        rt.web[url(n)] = page(first)
        i = open_cover(label + ": open", n)
        out[label + ": pinned"] = cover(i)["state"]
        tx(label + ": accept", T, "accept", i, sender=VENDOR)
        return i

    def check(label, i, sender=OTHER):
        before = len(calls)
        r = tx(label, W, "check", T, i, sender=sender)
        out[label + ": model calls"] = len(calls) - before
        out[label + ": record"] = record(i)
        return r

    # --- 7. Opening and pinning ------------------------------------------
    rt.web[url(90)] = page("terms-v1.html")
    tx("open: bad passages", T, "open_cover", VENDOR, url(90), json.dumps([{"id": "x", "text": "too short"}]), COVER, 1800, GAP,
       sender=BUYER, value=AMOUNT)
    out["open: bad passages refusal"] = json.loads(t.refusal_of(BUYER))
    tx("open: no value", T, "open_cover", VENDOR, url(90), json.dumps(PASSAGES), COVER, 1800, GAP, sender=BUYER, value=0)
    tx("open: vendor is buyer", T, "open_cover", BUYER, url(90), json.dumps(PASSAGES), COVER, 1800, GAP, sender=BUYER, value=AMOUNT)
    out["refunded after refusals"] = t.owed_to(BUYER)

    rt.web[url(91)] = page("terms-v1.html")
    bogus = [{"id": "refund", "text": REFUND.replace("30 days", "90 days")}]
    i_bogus = open_cover("pin: passage not on page", 91, passages=bogus)
    out["pin: passage not on page"] = cover(i_bogus)
    out["pin: passage not on page record"] = json.loads(w.pin_of(T, i_bogus))

    # The page does not answer at funding: nothing is pinned; pin can be sent
    # again; if it never lands, the cover refunds at its acceptance deadline.
    i_down = open_cover("pin: page down", 92)  # url(92) not served
    out["pin: page down state"] = cover(i_down)["state"]
    out["pin: page down messages"] = [m[2:] for m in rt.messages if m[2] == "pin"][-1:]
    tx("pin: accept before pinned", T, "accept", i_down, sender=VENDOR)

    rt.web[url(93)] = page("terms-v1.html")
    i_cancel = open_cover("cancel: open", 93)
    tx("cancel: by vendor", T, "cancel", i_cancel, sender=VENDOR)
    tx("cancel: by buyer", T, "cancel", i_cancel, sender=BUYER)
    out["cancel"] = cover(i_cancel)
    tx("cancel: accept after", T, "accept", i_cancel, sender=VENDOR)

    rt.web[url(94)] = page("terms-v1.html")
    i_late = open_cover("late: open", 94)
    tx("note from anyone", T, "note_check", i_late, 1, "breach", rt.now, rt.now, sender=BUYER)
    tx("pin note from anyone", T, "note_pin", i_late, True, rt.now, "", sender=VENDOR)
    tx("late: accept by buyer", T, "accept", i_late, sender=BUYER)

    # --- 1-6, 10, 11: active covers ---------------------------------------
    i_unchanged = active("unchanged", 1)
    i_reworded = active("reworded", 2)
    i_narrow = [active("narrowed %d" % k, 10 + k) for k in (1, 2, 3)]
    i_gone = active("gone", 4)
    i_removed = active("removed", 5)
    i_injected = active("injected", 6)
    i_complete = active("complete", 7)
    i_blink = active("blink", 8)
    i_split = active("disagree", 9)
    i_bricked = active("bricked", 20)
    i_quiet = active("quiet", 21)
    started = rt.now
    tx("accept twice", T, "accept", i_unchanged, sender=VENDOR)
    tx("check too early", W, "check", T, i_late, sender=OTHER)

    rt.now += 1000  # a third of the way through every cover
    rt.web[url(1)] = page("terms-v1-rebuilt.html")
    check("1 unchanged", i_unchanged)
    check("1 again at once", i_unchanged)
    rt.web[url(2)] = page("terms-reworded.html")
    check("2 reworded", i_reworded)
    for k, i in zip((1, 2, 3), i_narrow):
        rt.web[url(10 + k)] = page("terms-narrowed.html")
        check("3 narrowed %d" % k, i)
    # Inside the appeal window the breach holds the vendor's accrual but closes nothing.
    tx("3 narrowed 1: settle early", T, "settle", i_narrow[0], sender=VENDOR)
    out["3 narrowed 1: early"] = cover(i_narrow[0])
    rt.web[url(5)] = page("terms-deletion-removed.html")
    check("5 removed", i_removed)
    rt.web[url(6)] = page("terms-narrowed-injected.html")
    check("6 injected", i_injected)
    out["6 injected: prompt"] = calls[-1]
    rt.web[url(20)] = page("terms-narrowed.html")
    check("9 bricked: breach", i_bricked)

    # 11. Validators disagree: the leader reads narrowed, the validator same.
    rt.web[url(9)] = page("terms-narrowed.html")
    flip = {"n": 0}

    def disagreeing(prompt):
        flip["n"] += 1
        if flip["n"] == 1:
            return {"reading": "narrowed", "reason": "", "confidence": 95}
        return {"reading": "same", "reason": "", "confidence": 95}

    rt.jury = disagreeing
    check("11 disagree", i_split)
    rt.jury = scripted_model

    # 4. Gone: 404 three checks running, each a gap apart.
    rt.web[url(4)] = 404
    check("4 gone 1", i_gone)
    check("4 gone too soon", i_gone)
    out["4 after one absence"] = cover(i_gone)

    # 10. Absent once (no answer), then back.
    del rt.web[url(8)]
    check("10 blink: absent", i_blink)
    out["10 blink: held"] = cover(i_blink).get("held")

    rt.now += GAP
    check("4 gone 2", i_gone)
    rt.web[url(8)] = page("terms-v1-rebuilt.html")
    check("10 blink: back", i_blink)
    out["10 blink: after"] = cover(i_blink)
    rt.now += GAP
    rt.web[url(4)] = 503  # an outage counts as absent too
    check("4 gone 3", i_gone)
    check("4 after gone", i_gone)

    # Breaches wait out their appeal window, then settle refunds the rest.
    rt.contracts.pop(W)  # 9. the watcher becomes unreadable
    rt.now += APPEAL
    for label, i in [("1", i_unchanged), ("2", i_reworded), ("3a", i_narrow[0]), ("3b", i_narrow[1]), ("3c", i_narrow[2]),
                     ("4", i_gone), ("5", i_removed), ("6", i_injected), ("9", i_bricked), ("10", i_blink), ("11", i_split)]:
        before = owed()
        tx("settle " + label, T, "settle", i, sender=OTHER)
        after = owed()
        out["cover " + label] = cover(i)
        out["credited " + label] = {k: after[k] - before[k] for k in after}
    rt.contracts[W] = w

    # 8. Run to the end: completed covers pay the vendor the whole prepay.
    rt.now = started + COVER + APPEAL + 1
    rt.contracts.pop(W)  # 9. with nothing reported and the watcher gone, the vendor is paid
    for i in range(int(json.loads(t.status())["covers"])):
        tx("end %d" % i, T, "settle", i, sender=OTHER)
    rt.contracts[W] = w
    out["states"] = [cover(i)["state"] for i in range(int(json.loads(t.status())["covers"]))]
    out["covers"] = {i: cover(i) for i in range(int(json.loads(t.status())["covers"]))}
    out["indices"] = {"unchanged": i_unchanged, "reworded": i_reworded, "narrowed": i_narrow, "gone": i_gone, "removed": i_removed,
                      "injected": i_injected, "complete": i_complete, "blink": i_blink, "disagree": i_split,
                      "bricked": i_bricked, "quiet": i_quiet, "bogus": i_bogus, "down": i_down, "cancel": i_cancel, "late": i_late}
    out["owed"] = owed()
    out["status before withdraw"] = json.loads(t.status())
    tx("withdraw vendor", T, "withdraw", sender=VENDOR)
    tx("withdraw buyer", T, "withdraw", sender=BUYER)
    tx("withdraw again", T, "withdraw", sender=BUYER)
    out["status"] = json.loads(t.status())
    out["balance"] = rt.balances.get(T, 0)
    out["watcher balance"] = rt.balances.get(W, 0)
    out["transfers"] = list(rt.transfers)
    out["failed messages"] = [m for m in rt.messages if m[4] != "ok"]
    return out


@pytest.fixture(scope="module")
def readable():
    return scenario(".py")


@pytest.fixture(scope="module")
def deployed():
    return scenario(".min.py")


def test_deployed_bytes_behave_exactly_like_the_tested_build(readable, deployed):
    assert readable.keys() == deployed.keys()
    for key in readable:
        assert readable[key] == deployed[key], key


def test_opening_needs_real_passages_a_prepay_and_two_parties(readable):
    r = readable
    assert r["open: bad passages"] == -1 and "at least 40 characters" in r["open: bad passages refusal"]["reason"]
    assert r["open: no value"] == -1 and r["open: vendor is buyer"] == -1
    assert r["refunded after refusals"] == 2 * AMOUNT  # every refused value credited back


def test_a_passage_not_on_the_page_refuses_the_cover_at_once(readable):
    c = readable["pin: passage not on page"]
    assert (c["state"], c["refunded"]) == ("refunded", AMOUNT) and "not on the page: refund" in c["why"]
    assert readable["pin: passage not on page record"]["found"] == []


def test_a_page_that_does_not_answer_pins_nothing_and_cannot_be_accepted(readable):
    assert readable["pin: page down state"] == "pinning"
    assert "is not offered" in readable["pin: accept before pinned"]
    assert readable["covers"][readable["indices"]["down"]]["state"] == "refunded"  # at its acceptance deadline


def test_cancel_and_acceptance_belong_to_their_parties(readable):
    r = readable
    assert "only the buyer may cancel" in r["cancel: by vendor"]
    assert r["cancel: by buyer"] == "ok" and r["cancel"]["state"] == "refunded"
    assert "is not offered" in r["cancel: accept after"]
    assert "only the vendor may accept" in r["late: accept by buyer"]
    assert "is not offered (it is active)" in r["accept twice"]
    assert r["covers"][r["indices"]["late"]]["state"] == "refunded"  # never accepted


def test_only_the_watcher_reports_on_a_cover(readable):
    assert "only the watcher contract reports" in readable["note from anyone"]
    assert "only the watcher contract reports" in readable["pin note from anyone"]
    assert "the cover is not active" in readable["check too early"]


def test_1_a_rebuilt_page_with_every_word_kept_runs_no_model_and_moves_nothing(readable):
    r = readable
    rec = r["1 unchanged: record"]
    assert (rec["kind"], rec["reason"], r["1 unchanged: model calls"]) == ("kept", "word_for_word", 0)
    assert "may run from" in r["1 again at once"]
    assert r["cover 1"]["state"] == "active" and r["credited 1"]["buyer"] == 0
    assert r["covers"][r["indices"]["unchanged"]]["state"] == "completed"


def test_2_a_reworded_right_is_kept(readable):
    r = readable
    rec = r["2 reworded: record"]
    assert (rec["kind"], rec["passage"], rec["reading"]) == ("kept", "refund", "same")
    # Only the reworded passage reaches the jury: once for the leader, once for
    # the validator the stand-in runs.
    assert r["2 reworded: model calls"] == 2
    assert r["credited 2"]["buyer"] == 0 and r["covers"][r["indices"]["reworded"]]["state"] == "completed"


def test_3_a_narrowed_right_refunds_what_the_vendor_had_not_earned(readable):
    r = readable
    for label in ("3a", "3b", "3c"):
        c = r["cover " + label]
        assert (c["state"], c["last_check"]["kind"]) == ("breached", "breach")
        # Accepted at the start, checked a third of the way through.
        assert c["paid"] == AMOUNT * 1000 // COVER and c["refunded"] == AMOUNT - AMOUNT * 1000 // COVER
        assert c["paid"] + c["refunded"] == AMOUNT
    for k in (1, 2, 3):
        rec = r["3 narrowed %d: record" % k]
        assert (rec["kind"], rec["passage"], rec["reading"]) == ("breach", "refund", "narrowed")
    early = r["3 narrowed 1: early"]
    assert early["state"] == "active" and early["held"]["kind"] == "breach"
    assert early["paid"] == AMOUNT * 1000 // COVER  # credited up to the check, not past it


def test_4_a_page_gone_three_checks_running_refunds_without_a_model(readable):
    r = readable
    assert [r["4 gone %d: record" % k]["kind"] for k in (1, 2, 3)] == ["absent", "absent", "gone"]
    assert sum(r["4 gone %d: model calls" % k] for k in (1, 2, 3)) == 0
    assert "may run from" in r["4 gone too soon"]
    assert "already ended in a gone" in r["4 after gone"]
    held = r["4 after one absence"]["held"]
    assert held["kind"] == "absent"
    c = r["cover 4"]
    # Gone dates from the first absent check: the vendor earned only until then.
    assert c["state"] == "breached" and c["paid"] == AMOUNT * 1000 // COVER


def test_5_a_deleted_promise_is_removed(readable):
    rec = readable["5 removed: record"]
    assert (rec["kind"], rec["passage"], rec["reading"]) == ("breach", "deletion", "removed")
    assert readable["5 removed: model calls"] == 2  # leader + validator; the refund passage is still word for word
    assert readable["cover 5"]["state"] == "breached"


def test_6_a_page_cannot_answer_for_the_jury(readable):
    r = readable
    assert r["6 injected: record"]["kind"] == "breach"
    prompt = r["6 injected: prompt"]
    assert prompt.count("=== END CURRENT ===") == 1  # the page's own marker was defused
    assert "= = = end current = = =" in prompt


def test_9_an_unreadable_watcher_cannot_stop_a_reported_refund_or_the_vendors_pay(readable):
    r = readable
    assert r["cover 9"]["state"] == "breached" and r["credited 9"]["buyer"] > 0
    assert r["covers"][r["indices"]["quiet"]]["state"] == "completed"
    assert r["covers"][r["indices"]["quiet"]]["paid"] == AMOUNT


def test_10_a_page_absent_once_pauses_accrual_and_resumes(readable):
    r = readable
    assert r["10 blink: absent: record"]["kind"] == "absent" and r["10 blink: held"]["kind"] == "absent"
    assert r["10 blink: back: record"]["kind"] == "kept" and "held" not in r["10 blink: after"]
    assert r["covers"][r["indices"]["blink"]]["state"] == "completed"


def test_11_validators_that_disagree_record_nothing(readable):
    r = readable
    assert r["11 disagree"].startswith("refused")
    assert r["11 disagree: record"] == {}
    assert r["covers"][r["indices"]["disagree"]]["state"] == "completed"


def test_every_gen_is_credited_exactly_once_and_withdrawn(readable):
    r = readable
    assert all(s in ("breached", "completed", "refunded") for s in r["states"])
    for c in r["covers"].values():
        assert c["paid"] + c.get("refunded", 0) == c["amount"]
    s = r["status before withdraw"]
    assert s["held"] == 0 and s["owed"] == s["balance"] == r["owed"]["buyer"] + r["owed"]["vendor"]
    assert r["withdraw vendor"] == "ok" and r["withdraw buyer"] == "ok" and "nothing is owed" in r["withdraw again"]
    assert r["status"]["owed"] == 0 and r["balance"] == 0 and r["watcher balance"] == 0
    assert (T, VENDOR, r["owed"]["vendor"]) in r["transfers"] and (T, BUYER, r["owed"]["buyer"]) in r["transfers"]


def test_messages_that_fail_are_only_the_ones_meant_to(readable):
    # The pin of a page that never answered is the only message that may fail.
    failed = readable["failed messages"]
    assert all(m[2] == "pin" for m in failed) and len(failed) == 1
