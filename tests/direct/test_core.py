"""The rules that decide without a model: what can be opened, how the prepay
accrues, what each report from the watcher does, and what every clock does.
The money rules are also driven with random event sequences: whatever order
reports arrive in, every GEN of a prepay is credited exactly once."""

import random

import pytest
from conftest import BUYER, DELETION, GEN, OTHER, REFUND, T0, VENDOR

import redline_core as core
from redline_text import passage_error

AMOUNT = 300 * GEN
COVER = 3000
APPEAL = 300
PASSAGES = [{"id": "refund", "text": REFUND}, {"id": "deletion", "text": DELETION}]


def errors(**kw):
    args = dict(buyer=BUYER, vendor=VENDOR, url="https://acme.test/terms", passages=PASSAGES, value=AMOUNT,
                coverage_seconds=COVER, accept_seconds=1800, check_gap_seconds=600, passage_error=passage_error)
    args.update(kw)
    return core.cover_errors(**args)


def fresh(state="active"):
    c = core.open_cover(cover_id=0, buyer=BUYER, vendor=VENDOR, url="https://acme.test/terms", passages=PASSAGES,
                        amount=AMOUNT, coverage_seconds=COVER, accept_seconds=1800, check_gap_seconds=600, now=T0)
    if state == "pinning":
        return c
    core.apply_pin(c, ok=True, at=T0 + 5, now=T0 + 5)
    if state == "offered":
        return c
    core.accept(c, by=VENDOR, now=T0 + 10)
    return c


# --- opening ----------------------------------------------------------------


def test_a_well_formed_cover_opens():
    assert errors() == []


@pytest.mark.parametrize("kw,needle", [
    (dict(vendor=BUYER), "must differ"),
    (dict(url="ftp://acme.test/terms"), "https URL"),
    (dict(url="http://acme.test/terms"), "https URL"),
    (dict(url="https://acme.test/" + "a" * 300), "https URL"),
    (dict(url="https://acme.test/terms?token=s3cret"), "query"),
    (dict(url="https://acme.test/terms#refunds"), "fragment"),
    (dict(url="https://acme.test/te rms"), "spaces"),
    (dict(url="https://acme.test/términos"), "non-ASCII"),
    (dict(url="https://user:pw@acme.test/terms"), "user name or password"),
    (dict(url="https://localhost/terms"), "must name a host"),
    (dict(passages=[]), "pin 1 to 4"),
    (dict(passages=PASSAGES * 3), "pin 1 to 4"),
    (dict(passages=[{"id": "x", "text": "short"}]), "at least 40"),
    (dict(passages=[{"id": "x", "text": "word " * 200}]), "at most 600"),
    (dict(passages=[{"id": "a b", "text": REFUND}]), "letters, digits"),
    (dict(passages=[{"id": "x", "text": REFUND}, {"id": "x", "text": DELETION}]), "used twice"),
    (dict(passages=["just text"]), '{"id"'),
    (dict(value=0), "more than 0"),
    (dict(value=True), "more than 0"),
    (dict(coverage_seconds=10), "coverage_seconds"),
    (dict(check_gap_seconds=1200), "room for 3 checks"),
])
def test_a_malformed_cover_is_refused(kw, needle):
    assert any(needle in e for e in errors(**kw)), errors(**kw)


def test_pin_accept_and_cancel_follow_the_states():
    c = fresh("pinning")
    with pytest.raises(core.RedlineError, match="not offered"):
        core.accept(c, by=VENDOR, now=T0 + 1)
    with pytest.raises(core.RedlineError, match="after the acceptance deadline"):
        core.apply_pin(dict(c), ok=True, at=T0 + 1801, now=T0 + 1801)
    core.apply_pin(c, ok=True, at=T0 + 5, now=T0 + 5)
    with pytest.raises(core.RedlineError, match="not being pinned"):
        core.apply_pin(c, ok=True, at=T0 + 6, now=T0 + 6)
    with pytest.raises(core.RedlineError, match="only the vendor"):
        core.accept(c, by=BUYER, now=T0 + 7)
    with pytest.raises(core.RedlineError, match="deadline has passed"):
        core.accept(dict(c), by=VENDOR, now=T0 + 1801)
    with pytest.raises(core.RedlineError, match="only the buyer"):
        core.cancel(dict(c), by=VENDOR, now=T0 + 8)
    assert core.cancel(dict(c), by=BUYER, now=T0 + 8) == {BUYER: AMOUNT}
    core.accept(c, by=VENDOR, now=T0 + 10)
    assert (c["state"], c["start"], c["end"]) == ("active", T0 + 10, T0 + 10 + COVER)
    with pytest.raises(core.RedlineError, match="can no longer be cancelled"):
        core.cancel(c, by=BUYER, now=T0 + 11)


