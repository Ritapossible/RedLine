"""RedLine: the deterministic core.

Every decision that does not need a model lives here, as pure Python with no
``gl.*``, no network and no clock of its own. It is inlined into both
contracts by ``deploy/build_contract.py`` and tested directly.

The product in one paragraph. A buyer prepays a vendor for a coverage
period and pins, word for word, the passages of the vendor's public terms
page it relies on ("refunds within 30 days", "we delete your data within 7
days"). The prepay sits in the RedLine treasury and accrues to the vendor
second by second while the cover runs. Anyone may ask the watcher contract to
check the page. If every pinned passage is still there word for word, nothing
happens and no model runs. If one is gone, a jury compares the pinned passage
with what the page says now and answers one question: is the right it gave
the same, narrowed, or removed? A narrowed or removed right - or a page that
answers with nothing, three checks running - ends the cover: the vendor keeps
what it earned until then, and the buyer gets the rest back.
"""

import json

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

# Cover states, in the treasury.
COVER_PINNING = "pinning"  # funded; the watcher is checking that every passage is on the page
COVER_OFFERED = "offered"  # pinned; waiting for the vendor to accept
COVER_ACTIVE = "active"  # accepted; the prepay accrues to the vendor
COVER_BREACHED = "breached"  # closed: a right was cut; the unearned rest went back to the buyer
COVER_COMPLETED = "completed"  # closed: the cover ran its course; the vendor earned it all
COVER_REFUNDED = "refunded"  # closed before it started: never pinned, never accepted, or cancelled
COVER_STATES = (COVER_PINNING, COVER_OFFERED, COVER_ACTIVE, COVER_BREACHED, COVER_COMPLETED, COVER_REFUNDED)
CLOSED = (COVER_BREACHED, COVER_COMPLETED, COVER_REFUNDED)

# What one check of the page found, as the watcher records it.
CHECK_KEPT = "kept"  # every pinned right still granted (word for word, or ruled the same)
CHECK_ABSENT = "absent"  # the page did not answer, or answered 404/410
CHECK_BREACH = "breach"  # the jury ruled a pinned right narrowed or removed
CHECK_GONE = "gone"  # the page was absent ABSENT_LIMIT checks running
CHECK_KINDS = (CHECK_KEPT, CHECK_ABSENT, CHECK_BREACH, CHECK_GONE)
ENDS_COVER = (CHECK_BREACH, CHECK_GONE)  # kinds that end a cover in the buyer's favour
HOLDS_ACCRUAL = (CHECK_ABSENT, CHECK_BREACH, CHECK_GONE)  # kinds that stop the vendor accruing

# The jury's readings of a pinned passage against the current page.
READ_SAME = "same"  # the right is still granted, perhaps reworded or moved on the page
READ_NARROWED = "narrowed"  # still there, but less favourable to the customer
READ_REMOVED = "removed"  # no longer granted on the page
READ_CANNOT_TELL = "cannot_tell"
READINGS = (READ_SAME, READ_NARROWED, READ_REMOVED, READ_CANNOT_TELL)
BREACH_READINGS = (READ_NARROWED, READ_REMOVED)

# What fetching the page found.
PAGE_READ = "read"  # 2xx: the page answered with a body
PAGE_MISSING = "missing"  # 404/410: the server says the page is not there
PAGE_UNREAD = "unread"  # no answer: network error, 5xx, 429
MISSING_STATUS = (404, 410)

# A hesitant breach is not a breach: the vendor keeps earning unless a right
# was demonstrably cut. Applied to the leader and every validator alike.
MIN_BREACH_CONFIDENCE = 70
ABSENT_LIMIT = 3  # absent checks running, each at least check_gap apart, that end a cover

MAX_PASSAGES = 4
MAX_ID = 24
MAX_URL = 300
MIN_WINDOW = 60
MAX_WINDOW = 400 * 86400


class RedlineError(ValueError):
    """A condition the caller must not be able to ignore."""


def _int(value, context):
    if isinstance(value, bool) or not isinstance(value, int):
        raise RedlineError("%s: expected an integer, got %r" % (context, value))
    return value


def normalize_address(value, context="address"):
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        raise RedlineError("%s: not an address: %r" % (context, value))
    for ch in text[2:]:
        if ch not in "0123456789abcdef":
            raise RedlineError("%s: not hex: %r" % (context, value))
    return text


# --------------------------------------------------------------------------
# Opening a cover
# --------------------------------------------------------------------------


def _id_ok(cid):
    if not cid or len(cid) > MAX_ID:
        return False
    for ch in cid:
        if not (ch.isalnum() or ch in "-_"):
            return False
    return True


