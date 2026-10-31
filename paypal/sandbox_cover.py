"""One whole cover through RedLine's HTTP API, the way a person clicks it:
pin two rights, hold $20 with a sandbox test card, cut the refund window in
the vendor console, check, confirm, settle. Then PayPal's own record is read
back (when the PayPal keys are in the environment) and must agree with the
cover page: captured + released == held.

    python sandbox_cover.py https://<the server>            # a deployed server
    python sandbox_cover.py http://localhost:8000 --out deploy/sandbox-cover.json

Prints ids, statuses and amounts only.
"""

import argparse
import json
import os
import sys
import time

import httpx


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    http = httpx.Client(base_url=args.base.rstrip("/"), timeout=90)

    def call(method, path, **kw):
        r = http.request(method, path, **kw)
        if r.status_code >= 400:
            raise SystemExit("%s %s -> %d %s" % (method, path, r.status_code, r.text[:300]))
        return r.json()

    health = call("GET", "/api/health")
    vendor = call("POST", "/api/demo/vendors")
    t = vendor["token"]
    pins = [{k: s[k] for k in ("id", "text", "label")} for s in call("GET", "/api/vendors/%s/suggestions" % t)
            if s["id"] in ("refund", "deletion")]
    problems = call("POST", "/api/vendors/%s/pins/verify" % t, json={"passages": pins})
    assert problems == [], problems
    opened = call("POST", "/api/checkout", json={"vendor": t, "passages": pins})
    cover = call("POST", "/api/covers/%s/test-card" % opened["cover"]["token"])
    c = cover["token"]
    assert cover["state"] == "active", cover["state"]
    steps = [("held", cover)]

    time.sleep(4)
    steps.append(("check on the original terms", call("POST", "/api/covers/%s/check" % c)))
    call("PUT", "/api/demo/vendors/%s/version" % t, json={"version": "narrowed"})
    time.sleep(4)
    steps.append(("check after the refund window was cut", call("POST", "/api/covers/%s/check" % c)))
    time.sleep(4)
    final = call("POST", "/api/covers/%s/check" % c)
    steps.append(("confirming check", final))

    s, pp = final.get("settlement"), final["paypal"]
    record = {
        "server": {"mode": health.get("mode"), "panel": health.get("panel"), "build": health.get("build")},
        "cover": c[:8],
        "steps": [{"step": name, "state": v["state"],
                   "check": ({k: v["checks"][-1].get(k) for k in ("seq", "kind", "decidedBy", "reading", "suspected", "confirms")}
                             if v["checks"] else None)} for name, v in steps],
        "held_cents": final["amountCents"],
        "settlement": s,
        "paypal": {"order": pp["orderId"], "authorizations": pp["authorizations"],
                   "capture": pp.get("capture"), "void": pp.get("void")},
    }
    ok = (final["state"] == "breached" and s and s["vendorCents"] + s["releasedCents"] == final["amountCents"]
          and s["releasedCents"] > 0 and pp.get("capture") and pp.get("void"))

    if os.environ.get("PAYPAL_CLIENT_ID") and health.get("mode") == "sandbox":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from redline_paypal.paypal_api import RestPayPal

        paypal = RestPayPal(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"])
        auth = paypal.get_authorization(pp["authorizations"][-1]["id"])
        cap = paypal.get_capture(pp["capture"]["id"])
        record["read_back_from_paypal"] = {"authorization_status": auth.status, "authorized_cents": auth.amount_cents,
                                           "capture_status": cap.status, "captured_cents": cap.amount_cents}
        ok = ok and auth.status == "VOIDED" and cap.amount_cents == s["vendorCents"] and auth.amount_cents == final["amountCents"]

    record["result"] = "passed" if ok else "FAILED"
    text = json.dumps(record, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