def test_a_failed_pin_refunds_whole_at_once():
    c = fresh("pinning")
    assert core.apply_pin(c, ok=False, at=T0 + 5, now=T0 + 5, reason="not on the page: refund") == {BUYER: AMOUNT}
    assert c["state"] == "refunded" and "refund" in c["why"]


def test_an_offer_nobody_accepts_refunds_whole_at_its_deadline():
    for state in ("pinning", "offered"):
        c = fresh(state)
        assert core.apply_deadlines(c, T0 + 1800, APPEAL) == {}
        assert core.apply_deadlines(c, T0 + 1801, APPEAL) == {BUYER: AMOUNT}
        assert core.apply_deadlines(c, T0 + 9999, APPEAL) == {}


# --- accrual ----------------------------------------------------------------


def test_the_vendor_earns_pro_rata_and_never_more_than_the_prepay():
    c = fresh()
    start = c["start"]
    assert core.earned(c, start - 5) == 0 and core.earned(c, start) == 0
    assert core.earned(c, start + COVER // 3) == AMOUNT // 3
    assert core.earned(c, start + COVER) == core.earned(c, start + 10 * COVER) == AMOUNT
    assert core.earned(fresh("offered"), T0 + 100) == 0


def test_settling_credits_what_was_earned_once():
    c = fresh()
    first = core.apply_deadlines(c, c["start"] + 1000, APPEAL)
    assert first == {VENDOR: AMOUNT * 1000 // COVER}
    assert core.apply_deadlines(c, c["start"] + 1000, APPEAL) == {}
    assert core.apply_deadlines(c, c["end"] + APPEAL, APPEAL) == {VENDOR: AMOUNT - AMOUNT * 1000 // COVER}
    assert c["state"] == "active"  # closes only after the appeal window past the end
    assert core.apply_deadlines(c, c["end"] + APPEAL + 1, APPEAL) == {}
    assert (c["state"], c["paid"], c["refunded"]) == ("completed", AMOUNT, 0)


# --- reports from the watcher ----------------------------------------------


def test_a_breach_holds_accrual_then_refunds_the_rest_after_its_appeal_window():
    c = fresh()
    at = c["start"] + 1000
    assert core.apply_check(c, seq=1, kind="breach", at=at, since=at, now=at) == {VENDOR: AMOUNT * 1000 // COVER}
    c2 = fresh()
    core.apply_check(c2, seq=1, kind="breach", at=at, since=at, now=at)
    assert core.apply_deadlines(c2, at + APPEAL - 1, APPEAL) == {}  # no further accrual, nothing closed
    assert c2["state"] == "active"
    credits = core.apply_deadlines(c2, at + APPEAL, APPEAL)
    assert credits == {BUYER: AMOUNT - AMOUNT * 1000 // COVER}
    assert (c2["state"], c2["closed_as_of"]) == ("breached", at)


def test_a_re_executed_check_with_the_same_number_replaces_it():
    c = fresh()
    at = c["start"] + 1000
    core.apply_check(c, seq=1, kind="breach", at=at, since=at, now=at)
    core.apply_check(c, seq=1, kind="kept", at=at, since=at, now=at + 10)  # the appeal reversed it
    assert "held" not in c
    assert core.apply_deadlines(c, at + APPEAL, APPEAL) == {VENDOR: AMOUNT * (1000 + APPEAL) // COVER - AMOUNT * 1000 // COVER}
    assert c["state"] == "active"


def test_a_reported_breach_stands_against_later_and_older_checks():
    c = fresh()
    at = c["start"] + 1000
    core.apply_check(c, seq=2, kind="breach", at=at, since=at, now=at)
    assert core.apply_check(c, seq=3, kind="kept", at=at + 600, since=at + 600, now=at + 600) == {}
    assert core.apply_check(c, seq=1, kind="kept", at=at - 600, since=at - 600, now=at + 601) == {}
    assert c["held"]["kind"] == "breach"


def test_an_absence_holds_accrual_from_its_start_and_lets_go_when_the_page_is_back():
    c = fresh()
    s = c["start"]
    core.apply_check(c, seq=1, kind="absent", at=s + 1000, since=s + 1000, now=s + 1000)
    assert core.apply_deadlines(c, s + 2500, APPEAL) == {}
    core.apply_check(c, seq=2, kind="absent", at=s + 1600, since=s + 1000, now=s + 1600)
    assert c["held"]["from"] == s + 1000
    core.apply_check(c, seq=3, kind="kept", at=s + 2200, since=s + 2200, now=s + 2200)
    assert "held" not in c


def test_an_older_check_arriving_late_is_ignored():
    c = fresh()
    s = c["start"]
    core.apply_check(c, seq=3, kind="kept", at=s + 1200, since=s + 1200, now=s + 1200)
    assert core.apply_check(c, seq=2, kind="absent", at=s + 600, since=s + 600, now=s + 1300) == {}
    assert "held" not in c and c["seq"] == 3


def test_an_absence_dates_from_its_streak_even_if_an_earlier_report_was_lost():
    c = fresh()
    s = c["start"]
    core.apply_check(c, seq=2, kind="absent", at=s + 1600, since=s + 1000, now=s + 1600)
    assert c["held"]["from"] == s + 1000


def test_gone_dates_from_the_first_absence():
    c = fresh()
    s = c["start"]
    core.apply_check(c, seq=1, kind="absent", at=s + 1000, since=s + 1000, now=s + 1000)
    core.apply_check(c, seq=2, kind="absent", at=s + 1600, since=s + 1000, now=s + 1600)
    core.apply_check(c, seq=3, kind="gone", at=s + 2200, since=s + 1000, now=s + 2200)
    credits = core.apply_deadlines(c, s + 2200 + APPEAL, APPEAL)
    assert credits == {BUYER: AMOUNT - AMOUNT * 1000 // COVER}
    assert (c["state"], c["paid"]) == ("breached", AMOUNT * 1000 // COVER)


def test_a_page_still_absent_at_the_end_is_not_paid_for():
    c = fresh()
    s = c["start"]
    core.apply_check(c, seq=1, kind="absent", at=s + 2900, since=s + 2900, now=s + 2900)
    core.apply_deadlines(c, c["end"] + APPEAL + 1, APPEAL)
    assert (c["state"], c["paid"]) == ("breached", AMOUNT * 2900 // COVER)


def test_reports_are_refused_outside_an_active_cover():
    with pytest.raises(core.RedlineError, match="not active"):
        core.apply_check(fresh("offered"), seq=1, kind="kept", at=T0, since=T0, now=T0)
    c = fresh()
    with pytest.raises(core.RedlineError, match="after the cover ended"):
        core.apply_check(c, seq=1, kind="breach", at=c["end"] + 1, since=c["end"] + 1, now=c["end"] + 1)
    with pytest.raises(core.RedlineError, match="unknown check kind"):
        core.apply_check(c, seq=1, kind="bad", at=c["start"], since=c["start"], now=c["start"])


def test_a_report_dated_before_what_was_already_credited_never_claws_back():
    c = fresh()
    s = c["start"]
    core.apply_deadlines(c, s + 2000, APPEAL)  # credited to +2000
    core.apply_check(c, seq=1, kind="breach", at=s + 1000, since=s + 1000, now=s + 2001)  # an older check arrives late
    credits = core.apply_deadlines(c, s + 2001 + APPEAL, APPEAL)
    assert credits == {BUYER: AMOUNT - AMOUNT * 2000 // COVER}
    assert c["paid"] + c["refunded"] == AMOUNT


# --- the property: no leakage ----------------------------------------------


def _random_life(rng):
    c = fresh(rng.choice(["pinning", "offered", "active", "active", "active"]))
    total = {}
    t = T0 + 20
    seq = 0
    for _ in range(rng.randint(1, 25)):
        t += rng.choice([0, 1, 30, 299, 300, 301, 600, 1000, 2500])
        event = rng.random()
        try:
            if event < 0.45 and c["state"] == "active":
                seq += rng.choice([-1, 0, 1, 1, 1, 2])
                kind = rng.choice(core.CHECK_KINDS)
                at = min(t, c["end"]) - rng.choice([0, 0, 5, 400])
                credits = core.apply_check(c, seq=max(0, seq), kind=kind, at=at, since=at - rng.choice([0, 600]), now=t)
            elif event < 0.5 and c["state"] in ("pinning", "offered"):
                credits = core.cancel(c, by=BUYER, now=t)
            elif event < 0.55 and c["state"] == "pinning":
                credits = core.apply_pin(c, ok=rng.random() < 0.8, at=t, now=t)
            elif event < 0.6 and c["state"] == "offered":
                core.accept(c, by=VENDOR, now=t)
                credits = {}
            else:
                credits = core.apply_deadlines(c, t, APPEAL)
        except core.RedlineError:
            continue
        for who, v in credits.items():
            assert v > 0, "a credit is never zero or negative"
            assert who in (BUYER, VENDOR)
            total[who] = total.get(who, 0) + v
        assert sum(total.values()) + core.outstanding(c) == AMOUNT, "held + credited is always the prepay"
        assert c["paid"] <= AMOUNT
    for who, v in core.apply_deadlines(c, T0 + 10 * COVER, APPEAL).items():
        total[who] = total.get(who, 0) + v
    return c, total


@pytest.mark.parametrize("seed", range(400))
def test_whatever_happens_every_gen_of_a_prepay_is_credited_exactly_once(seed):
    rng = random.Random(seed)
    c, total = _random_life(rng)
    assert c["state"] in core.CLOSED
    assert sum(total.values()) == AMOUNT
    assert total.get(VENDOR, 0) == c["paid"]
    assert total.get(BUYER, 0) == AMOUNT - c["paid"]
    if c["state"] == "completed":
        assert c["paid"] == AMOUNT
    if c["state"] == "refunded":
        assert c["paid"] == 0


# --- the watcher's rules -----------------------------------------------------


def test_three_absences_running_are_gone_and_a_read_page_breaks_the_streak():
    r1 = core.next_record({}, seq=1, page="missing", finding={}, now=T0)
    r2 = core.next_record(r1, seq=2, page="unread", finding={}, now=T0 + 600)
    r3 = core.next_record(r2, seq=3, page="missing", finding={}, now=T0 + 1200)
    assert [r["kind"] for r in (r1, r2, r3)] == ["absent", "absent", "gone"]
    assert r3["since"] == T0 and r3["streak"] == 3
    kept = core.next_record(r2, seq=3, page="read", finding={"kind": "kept", "passage": "", "reading": "", "confidence": 100, "reason": ""}, now=T0 + 1200)
    assert kept["kind"] == "kept" and kept["streak"] == 0
    assert core.next_record(kept, seq=4, page="missing", finding={}, now=T0 + 1800)["streak"] == 1


@pytest.mark.parametrize("reading,confidence,kind", [
    ("narrowed", 70, "breach"), ("removed", 99, "breach"), ("narrowed", 69, "kept"),
    ("same", 100, "kept"), ("cannot_tell", 100, "kept"),
])
def test_only_a_confident_narrowed_or_removed_is_a_breach(reading, confidence, kind):
    assert core.reading_to_kind(reading, confidence) == kind


def test_validators_fail_closed_toward_the_vendor():
    assert core.jury_agrees(leader_kind="breach", own_kind="breach")
    assert not core.jury_agrees(leader_kind="breach", own_kind="kept")
    assert not core.jury_agrees(leader_kind="kept", own_kind="breach")
    assert core.jury_agrees(leader_kind="kept", own_kind="kept")
    with pytest.raises(core.RedlineError):
        core.jury_agrees(leader_kind="maybe", own_kind="kept")


def test_the_first_passage_ruled_a_breach_decides():
    present = {"passage": "refund", "present": True, "reading": "same", "confidence": 100}
    same = {"passage": "refund", "present": False, "reading": "same", "confidence": 90, "reason": "reworded"}
    cut = {"passage": "deletion", "present": False, "reading": "removed", "confidence": 90, "reason": "gone"}
    assert core.decide([present, cut])["kind"] == "breach"
    assert core.decide([same, cut])["passage"] == "deletion"
    assert core.decide([present])["reason"] == "word_for_word"
    assert core.decide([same])["kind"] == "kept"


# --- requests: a check always ends in a record ------------------------------


def test_the_observation_window_is_half_the_gap():
    assert core.observe_window(1800) == 900 and core.observe_window(60) == 30


def test_a_request_needs_no_open_one_the_gap_and_room_before_the_end():
    end = T0 + 3000
    assert core.request_error(pending={}, last_request_at=0, now=T0, gap=600, end=end) == ""
    open_one = {"requested_at": T0, "due": T0 + 300}
    assert "open until %d" % (T0 + 300) in core.request_error(pending=open_one, last_request_at=T0, now=T0 + 10, gap=600, end=end)
    assert "may be requested from %d" % (T0 + 600) in core.request_error(pending={}, last_request_at=T0, now=T0 + 599, gap=600, end=end)
    assert core.request_error(pending={}, last_request_at=T0, now=T0 + 600, gap=600, end=end) == ""
    assert "too close to the end" in core.request_error(pending={}, last_request_at=0, now=end - 299, gap=600, end=end)


def test_a_contested_check_counts_like_an_absent_page():
    r1 = core.next_record({}, seq=1, page="contested", finding={}, now=T0)
    r2 = core.next_record(r1, seq=2, page="contested", finding={}, now=T0 + 600)
    r3 = core.next_record(r2, seq=3, page="unread", finding={}, now=T0 + 1200)
    assert [r["kind"] for r in (r1, r2, r3)] == ["absent", "absent", "gone"] and r3["since"] == T0
