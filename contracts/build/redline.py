# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

import datetime
import hashlib
import json

# ---------------------------------------------------------------------------
# GENERATED FILE - do not edit.
# Built by deploy/build_contract.py from contracts/redline_text.py (page text),
# contracts/redline_core.py (the rules) and, for the treasury,
# treasury_shell.py; for the watcher, redline_prompts.py and watcher_shell.py.
# ---------------------------------------------------------------------------


# --- redline_text.py ---------------------------------------------------

# Elements whose content is never visible text.
HIDDEN_ELEMENTS = ("script", "style", "noscript", "template", "svg", "head", "iframe")

ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " ",
    "rsquo": "'", "lsquo": "'", "rdquo": '"', "ldquo": '"', "ndash": "-", "mdash": "-",
    "hellip": "...", "shy": "", "middot": "*", "bull": "*",
}

# Typographic characters folded to their plain form, so that "30‑day" and
# "30-day", or curly and straight quotes, compare equal.
FOLD = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "​": "", "‌": "", "‍": "", "﻿": "", "­": "",
    "…": "...",
}

MAX_PAGE_BYTES = 2_000_000  # a terms page larger than this is cut, never parsed whole
MIN_PASSAGE = 40  # characters, after normalisation: a pinned passage must say something
MAX_PASSAGE = 600


def _decode_entity(name):
    if name.startswith("#"):
        try:
            code = int(name[2:], 16) if name[1:2] in ("x", "X") else int(name[1:])
            if 0 < code < 0x110000:
                return chr(code)
        except ValueError:
            return None
        return None
    return ENTITIES.get(name.lower())


def unescape(text):
    """HTML character references, decoded without the ``html`` module."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "&":
            end = text.find(";", i + 1, i + 12)
            if end != -1:
                decoded = _decode_entity(text[i + 1 : end])
                if decoded is not None:
                    out.append(decoded)
                    i = end + 1
                    continue
        out.append(ch)
        i += 1
    return "".join(out)


VOID_ELEMENTS = ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr")

# Class names that hide an element in the common CSS frameworks. An element
# that a responsive class shows at some screen size ("hidden md:block") is not hidden.
HIDING_CLASSES = ("hidden", "d-none", "sr-only", "visually-hidden", "invisible", "screen-reader-text")

HIDING_STYLES = ("display:none", "visibility:hidden", "font-size:0;", "font-size:0px", "opacity:0;")


def _attr(tag, name):
    """One attribute of an opening tag normalised by ``is_hidden`` ("" if absent)."""
    at = tag.find(" " + name + "=")
    if at == -1:
        return ""
    v = tag[at + len(name) + 2 :]
    if v[:1] in ("'", '"'):
        end = v.find(v[0], 1)
        return v[1:end] if end != -1 else v[1:]
    return v.split(" ")[0]


def _bare(tag):
    """The tag with every quoted value removed, to find bare attributes."""
    out = []
    quote = ""
    for ch in tag:
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        else:
            out.append(ch)
    return "".join(out).replace("/", " ") + " "


def hidden_selectors(html):
    """Classes and ids that the page's own <style> blocks hide: rules whose
    selector is a bare ``.name`` or ``#name`` and whose body hides it."""
    found = set()
    for block in html.lower().split("<style")[1:]:
        css = block[block.find(">") + 1 : block.find("</style")]
        for rule in css.split("}"):
            head, _, body = rule.rpartition("{")
            body = "".join(body.split())
            if "display:none" in body or "visibility:hidden" in body:
                for sel in head[head.rfind("{") + 1 :].split(","):
                    sel = sel.strip()
                    if len(sel) > 1 and sel[0] in ".#" and all(c.isalnum() or c in "-_" for c in sel[1:]):
                        found.add(sel)
    return found


def is_hidden(name, tag, hidden):
    """Does this opening tag (lower case) hide what it contains from a reader?"""
    tag = " " + " ".join(tag.replace("=", " = ").split()).replace(" = ", "=")
    if name in HIDDEN_ELEMENTS or " hidden " in _bare(tag).replace("=", " ") or _attr(tag, "aria-hidden") == "true":
        return True
    style = "".join(_attr(tag, "style").split()) + ";"
    if any(rule in style for rule in HIDING_STYLES) or "#" + _attr(tag, "id") in hidden:
        return True
    classes = _attr(tag, "class").split()
    if any(":" in c and not c.endswith(("hidden", "none")) for c in classes):
        return False  # shown at some screen size ("hidden md:block")
    return any(c in HIDING_CLASSES or "." + c in hidden for c in classes)