def cover_errors(*, buyer, vendor, url, passages, value, coverage_seconds, accept_seconds, check_gap_seconds, passage_error):
    """Why a cover cannot be opened ([] if it can). ``passage_error`` is the
    text module's check of one passage, passed in so this module stays free
    of it."""
    errors = []
    try:
        if normalize_address(buyer, "buyer") == normalize_address(vendor, "vendor"):
            errors.append("the buyer and the vendor must differ")
    except RedlineError as exc:
        errors.append(str(exc))
    u = str(url).strip()
    if not (u.startswith("https://") or u.startswith("http://")) or len(u) > MAX_URL or " " in u:
        errors.append("the terms page must be an http(s) URL of at most %d characters" % MAX_URL)
    if not isinstance(passages, list) or not 1 <= len(passages) <= MAX_PASSAGES:
        errors.append("pin 1 to %d passages" % MAX_PASSAGES)
    else:
        seen = set()
        for p in passages:
            if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not isinstance(p.get("text"), str):
                errors.append("each passage is {\"id\": ..., \"text\": ...}")
                continue
            cid = p["id"].strip()
            if not _id_ok(cid):
                errors.append("passage id %r: 1-%d letters, digits, - or _" % (cid[:30], MAX_ID))
            elif cid in seen:
                errors.append("passage id %r is used twice" % cid)
            seen.add(cid)
            e = passage_error(p["text"])
            if e:
                errors.append("passage %r: %s" % (cid[:30], e))
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.append("the prepay must be more than 0")
    for name, v in (("coverage_seconds", coverage_seconds), ("accept_seconds", accept_seconds), ("check_gap_seconds", check_gap_seconds)):
        if isinstance(v, bool) or not isinstance(v, int) or v < MIN_WINDOW or v > MAX_WINDOW:
            errors.append("%s must be %d-%d seconds" % (name, MIN_WINDOW, MAX_WINDOW))
    if not errors and ABSENT_LIMIT * int(check_gap_seconds) > int(coverage_seconds):
        errors.append("check_gap_seconds must leave room for %d checks in the coverage period" % ABSENT_LIMIT)
    return errors


def open_cover(*, cover_id, buyer, vendor, url, passages, amount, coverage_seconds, accept_seconds, check_gap_seconds, now):
    """The record a funded cover starts as."""
    return {
        "id": int(cover_id),
        "buyer": normalize_address(buyer, "buyer"),
        "vendor": normalize_address(vendor, "vendor"),
        "url": str(url).strip(),
        "passages": [{"id": str(p["id"]).strip(), "text": " ".join(str(p["text"]).split())} for p in passages],
        "amount": int(amount),
        "coverage_seconds": int(coverage_seconds),
        "check_gap_seconds": int(check_gap_seconds),
        "created_at": int(now),
        "accept_by": int(now) + int(accept_seconds),
        "state": COVER_PINNING,
        "paid": 0,  # credited to the vendor so far
        "seq": 0,  # the last check the treasury has been told about
    }


# --------------------------------------------------------------------------
# Money: accrual and closing
# --------------------------------------------------------------------------


def earned(cover, at):
    """What the vendor has earned by time ``at``: the prepay pro rata over the
    coverage period, never more than the prepay."""
    if cover.get("start") is None:
        return 0
    elapsed = int(at) - int(cover["start"])
    if elapsed <= 0:
        return 0
    duration = int(cover["coverage_seconds"])
    if elapsed >= duration:
        return int(cover["amount"])
    return int(cover["amount"]) * elapsed // duration


def accrual_cap(cover, now):
    """The time up to which the vendor may be credited now: now, or the time
    of a check that holds accrual (an absent page, or a breach waiting out its
    appeal window), whichever is earlier. ``earned`` stops at the end."""
    cap = int(now)
    held = cover.get("held")
    if held:
        cap = min(cap, int(held["from"]))
    return cap


def _credit(credits, who, amount):
    if amount > 0:
        credits[who] = credits.get(who, 0) + amount


def accrue(cover, now):
    """Credit the vendor what it has earned and not been paid. Returns the
    credits made."""
    credits = {}
    if cover["state"] != COVER_ACTIVE:
        return credits
    due = earned(cover, accrual_cap(cover, now)) - int(cover["paid"])
    if due > 0:
        cover["paid"] = int(cover["paid"]) + due
        _credit(credits, cover["vendor"], due)
    return credits


