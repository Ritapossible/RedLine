"""The day-one sandbox spike: prove the money path before building on it.

    PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=... python spike.py [record.json]

On the PayPal sandbox, with a sandbox test card (no buyer step):

1. Hold $20.00 (an order with intent AUTHORIZE).
2. Capture $7.50 with final_capture false, then void the rest. Read the
   authorization and the capture back from PayPal: captured + released must
   equal the hold, and the hold must end VOIDED.
3. A second hold: capture $7.50 with final_capture true. Does PayPal release
   the remaining $12.50 by itself (the authorization's status), and does a
   void afterwards succeed or fail?
4. A third hold: reauthorize it at once, inside the honor period. PayPal
   should refuse; record its error name.
5. A fourth hold, voided whole: a hold with no capture releases everything.

Prints, and optionally writes, a record of ids, statuses and amounts only:
no PayPal response bodies (they carry the payer's name and email). Exits
non-zero if the money does not add up.
"""

import json
import os
import secrets
import sys
import time

from redline_paypal.paypal_api import PayPalError, RestPayPal

CARD = {"number": "4111111111111111", "expiry": "2030-12", "security_code": "123", "name": "RedLine Spike"}
HOLD, SHARE = 2000, 750


def main(argv=sys.argv, env=os.environ, paypal=None):
    paypal = paypal or RestPayPal(env.get("PAYPAL_CLIENT_ID", ""), env.get("PAYPAL_CLIENT_SECRET", ""))
    run = "spike-" + secrets.token_hex(4)
    rid = lambda step: "%s-%s" % (run, step)  # noqa: E731
    record = {"run": run, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "hold_cents": HOLD, "steps": {}}
    ok = True

    def new_hold(step):
        order_id, status = paypal.create_order(amount_cents=HOLD, currency="USD", request_id=rid(step + "-order"),
                                               description="RedLine sandbox spike", card=CARD)
        h = paypal.authorize_order(order_id, request_id=rid(step + "-authorize"))
        return order_id, status, h

    # 1-2: partial capture, then void
    order_id, order_status, h = new_hold("partial")
    c = paypal.capture(h.id, amount_cents=SHARE, currency="USD", final=False, request_id=rid("partial-capture"))
    after_capture = paypal.get_authorization(h.id)
    v = paypal.void(h.id, request_id=rid("partial-void"))
    after_void = paypal.get_authorization(h.id)
    captured = paypal.get_capture(c.id)
    released = after_void.amount_cents - captured.amount_cents if after_void.status == "VOIDED" else None
    adds_up = after_void.status == "VOIDED" and captured.amount_cents + (released or 0) == h.amount_cents
    ok &= adds_up
    record["steps"]["partial_capture_then_void"] = {
        "order": order_id, "order_status_on_create": order_status,
        "authorization": h.id, "authorized_cents": h.amount_cents, "authorization_status": h.status,
        "expires": h.expires, "capture": c.id, "capture_status": captured.status, "captured_cents": captured.amount_cents,
        "status_after_capture": after_capture.status, "status_after_void": after_void.status,
        "void_answer_status": v.status, "released_cents": released, "adds_up": adds_up}

    # 3: does final_capture=true release the rest?
    _, _, h2 = new_hold("final")
    c2 = paypal.capture(h2.id, amount_cents=SHARE, currency="USD", final=True, request_id=rid("final-capture"))
    after_final = paypal.get_authorization(h2.id)
    try:
        paypal.void(h2.id, request_id=rid("final-void"))
        void_after_final = "succeeded"
    except PayPalError as exc:
        void_after_final = "refused: %s" % exc.name
    record["steps"]["final_capture_true_partial"] = {
        "authorization": h2.id, "capture": c2.id, "captured_cents": c2.amount_cents,
        "status_after_final_capture": after_final.status, "void_afterwards": void_after_final,
        "status_at_end": paypal.get_authorization(h2.id).status}

    # 4: reauthorize inside the honor period
    _, _, h3 = new_hold("reauth")
    try:
        h3b = paypal.reauthorize(h3.id, request_id=rid("reauth-reauthorize"))
        reauth = {"result": "accepted", "new_authorization": h3b.id, "new_status": h3b.status}
    except PayPalError as exc:
        reauth = {"result": "refused", "status": exc.status, "error": exc.name, "debug_id": exc.debug_id}
    paypal.void(reauth.get("new_authorization") or h3.id, request_id=rid("reauth-void"))  # leave no hold behind
    record["steps"]["reauthorize_inside_honor_period"] = dict(reauth, authorization=h3.id)

    # 5: a hold voided whole
    _, _, h4 = new_hold("whole")
    paypal.void(h4.id, request_id=rid("whole-void"))
    end4 = paypal.get_authorization(h4.id)
    ok &= end4.status == "VOIDED"
    record["steps"]["void_whole_hold"] = {"authorization": h4.id, "status_at_end": end4.status}

    record["money_adds_up"] = bool(ok)
    text = json.dumps(record, indent=2)
    print(text)
    if len(argv) > 1:
        with open(argv[1], "w") as f:
            f.write(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