def strip_markup(html):
    """Visible text of an HTML document: tags become spaces; comments, and the
    content of every element a reader would not see (script, style, an element
    marked hidden, hidden by an inline style, or hidden by a class), are
    dropped. A plain-text page passes through."""
    lower = html.lower()
    hidden = hidden_selectors(html)
    out = []
    i = 0
    n = len(html)
    while i < n:
        lt = html.find("<", i)
        if lt == -1:
            out.append(html[i:])
            break
        out.append(html[i:lt])
        if html.startswith("<!--", lt):
            end = html.find("-->", lt + 4)
            i = n if end == -1 else end + 3
            continue
        gt = html.find(">", lt + 1)
        if gt == -1:
            break
        tag = lower[lt + 1 : gt].strip()
        name = ""
        for ch in tag:
            if ch.isalnum() or ch == "-":
                name += ch
            else:
                break
        out.append(" ")
        i = gt + 1
        if not name or name in VOID_ELEMENTS or tag.endswith("/") or not is_hidden(name, tag, hidden):
            continue
        # Skip to the matching close tag, counting nested elements of the same name.
        depth = 1
        while depth > 0:
            nxt = lower.find("<" + name, i)
            close = lower.find("</" + name, i)
            if close == -1:
                i = n
                break
            if nxt != -1 and nxt < close and not lower[nxt + 1 + len(name) : nxt + 2 + len(name)].isalnum():
                depth += 1
                i = nxt + 1
                continue
            depth -= 1
            end = lower.find(">", close)
            i = n if end == -1 else end + 1
    return "".join(out)


def normalize(text):
    """The comparable form of a piece of text: entities decoded, typography
    folded, lower case, every run of whitespace a single space."""
    text = unescape(str(text))
    folded = []
    for ch in text:
        folded.append(FOLD.get(ch, ch))
    return " ".join("".join(folded).lower().split())


def page_text(raw):
    """The normalised visible text of a fetched page (bytes or str)."""
    if isinstance(raw, bytes):
        raw = raw[:MAX_PAGE_BYTES].decode("utf-8", "replace")
    else:
        raw = str(raw)[:MAX_PAGE_BYTES]
    head = raw.lstrip()[:200].lower()
    if head.startswith("<") or "<html" in head or "<!doctype" in head:
        raw = strip_markup(raw)
    return normalize(raw)


def passage_present(text, passage):
    """Is the pinned passage still on the page, word for word (both normalised)?"""
    p = normalize(passage)
    return p != "" and p in text


def passage_error(passage):
    """Why a passage cannot be pinned ("" if it can)."""
    p = normalize(passage)
    if len(p) < MIN_PASSAGE:
        return "a pinned passage must be at least %d characters" % MIN_PASSAGE
    if len(p) > MAX_PASSAGE:
        return "a pinned passage must be at most %d characters" % MAX_PASSAGE
    return ""


def _words(text):
    out = []
    word = ""
    for ch in text:
        if ch.isalnum():
            word += ch
        else:
            if word:
                out.append(word)
            word = ""
    if word:
        out.append(word)
    return out


CONTEXT = 60  # words either side of a pinned passage that must stay as they were
WHOLE_PAGE = 12000  # a page this short is shown to the jury whole
EXCERPT = 2000  # otherwise, up to three windows this wide


DATE_WORDS = set("january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday".split())


def _letters(text):
    """Words only: digits, punctuation, symbols, and month and day names
    dropped, so dates, counters and version numbers near a passage do not count."""
    return " ".join(w for w in "".join(c if c.isalpha() else " " for c in text).split() if w not in DATE_WORDS)


def _significant(text):
    return set(w for w in _words(text) if len(w) > 4 and w.isalpha())


def context_print(text, passage):
    """A fingerprint of everything that could qualify a pinned passage: the
    text either side of every place it appears, and every sentence on the page
    that shares three or more of its long words. "" if it is not on the page.
    A passage still there word for word counts as kept without a model only if
    this is unchanged since pinning."""
    p = normalize(passage)
    if not p or p not in text:
        return ""
    parts = []
    at = text.find(p)
    while at != -1:
        before = _letters(text[max(0, at - 30 * CONTEXT) : at]).split()[-CONTEXT:]
        parts.append(" ".join(before) + "|" + " ".join(_letters(text[at + len(p) : at + len(p) + 30 * CONTEXT]).split()[:CONTEXT]))
        at = text.find(p, at + 1)
    words = _significant(p)
    for sentence in text.replace(p, " ").replace("? ", ". ").replace("; ", ". ").split(". "):
        if len(words.intersection(_significant(sentence))) >= 3:
            parts.append(_letters(sentence))
    h = 14695981039346656037
    for ch in "#".join(parts):
        h = ((h ^ ord(ch)) * 1099511628211) % 18446744073709551616
    return "%016x" % h