def close(cover, state, at, now):
    """End an active cover: the vendor is owed what it earned by ``at``, the
    buyer the rest. Never claws back what was already credited, so the two
    always add up to the prepay."""
    credits = {}
    vendor_total = max(int(cover["paid"]), earned(cover, at))
    _credit(credits, cover["vendor"], vendor_total - int(cover["paid"]))
    _credit(credits, cover["buyer"], int(cover["amount"]) - vendor_total)
    cover["paid"] = vendor_total
    cover["refunded"] = int(cover["amount"]) - vendor_total
    cover["state"] = state
    cover["closed_at"] = int(now)
    cover["closed_as_of"] = int(at)
    cover.pop("held", None)
    return credits


def refund_all(cover, now, why):
    """A cover that never started goes back to the buyer whole."""
    credits = {}
    _credit(credits, cover["buyer"], int(cover["amount"]))
    cover["refunded"] = int(cover["amount"])
    cover["state"] = COVER_REFUNDED
    cover["closed_at"] = int(now)
    cover["why"] = str(why)[:80]
    return credits


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def apply_pin(cover, *, ok, at, now, reason=""):
    """The watcher's report on pinning. Every passage on the page: the cover
    is offered to the vendor. A page that answered without them: refunded at
    once - nothing was ever at risk."""
    if cover["state"] != COVER_PINNING:
        raise RedlineError("cover %d is not being pinned" % int(cover["id"]))
    if int(at) > int(cover["accept_by"]):
        raise RedlineError("the pin came after the acceptance deadline")
    if ok:
        cover["state"] = COVER_OFFERED
        cover["pinned_at"] = int(at)
        return {}
    return refund_all(cover, now, "not pinned: " + str(reason))


def accept(cover, *, by, now):
    if normalize_address(by) != cover["vendor"]:
        raise RedlineError("only the vendor may accept")
    if cover["state"] != COVER_OFFERED:
        raise RedlineError("cover %d is not offered (it is %s)" % (int(cover["id"]), cover["state"]))
    if int(now) > int(cover["accept_by"]):
        raise RedlineError("the acceptance deadline has passed")
    cover["state"] = COVER_ACTIVE
    cover["start"] = int(now)
    cover["end"] = int(now) + int(cover["coverage_seconds"])


def cancel(cover, *, by, now):
    """The buyer withdraws an offer the vendor has not accepted."""
    if normalize_address(by) != cover["buyer"]:
        raise RedlineError("only the buyer may cancel")
    if cover["state"] not in (COVER_PINNING, COVER_OFFERED):
        raise RedlineError("cover %d can no longer be cancelled (it is %s)" % (int(cover["id"]), cover["state"]))
    return refund_all(cover, now, "cancelled by the buyer")


def apply_check(cover, *, seq, kind, at, since, now):
    """The watcher's report of one check, sent as a message. Credits nothing
    by itself: it stops the vendor accruing while the page is absent or a
    breach waits out its appeal window, and lets an absence go when the page
    is back. Checks are numbered; an older one is ignored, and the same
    number again replaces it (a re-executed, appealed check)."""
    if cover["state"] != COVER_ACTIVE:
        raise RedlineError("cover %d is not active" % int(cover["id"]))
    if kind not in CHECK_KINDS:
        raise RedlineError("unknown check kind %r" % kind)
    seq = _int(seq, "seq")
    if int(at) > int(cover["end"]):
        raise RedlineError("the check came after the cover ended")
    held = cover.get("held")
    if seq < int(cover["seq"]):
        return {}
    if held and int(held["seq"]) != seq and held["kind"] in ENDS_COVER:
        return {}  # a breach already reported stands; later checks do not undo it
    credits = accrue(cover, at) if not held else {}
    cover["seq"] = seq
    cover["last_check"] = {"seq": seq, "kind": kind, "at": int(at)}
    if kind in HOLDS_ACCRUAL:
        start = int(since) if kind in (CHECK_ABSENT, CHECK_GONE) else int(at)
        if held and int(held["seq"]) != seq:
            start = min(start, int(held["from"]))  # an absence already holding accrual keeps its start
        cover["held"] = {"seq": seq, "kind": kind, "from": max(min(start, int(at)), int(cover["start"])), "noted_at": int(now)}
    else:
        cover.pop("held", None)
    return credits


