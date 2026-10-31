"""The cover's life, from checkout to settlement. The only writer of covers.

Read with docs/PAYPAL-ARCHITECTURE.md, sections 6 and 7:

- checkout is journaled: a cover is saved ``opening`` before PayPal is asked
  for anything, and an authorization whose cover never opened is voided by
  the sweep (6.5);
- the cover's money and state are redline_core's dict, stored whole; nothing
  here computes a share (6.1);
- a cut is suspected on its first reading and reported to redline_core only
  when a second check confirms it, as of the first (6.1);
- settlement captures the earned share and voids the rest through a journal
  of PayPal operations, each written before it is sent, with a deterministic
  PayPal-Request-Id, reconciled from PayPal's record before any retry; a
  capture after the 3-day honor period is preceded by a reauthorization (6.2-6.4);
- every cover is worked under a lease, so two workers never act on one (7).

PayPal appears only as ids, statuses and amounts.
"""

import contextlib
import hashlib
import json
import secrets
import time

from .core import core, prompts, text
from .paypal_api import PayPalError

HONOR_SECONDS = 3 * 86400
LEASE_SECONDS = 120
SWEEP_AFTER = 600  # an opening cover older than this is resolved from PayPal's record
ACCEPT_SECONDS = 3600
CHECK_NOW_GAP = 3