def excerpts(text, passage):
    """What the jury is shown of the current page. A short page whole.
    Otherwise up to three non-overlapping windows: the one centred on the
    passage if it is still there, then those sharing the most distinct words
    with it. Deterministic."""
    if len(text) <= WHOLE_PAGE:
        return [text] if text else []
    w = EXCERPT
    p = normalize(passage)
    at = text.find(p) if p else -1
    out = [] if at == -1 else [max(0, min(len(text) - w, at + len(p) // 2 - w // 2))]
    wanted = set(x for x in _words(p) if len(x) > 2)
    scored = sorted(((len(wanted.intersection(_words(text[i : i + w]))), -i) for i in range(0, len(text) - w // 4 * 3, w // 4)), reverse=True)
    for score, neg in scored:
        if len(out) < 3 and (score or not out) and all(abs(-neg - o) >= w for o in out):
            out.append(-neg)
    return [text[o : o + w] for o in out]


# --- redline_core.py ---------------------------------------------------

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
# No agreed observation by the end of the window: validators could not agree
# on what the page says (a page shown differently to different readers), or
# no round completed. Counted exactly like a page that does not answer.
PAGE_CONTESTED = "contested"
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


def url_error(url):
    """Why a terms page URL cannot be pinned ("" if it can). Every validator
    fetches it and it is stored in public, so it must be a plain https address:
    no query, fragment, user name or password that could carry a secret."""
    u = str(url).strip()
    if not u.startswith("https://") or len(u) > MAX_URL:
        return "the terms page must be an https URL of at most %d characters" % MAX_URL
    host = u[8:].split("/")[0]
    for ch in u:
        if ch.isspace() or ch in "?#" or ord(ch) < 33 or ord(ch) > 126:
            return "the terms page URL may not contain a query (?), a fragment (#), spaces or non-ASCII characters"
    if "@" in host or "." not in host or host.startswith(".") or host.endswith("."):
        return "the terms page URL must name a host, with no user name or password"
    return ""


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
    e = url_error(url)
    if e:
        errors.append(e)
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


def observe_window(gap):
    """How long a requested check stays open for an agreed observation: half
    the gap, so a contested check is settled before the next may be asked."""
    return max(30, int(gap) // 2)


def request_error(*, pending, last_request_at, now, gap, end):
    """Why a check may not be requested now ("" if it may)."""
    if pending:
        return "a check is open until %d" % int(pending["due"])
    if last_request_at and int(now) < int(last_request_at) + int(gap):
        return "the next check may be requested from %d" % (int(last_request_at) + int(gap))
    if int(now) + observe_window(gap) > int(end):
        return "too close to the end of the cover"
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


# --- treasury_shell.py -------------------------------------------------

@gl.evm.contract_interface
class _Payee:
    """Any address, as a value recipient."""

    class View:
        pass

    class Write:
        pass


class RedLine(gl.Contract):
    release: str
    watcher: str
    appeal_seconds: u256
    cover_count: u256
    covers: TreeMap[u256, str]
    owed: TreeMap[str, u256]
    owed_total: u256
    held: u256
    refusals: TreeMap[str, str]

    def __init__(self, watcher: str, appeal_seconds: int):
        if int(appeal_seconds) < 0 or int(appeal_seconds) > MAX_WINDOW:
            raise Exception("[EXPECTED] the appeal window is 0-%d seconds" % MAX_WINDOW)
        self.release = "redline/2"
        self.watcher = normalize_address(watcher, "watcher")
        self.appeal_seconds = u256(int(appeal_seconds))
        self.cover_count = u256(0)
        self.owed_total = u256(0)
        self.held = u256(0)

    # -------------------------------------------------------------- helpers

    def _now(self) -> int:
        return int(datetime.datetime.now().timestamp())

    def _me(self) -> str:
        return str(gl.message.sender_address).lower()

    def _load(self, cover_id: int) -> dict:
        if int(cover_id) < 0 or int(cover_id) >= int(self.cover_count):
            raise Exception("[EXPECTED] unknown cover")
        return json.loads(self.covers[u256(int(cover_id))])

    def _save(self, cover: dict) -> None:
        self.covers[u256(int(cover["id"]))] = json.dumps(cover)

    def _pay(self, credits: dict) -> None:
        """Move credited GEN from held prepay to what each party is owed."""
        total = 0
        for who, amount in credits.items():
            key = str(who).lower()
            self.owed[key] = u256(int(self.owed.get(key, u256(0))) + int(amount))
            total += int(amount)
        self.held = u256(int(self.held) - total)
        self.owed_total = u256(int(self.owed_total) + total)

    def _refuse(self, reason: str, value: int) -> None:
        me = self._me()
        if value > 0:
            self.owed[me] = u256(int(self.owed.get(me, u256(0))) + value)
            self.owed_total = u256(int(self.owed_total) + value)
        self.refusals[me] = json.dumps({"reason": str(reason)[:600], "at": self._now(), "returned": value})

    def _from_watcher(self) -> None:
        if self._me() != self.watcher:
            raise Exception("[EXPECTED] only the watcher contract reports on a cover")

    # ---------------------------------------------------------- entrypoints

    @gl.public.write.payable
    def open_cover(self, vendor: str, url: str, passages_json: str, coverage_seconds: int, accept_seconds: int,
                   check_gap_seconds: int) -> int:
        """The buyer prepays a vendor and pins the passages of its terms page it
        relies on. The value sent is the prepay. Returns the cover id, or -1
        when refused - the value is then credited back and ``refusal_of`` says
        why. A funded cover asks the watcher to pin the page at once."""
        value = int(gl.message.value)
        try:
            passages = json.loads(str(passages_json))
        except Exception:
            passages = None
        errors = ["the passages are not valid JSON"] if passages is None else cover_errors(
            buyer=self._me(), vendor=str(vendor), url=str(url), passages=passages, value=value,
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), passage_error=passage_error,
        )
        if errors:
            self._refuse("; ".join(errors), value)
            return -1
        cover_id = int(self.cover_count)
        cover = open_cover(
            cover_id=cover_id, buyer=self._me(), vendor=str(vendor), url=str(url), passages=passages, amount=value,
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), now=self._now(),
        )
        self._save(cover)
        self.cover_count = u256(cover_id + 1)
        self.held = u256(int(self.held) + value)
        # A message, not a read: if the watcher fails, the cover simply is not
        # pinned and refunds at its acceptance deadline.
        gl.get_contract_at(Address(self.watcher)).emit(on="accepted").pin(str(self.address).lower(), cover_id)
        return cover_id

    @gl.public.write
    def note_pin(self, cover_id: int, ok: bool, at: int, reason: str) -> None:
        """Sent by the watcher once it has fetched the page at funding."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            credits = apply_pin(cover, ok=bool(ok), at=int(at), now=self._now(), reason=str(reason))
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def accept(self, cover_id: int) -> None:
        """The vendor accepts the pinned terms; the cover starts now."""
        cover = self._load(cover_id)
        try:
            accept(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)

    @gl.public.write
    def cancel(self, cover_id: int) -> None:
        """The buyer withdraws an offer the vendor has not accepted."""
        cover = self._load(cover_id)
        try:
            credits = cancel(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def note_check(self, cover_id: int, seq: int, kind: str, at: int, since: int) -> None:
        """Sent by the watcher after each check of the page."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            credits = apply_check(cover, seq=int(seq), kind=str(kind), at=int(at), since=int(since), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def settle(self, cover_id: int) -> None:
        """Apply every clock of a cover. Anyone may call it; it reads no other
        contract, so a cover always resolves."""
        cover = self._load(cover_id)
        credits = apply_deadlines(cover, self._now(), int(self.appeal_seconds))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def withdraw(self) -> None:
        """Send the caller everything it is owed."""
        me = self._me()
        amount = int(self.owed.get(me, u256(0)))
        if amount <= 0:
            raise Exception("[EXPECTED] nothing is owed to this address")
        self.owed[me] = u256(0)
        self.owed_total = u256(int(self.owed_total) - amount)
        _Payee(gl.message.sender_address).emit_transfer(value=u256(amount))

    # ---------------------------------------------------------------- views

    @gl.public.view
    def get_cover(self, cover_id: int) -> str:
        cover = self._load(cover_id)
        cover["now"] = self._now()
        cover["outstanding"] = outstanding(cover)
        return json.dumps(cover)

    @gl.public.view
    def owed_to(self, address: str) -> int:
        return int(self.owed.get(str(address).lower(), u256(0)))

    @gl.public.view
    def refusal_of(self, address: str) -> str:
        return self.refusals.get(str(address).lower(), "{}")

    @gl.public.view
    def status(self) -> str:
        return json.dumps(
            {
                "release": self.release,
                "watcher": self.watcher,
                "appeal_seconds": int(self.appeal_seconds),
                "covers": int(self.cover_count),
                "held": int(self.held),
                "owed": int(self.owed_total),
                "balance": int(self.balance),
            }
        )
