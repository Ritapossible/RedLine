"""A stateful stand-in for PayPal's sandbox: orders with intent AUTHORIZE,
authorizations, captures, voids and reauthorizations, with idempotent
writes. Its semantics follow PayPal's documentation; where the docs are
silent (what a final capture does to the rest), the spike records the real
answer and this fake is corrected to match."""

import itertools
import json

import httpx


class FakeSandbox:
    def __init__(self, honor_seconds=3 * 86400, clock=None):
        self.ids = itertools.count(1)
        self.orders, self.auths, self.captures, self.seen = {}, {}, {}, {}
        self.honor, self.clock = honor_seconds, clock or (lambda: 0)

    def __call__(self, request):
        path, method = request.url.path, request.method
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        rid = request.headers.get("paypal-request-id")
        if method == "POST":
            assert rid, "every write carries a PayPal-Request-Id"
            if rid in self.seen:
                return self.seen[rid]
        body = json.loads(request.content) if request.content else {}
        resp = self.route(method, path, body)
        if method == "POST" and resp.status_code < 400:
            self.seen[rid] = resp
        return resp

    def new_auth(self, value):
        aid = "A%04d" % next(self.ids)
        self.auths[aid] = {"id": aid, "status": "CREATED", "amount": value, "captured": 0, "at": self.clock(),
                           "create_time": "2026-10-29T00:00:00Z", "expiration_time": "2026-11-27T00:00:00Z"}
        return aid

    def auth_json(self, aid):
        a = self.auths[aid]
        return {k: a[k] for k in ("id", "status", "amount", "create_time", "expiration_time")}

    def route(self, method, path, body):
        p = path.strip("/").split("/")
        if method == "POST" and path == "/v2/checkout/orders":
            oid = "O%04d" % next(self.ids)
            unit = body["purchase_units"][0]
            o = {"id": oid, "status": "CREATED", "purchase_units": [{"amount": unit["amount"], "payments": {}}]}
            if "card" in body.get("payment_source", {}):
                aid = self.new_auth(unit["amount"])
                o["status"] = "COMPLETED"
                o["purchase_units"][0]["payments"]["authorizations"] = [self.auth_json(aid)]
            self.orders[oid] = o
            return httpx.Response(201, json=o)
        if p[:3] == ["v2", "checkout", "orders"] and method == "GET":
            return httpx.Response(200, json=self.orders[p[3]])
        if p[:3] == ["v2", "payments", "authorizations"]:
            aid = p[3]
            if aid not in self.auths:
                return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND", "message": aid})
            a = self.auths[aid]
            total = int(round(float(a["amount"]["value"]) * 100))
            if method == "GET":
                return httpx.Response(200, json=self.auth_json(aid))
            action = p[4]
            if action == "capture":
                if a["status"] not in ("CREATED", "PARTIALLY_CAPTURED"):
                    return error(422, "AUTHORIZATION_ALREADY_CAPTURED" if a["status"] == "CAPTURED" else "AUTHORIZATION_VOIDED")
                amount = int(round(float(body["amount"]["value"]) * 100))
                if a["captured"] + amount > total:
                    return error(422, "MAX_CAPTURE_AMOUNT_EXCEEDED")
                a["captured"] += amount
                final = body.get("final_capture", False)
                a["status"] = "CAPTURED" if final or a["captured"] == total else "PARTIALLY_CAPTURED"
                cid = "C%04d" % next(self.ids)
                self.captures[cid] = {"id": cid, "status": "COMPLETED", "amount": body["amount"], "final_capture": final}
                return httpx.Response(201, json=self.captures[cid])
            if action == "void":
                if a["status"] not in ("CREATED", "PARTIALLY_CAPTURED"):
                    return error(422, "PREVIOUSLY_CAPTURED" if a["status"] == "CAPTURED" else "PREVIOUSLY_VOIDED")
                a["status"] = "VOIDED"
                return httpx.Response(204)
            if action == "reauthorize":
                if self.clock() - a["at"] < self.honor:
                    return error(422, "REAUTHORIZE_TOO_EARLY")  # the name is a guess; the spike records PayPal's
                a["status"] = "VOIDED"
                return httpx.Response(201, json=self.auth_json(self.new_auth(a["amount"])))
        if p[:3] == ["v2", "payments", "captures"] and method == "GET":
            return httpx.Response(200, json=self.captures[p[3]])
        return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND", "message": path})


def error(status, name):
    return httpx.Response(status, json={"name": "UNPROCESSABLE_ENTITY", "message": name,
                                        "details": [{"issue": name}], "debug_id": "dbg"})