class CoverError(Exception):
    """A request the service refuses, with a sentence for people and an HTTP-like status."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def address(kind, value):
    """redline_core names parties by 0x addresses: a fixed hash of who they are."""
    return "0x" + hashlib.sha256(("%s:%s" % (kind, value)).encode()).hexdigest()[:40]


def money_text(cents):
    return "USD %d.%02d" % (cents // 100, cents % 100)


class Covers:
    def __init__(self, db, ledger, paypal, panel, read_page, *, clock=time.time, owner=None):
        """``read_page(url) -> (page_state, body_text)``: the demo's own pages in
        process, anything else through fetch.fetch."""
        self.db, self.ledger, self.paypal, self.panel, self.read_page = db, ledger, paypal, panel, read_page
        self.clock = clock
        self.owner = owner or "worker-" + secrets.token_hex(4)

    def now(self):
        return int(self.clock())

    # ------------------------------------------------------------ storage
    def load(self, token):
        row = self.db.execute(
            "SELECT token, vendor_token, state, amount_cents, currency, demo, created_at, core, extra, order_id, "
            "authorizations, next_check_at, version FROM covers WHERE token = ?", (token,)).fetchone()
        if not row:
            raise CoverError(404, "No cover with this link.")
        keys = ("token", "vendor_token", "state", "amount_cents", "currency", "demo", "created_at", "core", "extra",
                "order_id", "authorizations", "next_check_at", "version")
        c = dict(zip(keys, row))
        c["core"] = json.loads(c["core"]) if c["core"] else None
        c["extra"] = json.loads(c["extra"])
        c["authorizations"] = json.loads(c["authorizations"])
        return c

    def save(self, c):
        """One cover, one transaction, an optimistic version check: a write that
        lost a race fails rather than merging."""
        state = c["core"]["state"] if c["core"] else c["state"]
        c["state"] = state
        cur = self.db.execute(
            "UPDATE covers SET state = ?, core = ?, extra = ?, order_id = ?, authorizations = ?, next_check_at = ?, "
            "version = version + 1 WHERE token = ? AND version = ?",
            (state, json.dumps(c["core"], sort_keys=True) if c["core"] else "", json.dumps(c["extra"], sort_keys=True),
             c["order_id"], json.dumps(c["authorizations"]), c["next_check_at"], c["token"], c["version"]))
        if cur.rowcount != 1:
            raise CoverError(409, "The cover changed meanwhile; try again.")
        c["version"] += 1

    def lease(self, token):
        now = self.now()
        cur = self.db.execute(
            "UPDATE covers SET lease_owner = ?, lease_until = ? WHERE token = ? AND (lease_until IS NULL OR lease_until < ? "
            "OR lease_owner = ?)", (self.owner, now + LEASE_SECONDS, token, now, self.owner))
        return cur.rowcount == 1

    def release(self, token):
        self.db.execute("UPDATE covers SET lease_owner = NULL, lease_until = NULL WHERE token = ? AND lease_owner = ?",
                        (token, self.owner))

    @contextlib.contextmanager
    def leased(self, token):
        if not self.lease(token):
            raise CoverError(409, "This cover is being worked on; try again in a moment.")
        try:
            yield
        finally:
            self.release(token)

    def log(self, entry, **body):
        self.ledger.append(self.now(), entry, body)

    # ----------------------------------------------------------- checkout
    def start_checkout(self, vendor, passages):
        """Pins checked against the live page; the cover saved ``opening``; a
        PayPal order created for the buyer to approve. Nothing is held yet."""
        problems = self.pin_problems(vendor, passages)
        if problems:
            raise CoverError(422, " ".join(p["message"] for p in problems))
        page, body = self.read_page(vendor["terms_url"])
        visible = text.page_text(body)
        token = secrets.token_hex(12)
        extra = {
            "vendor": {k: vendor[k] for k in ("token", "name", "product", "terms_url")},
            "passages": [{"id": p["id"], "text": " ".join(p["text"].split()), "label": p.get("label") or p["id"],
                          "print": text.context_print(visible, p["text"])} for p in passages],
            "cover_seconds": vendor["cover_seconds"], "gap_seconds": vendor["gap_seconds"],
            "suspected": None, "last_record": None, "settlement": None,
        }
        now = self.now()
        self.db.execute("INSERT INTO covers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (token, vendor["token"], "opening", vendor["price_cents"], "USD", int(vendor["demo"]), now, "",
                         json.dumps(extra, sort_keys=True), "", "[]", None, None, None, 0))
        order_id = self.op(token, 0, "create_order", "", vendor["price_cents"], False,
                           lambda rid: self.paypal.create_order(amount_cents=vendor["price_cents"], currency="USD",
                                                                request_id=rid, description="%s: %s" % (vendor["name"], vendor["product"]))[0])
        c = self.load(token)
        c["order_id"] = order_id
        self.save(c)
        self.log("checkout_opened", cover=token[:8], order=order_id, amount_cents=c["amount_cents"],
                 passages=[p["id"] for p in extra["passages"]])
        return c

    def pin_problems(self, vendor, passages):
        out = []
        if not passages:
            out.append({"message": "Pin at least one right."})
        if len(passages) > core.MAX_PASSAGES:
            out.append({"message": "Pin at most %d rights." % core.MAX_PASSAGES})
        page, body = self.read_page(vendor["terms_url"])
        if page != core.PAGE_READ:
            return out + [{"message": "The vendor's terms page is not answering; nothing can be pinned now."}]
        visible = text.page_text(body)
        seen = set()
        for p in passages:
            err = text.passage_error(p.get("text", ""))
            if err:
                out.append({"passageId": p.get("id"), "message": err[0].upper() + err[1:] + "."})
            elif not text.passage_present(visible, p["text"]):
                out.append({"passageId": p.get("id"), "message": "Not on the page word for word."})
            n = text.normalize(p.get("text", ""))
            if n in seen:
                out.append({"passageId": p.get("id"), "message": "Pinned twice."})
            seen.add(n)
        return out

    def approve(self, token, order_id):
        """After the buyer approved the order in PayPal: authorize it, open the cover."""
        with self.leased(token):
            return self._approve(token, order_id)

    def _approve(self, token, order_id):
        c = self.load(token)
        if c["order_id"] != order_id:
            raise CoverError(409, "That order belongs to another checkout.")
        if c["state"] != "opening":
            return c
        hold = self.op(token, 1, "authorize", "", c["amount_cents"], False,
                       lambda rid: self.paypal.authorize_order(order_id, request_id=rid))
        return self.open(c, hold)

    def pay_with_test_card(self, token, card):
        """The sandbox test-card path: a card order is approved and authorized in one call."""
        with self.leased(token):
            return self._pay_with_test_card(token, card)

    def _pay_with_test_card(self, token, card):
        c = self.load(token)
        if c["state"] != "opening":
            return c
        v = c["extra"]["vendor"]

        def create(rid):
            order_id, _ = self.paypal.create_order(amount_cents=c["amount_cents"], currency="USD", request_id=rid,
                                                   description="%s: %s" % (v["name"], v["product"]), card=card)
            return order_id

        order_id = self.op(token, 1, "create_order_card", "", c["amount_cents"], False, create)
        c["order_id"] = order_id
        self.save(c)
        hold = self.op(token, 2, "authorize", "", c["amount_cents"], False,
                       lambda rid: self.paypal.authorize_order(order_id, request_id=rid))
        return self.open(self.load(token), hold)

    def open(self, c, hold):
        """The authorization exists: open the redline_core cover in one save. If
        this fails, the sweep voids the authorization (architecture 6.5)."""
        now = self.now()
        x = c["extra"]
        buyer, vendor = address("buyer", c["token"]), address("vendor", x["vendor"]["token"])
        passages = [{"id": p["id"], "text": p["text"]} for p in x["passages"]]
        errors = core.cover_errors(buyer=buyer, vendor=vendor, url=x["vendor"]["terms_url"], passages=passages,
                                   value=c["amount_cents"], coverage_seconds=x["cover_seconds"],
                                   accept_seconds=ACCEPT_SECONDS, check_gap_seconds=x["gap_seconds"],
                                   passage_error=text.passage_error)
        if errors:
            raise CoverError(422, "; ".join(errors))
        cv = core.open_cover(cover_id=int(now), buyer=buyer, vendor=vendor, url=x["vendor"]["terms_url"],
                             passages=passages, amount=c["amount_cents"], coverage_seconds=x["cover_seconds"],
                             accept_seconds=ACCEPT_SECONDS, check_gap_seconds=x["gap_seconds"], now=now)
        core.apply_pin(cv, ok=True, at=now, now=now)
        core.accept(cv, by=vendor, now=now)
        c["core"] = cv
        c["authorizations"] = [{"id": hold.id, "status": hold.status, "at": now}]
        c["next_check_at"] = now + x["gap_seconds"]
        self.save(c)
        self.log("authorized", cover=c["token"][:8], order=c["order_id"], authorization=hold.id, status=hold.status,
                 amount_cents=c["amount_cents"])
        return c

    # ---------------------------------------------------------- the journal
    def op(self, token, step, kind, authorization_id, amount, final, send):
        """Run one PayPal write through the journal: written before it is sent,
        under a deterministic request id, so a crash or retry never acts twice.
        ``send(request_id)`` returns the PayPal result; its id is recorded."""
        rid = "rl-%s-%d-%s-%s" % (token[:12], step, kind, (authorization_id or "x")[:17])
        row = self.db.execute("SELECT state, result_id FROM paypal_ops WHERE request_id = ?", (rid,)).fetchone()
        if row and row[0] == "done":
            return self.replay(kind, row[1])
        if row and row[0] == "declined":
            raise CoverError(409, "PayPal declined this step before; a person must resolve it.")
        if not row:
            self.db.execute("INSERT INTO paypal_ops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (rid, token, step, kind, authorization_id, amount, int(final), "planned", "", "", "",
                             self.now(), None))
        self.db.execute("UPDATE paypal_ops SET state = 'sent' WHERE request_id = ?", (rid,))
        try:
            result = send(rid)
        except PayPalError as exc:
            declined = 400 <= exc.status < 500 and exc.status not in (408, 409, 429)
            self.db.execute("UPDATE paypal_ops SET state = ?, error = ?, finished_at = ? WHERE request_id = ?",
                            ("declined" if declined else "unknown", "%s %s" % (exc.status, exc.name), self.now(), rid))
            raise CoverError(502 if not declined else 409, "PayPal did not complete this step: %s" % exc.name)
        except Exception as exc:
            self.db.execute("UPDATE paypal_ops SET state = 'unknown', error = ?, finished_at = ? WHERE request_id = ?",
                            (type(exc).__name__, self.now(), rid))
            raise CoverError(502, "PayPal could not be reached; nothing was done twice. Try again.")
        rid_out = result if isinstance(result, str) else result.id
        status = "" if isinstance(result, str) else result.status
        self.db.execute("UPDATE paypal_ops SET state = 'done', result_id = ?, paypal_status = ?, finished_at = ? "
                        "WHERE request_id = ?", (rid_out, status, self.now(), rid))
        return result

    def replay(self, kind, result_id):
        """A done op's result, read back from PayPal (never from a stored body)."""
        if kind in ("authorize", "reauthorize", "void"):
            return self.paypal.get_authorization(result_id)
        if kind == "capture":
            return self.paypal.get_capture(result_id)
        return result_id

    # -------------------------------------------------------------- checks
    def check(self, token, now=None, force=False):
        """One check of one active cover (under its lease)."""
        now = int(now if now is not None else self.now())
        c = self.load(token)
        if c["state"] != core.COVER_ACTIVE:
            return c
        if not force and (c["next_check_at"] or 0) > now:
            return c
        x = c["extra"]
        late = now > int(c["core"]["end"])
        if late and not x.get("suspected"):
            return self.deadlines(token, now)
        seq = self.db.execute("SELECT COUNT(*) FROM checks WHERE cover_token = ?", (token,)).fetchone()[0] + 1
        c["next_check_at"] = now + x["gap_seconds"]
        page, body = self.read_page(x["vendor"]["terms_url"])
        record = {"seq": seq, "at": now, "page": page, "votes": [], "decidedBy": "code"}

        if page != core.PAGE_READ:
            prev = x.get("last_record")
            rec = core.next_record(prev, seq=seq, page=page, finding={}, now=now)
            x["last_record"] = rec
            record.update(kind=rec["kind"], note=("No answer %d checks running: the page is gone." % core.ABSENT_LIMIT
                                                 if rec["kind"] == core.CHECK_GONE else
                                                 "No answer (%d of %d)." % (rec["streak"], core.ABSENT_LIMIT)))
            if x.get("suspected"):
                x["suspected"] = None  # a cut is confirmed only on a page that answered
                self.mark(x, None)
            if not late:
                core.apply_check(c["core"], seq=seq, kind=rec["kind"], at=now, since=rec["since"], now=now)
            return self.finish_check(c, record)

        visible = text.page_text(body)
        snapshot = hashlib.sha256(visible.encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO snapshots VALUES (?,?,?) ON CONFLICT (sha256) DO NOTHING", (snapshot, visible, now))
        record["snapshot"] = snapshot
        results, asked = [], None
        for p in x["passages"]:
            q = prompts.jury_question(visible, p["text"], p["print"])
            if not q:
                results.append({"passage": p["id"], "present": True, "reading": core.READ_SAME, "confidence": 100,
                                "reason": "word_for_word"})
                continue
            r = self.panel.read(q)
            reading = core.READ_CANNOT_TELL if r["contested"] else r["reading"]
            results.append({"passage": p["id"], "present": False, "reading": reading, "confidence": r["confidence"],
                            "reason": "contested" if r["contested"] else ""})
            asked = asked or {"passage": p["id"], **r}
            if core.reading_to_kind(reading, r["confidence"]) == core.CHECK_BREACH:
                asked = {"passage": p["id"], **r}
                break
        finding = core.decide(results)
        rec = core.next_record(x.get("last_record"), seq=seq, page=page, finding=finding, now=now)
        x["last_record"] = rec
        if asked:
            record.update(decidedBy="panel", passageId=asked["passage"], reading=asked["reading"],
                          confidence=asked["confidence"], contested=asked["contested"],
                          votes=[{k: v[k] for k in ("seat", "reading", "confidence") if k in v} | ({"error": v["error"]} if v.get("error") else {})
                                 for v in asked["votes"]])
        label = {p["id"]: p["label"] for p in x["passages"]}

        if finding["kind"] != core.CHECK_BREACH:
            dropped = x.get("suspected")
            x["suspected"] = None
            self.mark(x, None)
            record["kind"] = core.CHECK_KEPT
            if asked and asked["contested"]:
                record["note"] = "The panel disagreed. Disagreement is not a cut: kept, and asked again next check."
            elif asked:
                record["note"] = "The wording changed; the panel reads the right as still given."
            else:
                record["note"] = "Every pinned passage is on the page word for word, its surroundings unchanged. No model asked."
            if dropped:
                record["note"] = "Not confirmed: the suspected cut is dropped. " + record["note"]
            if not late:
                core.apply_check(c["core"], seq=seq, kind=core.CHECK_KEPT, at=now, since=now, now=now)
            return self.finish_check(c, record)

        pid = finding["passage"]
        if not x.get("suspected"):
            x["suspected"] = {"seq": seq, "at": now, "passage": pid}
            self.mark(x, pid, "suspected")
            record.update(kind=core.CHECK_BREACH, suspected=True,
                          note='Suspected: "%s" reads as %s. Not settled on one reading; a second check confirms.'
                          % (label[pid], finding["reading"]))
            return self.finish_check(c, record)

        first = x["suspected"]
        self.mark(x, pid, "cut")
        record.update(kind=core.CHECK_BREACH, confirms=first["seq"],
                      note='Confirmed: "%s" was cut. The vendor earned up to check %d; the rest is released.'
                      % (label[pid], first["seq"]))
        core.apply_check(c["core"], seq=first["seq"], kind=core.CHECK_BREACH, at=first["at"], since=first["at"], now=now)
        x["suspected"] = None
        return self.finish_check(c, record)

    @staticmethod
    def mark(x, pid, status=None):
        for p in x["passages"]:
            if status and p["id"] == pid:
                p["status"] = status
            elif p.get("status") != "cut":
                p["status"] = "holding"

    def finish_check(self, c, record):
        self.db.execute("INSERT INTO checks VALUES (?,?,?,?)", (c["token"], record["seq"], record["at"],
                                                               json.dumps(record, sort_keys=True)))
        self.save(c)
        self.log("check", cover=c["token"][:8], seq=record["seq"], page=record["page"], result=record["kind"],
                 by=record["decidedBy"], suspected=bool(record.get("suspected")), confirms=record.get("confirms"),
                 passage=record.get("passageId"), snapshot=record.get("snapshot"))
        return self.deadlines(c["token"], record["at"])

    def check_now(self, token):
        """The demo's "Check now": a check at once, or the pending confirmation."""
        with self.leased(token):
            c = self.load(token)
            if c["state"] != core.COVER_ACTIVE:
                return self.deadlines(token)
            last = self.db.execute("SELECT MAX(at) FROM checks WHERE cover_token = ?", (token,)).fetchone()[0]
            if last is not None and self.now() - int(last) < CHECK_NOW_GAP:
                raise CoverError(429, "A check just ran. Try again in a few seconds.")
            return self.check(token, force=True)

    def catch_up(self, token):
        """A read of a cover runs what fell due (a server woken from sleep)."""
        c = self.load(token)
        if c["state"] in (core.COVER_ACTIVE, core.COVER_BREACHED, core.COVER_COMPLETED) and not c["extra"].get("settlement"):
            if (c["next_check_at"] or 0) <= self.now() or c["state"] != core.COVER_ACTIVE or self.now() > int(c["core"]["end"]):
                if self.lease(token):
                    try:
                        return self.check(token) if c["state"] == core.COVER_ACTIVE else self.deadlines(token)
                    except CoverError:
                        pass
                    finally:
                        self.release(token)
        return self.load(token)

    # ---------------------------------------------------------- settlement
    def deadlines(self, token, now=None):
        """redline_core's clocks; a cover it closes is settled through PayPal."""
        now = int(now if now is not None else self.now())
        c = self.load(token)
        if c["core"] is None:
            return c
        if c["state"] == core.COVER_ACTIVE:
            x = c["extra"]
            # A cut found once is not a cut: hold the end until it is confirmed or dropped.
            if x.get("suspected"):
                if now > int(c["core"]["end"]):
                    return self.check(token, now=now, force=True)
                return c  # nothing accrues while a cut waits for its confirmation
            core.apply_deadlines(c["core"], now, 0)
            self.save(c)
        if c["state"] in (core.COVER_BREACHED, core.COVER_COMPLETED) and not c["extra"].get("settlement"):
            return self.settle(c)
        return c

    def settle(self, c):
        """Capture the earned share, void the rest (architecture 6.2). Each step
        is journaled; a finished step is never sent again."""
        cv, x = c["core"], c["extra"]
        vendor_cents, released = int(cv["paid"]), int(cv.get("refunded", 0))
        auth = c["authorizations"][-1]
        now = self.now()
        if vendor_cents > 0 and now - int(auth["at"]) > HONOR_SECONDS:
            new = self.op(c["token"], 10, "reauthorize", auth["id"], c["amount_cents"], False,
                          lambda rid: self.paypal.reauthorize(auth["id"], request_id=rid))
            auth = {"id": new.id, "status": new.status, "at": now}
            c["authorizations"].append(auth)
            self.save(c)
        capture = None
        if vendor_cents > 0:
            capture = self.op(c["token"], 11, "capture", auth["id"], vendor_cents, released == 0,
                              lambda rid: self.paypal.capture(auth["id"], amount_cents=vendor_cents, currency="USD",
                                                              final=released == 0, request_id=rid))
        void = None
        if released > 0:
            void = self.op(c["token"], 12, "void", auth["id"], released, False,
                           lambda rid: self.paypal.void(auth["id"], request_id=rid))
        hold = self.paypal.get_authorization(auth["id"])
        auth["status"] = hold.status
        reason = "held" if cv["state"] == core.COVER_COMPLETED else (
            "gone" if (x.get("last_record") or {}).get("kind") == core.CHECK_GONE else "cut")
        x["settlement"] = {"vendorCents": vendor_cents, "releasedCents": released,
                           "asOf": int(cv.get("closed_as_of", cv.get("end", now))), "reason": reason,
                           "capture": {"id": capture.id, "status": capture.status, "amountCents": capture.amount_cents} if capture else None,
                           "void": {"id": auth["id"], "status": hold.status} if void is not None else None}
        c["next_check_at"] = None
        self.save(c)
        self.log("settled", cover=c["token"][:8], reason=reason, authorization=auth["id"],
                 capture=capture.id if capture else None, captured_cents=vendor_cents, released_cents=released,
                 authorization_status=hold.status)
        return c

    # ---------------------------------------------------------------- tick
    def sweep(self, now=None):
        """Covers stuck ``opening``: void any authorization PayPal holds for them."""
        now = int(now if now is not None else self.now())
        rows = self.db.execute("SELECT token, order_id FROM covers WHERE state = 'opening' AND created_at < ?",
                               (now - SWEEP_AFTER,)).fetchall()
        for token, order_id in rows:
            if not self.lease(token):
                continue
            try:
                c = self.load(token)
                held = self.paypal.order_authorization(order_id) if order_id else None
                if held and held.status in ("CREATED", "PENDING"):
                    self.op(token, 20, "void", held.id, c["amount_cents"], False,
                            lambda rid: self.paypal.void(held.id, request_id=rid))
                c["state"] = "abandoned"
                self.save(c)
                self.log("abandoned", cover=token[:8], order=order_id or None,
                         voided=held.id if held and held.status in ("CREATED", "PENDING") else None)
            except Exception:
                pass  # tried again next tick
            finally:
                self.release(token)

    def tick(self, now=None, *, demo_checks=True, limit=50):
        """Everything due: the sweep, then each active cover's check and clocks.
        ``demo_checks=False`` (the scheduled worker) never reads demo pages."""
        now = int(now if now is not None else self.now())
        self.sweep(now)
        sql = "SELECT token, demo FROM covers WHERE state = ? AND (next_check_at IS NULL OR next_check_at <= ?) LIMIT ?"
        done = []
        for token, demo in self.db.execute(sql, (core.COVER_ACTIVE, now, limit)).fetchall():
            if not self.lease(token):
                continue
            try:
                if demo and not demo_checks:
                    self.deadlines(token, now)
                else:
                    self.check(token, now)
                done.append(token)
            except CoverError:
                pass  # PayPal or a race: the journal and the lease make the next tick safe
            finally:
                self.release(token)
        # Covers whose end passed between checks, and closed covers not yet settled.
        for (token,) in self.db.execute(
                "SELECT token FROM covers WHERE state IN (?,?,?) LIMIT ?",
                (core.COVER_ACTIVE, core.COVER_BREACHED, core.COVER_COMPLETED, limit)).fetchall():
            c = self.load(token)
            if c["extra"].get("settlement") or token in done:
                continue
            if c["state"] == core.COVER_ACTIVE and int(c["core"]["end"]) > now:
                continue
            if self.lease(token):
                try:
                    self.deadlines(token, now)
                except CoverError:
                    pass
                finally:
                    self.release(token)
        return done

    # ---------------------------------------------------------------- view
    def view(self, c):
        """The cover as the web app's ``Cover`` type."""
        cv, x, now = c["core"], c["extra"], self.now()
        checks = [json.loads(b) for (b,) in self.db.execute(
            "SELECT body FROM checks WHERE cover_token = ? ORDER BY seq", (c["token"],)).fetchall()]
        if cv is None:
            earned_cents = 0
        elif c["state"] == core.COVER_ACTIVE:
            at = core.accrual_cap(cv, now)
            if x.get("suspected"):
                at = min(at, int(x["suspected"]["at"]))
            earned_cents = max(int(cv["paid"]), core.earned(cv, at))
        else:
            earned_cents = int(cv["paid"])
        s = x.get("settlement")
        paypal = {"orderId": c["order_id"], "authorizations": [{"id": a["id"], "status": a["status"]} for a in c["authorizations"]]}
        if s and s.get("capture"):
            paypal["capture"] = s["capture"]
        if s and s.get("void"):
            paypal["void"] = s["void"]
        out = {
            "token": c["token"],
            "vendor": {"name": x["vendor"]["name"], "product": x["vendor"]["product"],
                       "termsUrl": x["vendor"]["terms_url"], "token": x["vendor"]["token"]},
            "state": c["state"],
            "amountCents": c["amount_cents"],
            "currency": c["currency"],
            "createdAt": c["created_at"],
            "coverSeconds": x["cover_seconds"],
            "checkGapSeconds": x["gap_seconds"],
            "passages": [{"id": p["id"], "text": p["text"], "label": p["label"], "status": p.get("status", "holding")}
                         for p in x["passages"]],
            "checks": checks,
            "earnedCents": earned_cents,
            "paypal": paypal,
            "demo": bool(c["demo"]),
        }
        if cv is not None and cv.get("start") is not None:
            out["start"], out["end"] = int(cv["start"]), int(cv["end"])
        if c["state"] == core.COVER_ACTIVE and c["next_check_at"]:
            out["nextCheckAt"] = int(c["next_check_at"])
        if s:
            out["settlement"] = {k: s[k] for k in ("vendorCents", "releasedCents", "asOf", "reason")}
        return out

    def vendor_covers(self, vendor_token, limit=50):
        rows = self.db.execute("SELECT token FROM covers WHERE vendor_token = ? AND state != 'opening' "
                               "ORDER BY created_at DESC LIMIT ?", (vendor_token, limit)).fetchall()
        return [self.view(self.catch_up(t)) for (t,) in rows]