def apply_deadlines(cover, now, appeal_seconds):
    """Every clock of one cover, by arithmetic. Reads no other contract.

    - pinning or offered, past the acceptance deadline: refunded whole.
    - active: the vendor is credited what it earned.
    - a breach (or a page gone) reported ``appeal_seconds`` ago: closed - the
      vendor keeps what it earned until the check, the buyer gets the rest.
    - past the end plus the appeal window: closed. If the page was absent at
      the last check, the vendor keeps only what it earned before the page
      went; otherwise it earned the whole prepay.
    """
    now = int(now)
    state = cover["state"]
    if state in (COVER_PINNING, COVER_OFFERED):
        if now > int(cover["accept_by"]):
            return refund_all(cover, now, "not accepted in time")
        return {}
    if state != COVER_ACTIVE:
        return {}
    held = cover.get("held")
    if held and held["kind"] in ENDS_COVER and now >= int(held["noted_at"]) + int(appeal_seconds):
        return close(cover, COVER_BREACHED, int(held["from"]), now)
    if now > int(cover["end"]) + int(appeal_seconds):
        if held and held["kind"] in ENDS_COVER:
            return close(cover, COVER_BREACHED, int(held["from"]), now)
        if held and held["kind"] == CHECK_ABSENT:
            return close(cover, COVER_BREACHED, int(held["from"]), now)
        return close(cover, COVER_COMPLETED, int(cover["end"]), now)
    return accrue(cover, now)


def outstanding(cover):
    """GEN this cover still holds in the treasury."""
    if cover["state"] in CLOSED:
        return 0
    return int(cover["amount"]) - int(cover["paid"])


# --------------------------------------------------------------------------
# The watcher's rules
# --------------------------------------------------------------------------


def check_gap_error(previous, *, now, gap):
    """Why the page may not be checked again yet ("" if it may). Checks are
    spaced so that three absences span real time, not one outage."""
    if previous and int(now) < int(previous["at"]) + int(gap):
        return "the page was checked at %d; the next check may run from %d" % (int(previous["at"]), int(previous["at"]) + int(gap))
    return ""


def next_record(previous, *, seq, page, finding, now):
    """The watcher's record of one check. ``page`` is what the fetch found
    (PAGE_*); ``finding`` is the decided outcome of a read page:
    ``{"kind": kept|breach, "passage", "reading", "confidence", "reason"}``."""
    record = {"seq": int(seq), "at": int(now), "page": page}
    if page == PAGE_READ:
        record.update({k: finding[k] for k in ("kind", "passage", "reading", "confidence", "reason") if k in finding})
        record["streak"] = 0
        record["since"] = int(now)
        return record
    streak, since = 1, int(now)
    if previous and previous.get("kind") in (CHECK_ABSENT,):
        streak = int(previous.get("streak", 1)) + 1
        since = int(previous.get("since", now))
    record["streak"] = streak
    record["since"] = since
    record["kind"] = CHECK_GONE if streak >= ABSENT_LIMIT else CHECK_ABSENT
    return record


def reading_to_kind(reading, confidence):
    """A breach needs a confident narrowed or removed reading."""
    if reading in BREACH_READINGS and int(confidence) >= MIN_BREACH_CONFIDENCE:
        return CHECK_BREACH
    return CHECK_KEPT


def jury_agrees(*, leader_kind, own_kind):
    """Does a validator accept the leader's finding on a passage? Fail closed
    toward the vendor: the buyer is refunded only if the right was cut.

    - The same kind is agreement.
    - A breach stands only on agreement.
    - A validator sure of a breach vetoes "kept"; the round fails and nothing
      is recorded - the page can be checked again after the gap.
    """
    if leader_kind not in (CHECK_KEPT, CHECK_BREACH) or own_kind not in (CHECK_KEPT, CHECK_BREACH):
        raise RedlineError("unknown finding")
    return leader_kind == own_kind


def decide(results):
    """The finding of a read page from the per-passage results, in pin order:
    the first passage ruled a breach, else kept. ``results`` is a list of
    ``{"passage", "present", "reading", "confidence", "reason"}``."""
    for r in results:
        if not r["present"] and reading_to_kind(r["reading"], r["confidence"]) == CHECK_BREACH:
            return {"kind": CHECK_BREACH, "passage": r["passage"], "reading": r["reading"],
                    "confidence": int(r["confidence"]), "reason": str(r.get("reason", ""))[:48]}
    missing = [r for r in results if not r["present"]]
    if not missing:
        return {"kind": CHECK_KEPT, "passage": "", "reading": "", "confidence": 100, "reason": "word_for_word"}
    first = missing[0]
    return {"kind": CHECK_KEPT, "passage": first["passage"], "reading": first["reading"],
            "confidence": int(first["confidence"]), "reason": str(first.get("reason", ""))[:48]}


def cover_json(cover):
    return json.dumps(cover, sort_keys=True)
