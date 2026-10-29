"""PayPal REST for RedLine: the hold and its settlement. Sandbox only.

A cover's money is a PayPal authorization (the hold). Settlement captures the
vendor's earned share and voids the rest; a capture after the 3-day honor
period is preceded by a reauthorization. Every write carries a
``PayPal-Request-Id``, so a retry returns the first result instead of acting
twice. Reads are retried on transient failures (network, 429, 5xx).

Callers get back ``Hold``/``Op`` records with ids, statuses and amounts only:
PayPal's response bodies carry the payer's name and email and are never
stored, logged or anchored.

Adapted from Remit for PayPal's client (auth, retries, errors).
"""

import base64
import time
from dataclasses import dataclass

import httpx

SANDBOX = "https://api-m.sandbox.paypal.com"
LIVE_HOSTS = ("api-m.paypal.com", "api.paypal.com")
TRANSIENT = (429, 500, 502, 503, 504)


class PayPalError(Exception):
    """A PayPal API error, with PayPal's own name and debug id."""

    def __init__(self, status, name, message, debug_id=""):
        super().__init__("%s %s: %s%s" % (status, name, message, " (debug id %s)" % debug_id if debug_id else ""))
        self.status, self.name, self.debug_id = status, name, debug_id


def _error(resp):
    try:
        body = resp.json()
    except Exception:
        body = {}
    message = body.get("message") or body.get("error_description") or resp.text[:200]
    # The specific reason (PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING, ...) is in ``details``.
    issues = ["%s%s" % (d.get("issue", ""), ": " + d["description"] if d.get("description") else "")
              for d in body.get("details", []) if isinstance(d, dict)]
    if issues:
        message = "%s [%s]" % (message, "; ".join(issues))
    return PayPalError(resp.status_code, body.get("name") or body.get("error") or "HTTP_ERROR", message,
                       body.get("debug_id", ""))


class RestPayPal:
    def __init__(self, client_id, client_secret, base_url=SANDBOX, transport=None, timeout=20.0, sleep=time.sleep,
                 tries=3):
        if any(h in base_url for h in LIVE_HOSTS):
            raise ValueError("RedLine on PayPal runs on the sandbox only; refusing %s" % base_url)
        if not client_id or not client_secret:
            raise ValueError("PayPal client id and secret are required")
        self._basic = base64.b64encode(("%s:%s" % (client_id, client_secret)).encode()).decode()
        self.http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)
        self.sleep, self.tries = sleep, tries
        self._token, self._expires = None, 0.0

    # ---------------------------------------------------------------- auth
    def _bearer(self, fresh=False):
        if fresh or not self._token or time.time() > self._expires:
            r = self.http.post("/v1/oauth2/token", data={"grant_type": "client_credentials"},
                               headers={"Authorization": "Basic " + self._basic})
            if r.status_code != 200:
                raise _error(r)
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + int(body.get("expires_in", 300)) - 60
        return self._token

    def _call(self, method, path, *, retry, **kw):
        """One API call. ``retry`` says whether a transient failure may be
        sent again; a 401 refreshes the token once."""
        refreshed = False
        for attempt in range(self.tries):
            headers = dict(kw.pop("headers", {}) or {})
            headers["Authorization"] = "Bearer " + self._bearer()
            try:
                r = self.http.request(method, path, headers=headers, **kw)
            except httpx.TransportError:
                if not retry or attempt == self.tries - 1:
                    raise
                self.sleep(2 ** attempt)
                kw["headers"] = {k: v for k, v in headers.items() if k != "Authorization"}
                continue
            kw["headers"] = {k: v for k, v in headers.items() if k != "Authorization"}
            if r.status_code == 401 and not refreshed:
                refreshed = True
                self._bearer(fresh=True)
                continue
            if r.status_code in TRANSIENT and retry and attempt < self.tries - 1:
                self.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise _error(r)
            return r.json() if r.content else {}
        raise PayPalError(0, "RETRIES_EXHAUSTED", "%s %s" % (method, path))

    # --------------------------------------------------------------- holds
    def create_order(self, *, amount_cents, currency, request_id, description="", card=None):
        """An order to hold ``amount_cents`` (``intent: AUTHORIZE``). With a
        sandbox ``card``, PayPal approves it in the same call; without one the
        buyer approves it in the PayPal button. Returns ``(order_id, status)``."""
        body = {"intent": "AUTHORIZE", "purchase_units": [{
            "amount": money(amount_cents, currency),
            **({"description": description[:127]} if description else {})}]}
        if card:
            body["payment_source"] = {"card": card}
        r = self._call("POST", "/v2/checkout/orders", retry=True, json=body, headers=self._write(request_id))
        return r["id"], r.get("status", "")

    def authorize_order(self, order_id, *, request_id):
        """Authorize an approved order. An order a card approved may already
        carry its authorization; then it is returned as it is."""
        r = self._call("GET", "/v2/checkout/orders/%s" % order_id, retry=True)
        if not _authorizations(r):
            r = self._call("POST", "/v2/checkout/orders/%s/authorize" % order_id, retry=True, json={},
                           headers=self._write(request_id))
        auths = _authorizations(r)
        if not auths:
            raise PayPalError(0, "NOT_AUTHORIZED", "order %s is %s" % (order_id, r.get("status")))
        return hold(auths[-1])

    def get_authorization(self, authorization_id):
        return hold(self._call("GET", "/v2/payments/authorizations/%s" % authorization_id, retry=True))

    def get_capture(self, capture_id):
        return op(self._call("GET", "/v2/payments/captures/%s" % capture_id, retry=True))

    # ----------------------------------------------------------- settlement
    def capture(self, authorization_id, *, amount_cents, currency, final, request_id):
        """Capture part or all of a hold. ``final=False`` leaves the rest
        capturable, so it can be voided explicitly."""
        body = {"amount": money(amount_cents, currency), "final_capture": bool(final)}
        return op(self._call("POST", "/v2/payments/authorizations/%s/capture" % authorization_id, retry=True,
                             json=body, headers=self._write(request_id)))

    def void(self, authorization_id, *, request_id):
        """Release what is left of a hold. PayPal answers 204 with no body, or
        200 with the authorization."""
        r = self._call("POST", "/v2/payments/authorizations/%s/void" % authorization_id, retry=True,
                       headers=self._write(request_id))
        return hold(r) if r else self.get_authorization(authorization_id)

    def reauthorize(self, authorization_id, *, request_id):
        """A new hold for the same amount, after the honor period. Returns the
        new authorization; later captures and voids use its id."""
        return hold(self._call("POST", "/v2/payments/authorizations/%s/reauthorize" % authorization_id,
                               retry=True, json={}, headers=self._write(request_id)))

    @staticmethod
    def _write(request_id):
        return {"PayPal-Request-Id": request_id, "Prefer": "return=representation",
                "Content-Type": "application/json"}


@dataclass(frozen=True)
class Hold:
    """An authorization, as RedLine keeps it."""
    id: str
    status: str  # CREATED, CAPTURED, PARTIALLY_CAPTURED, VOIDED, EXPIRED, DENIED, PENDING
    amount_cents: int
    currency: str
    created: str
    expires: str


@dataclass(frozen=True)
class Op:
    """A capture, as RedLine keeps it."""
    id: str
    status: str
    amount_cents: int
    currency: str
    final: bool


def money(value_cents, currency):
    return {"currency_code": currency, "value": "%d.%02d" % (value_cents // 100, value_cents % 100)}


def cents(value):
    whole, _, frac = str(value).partition(".")
    if not whole.isdigit() or (frac and not frac.isdigit()) or len(frac) > 2:
        raise ValueError("not an amount: %r" % value)
    return int(whole) * 100 + int((frac + "00")[:2])


def hold(a):
    amt = a.get("amount") or {}
    return Hold(id=a["id"], status=a.get("status", ""), amount_cents=cents(amt.get("value", "0")),
                currency=amt.get("currency_code", ""), created=a.get("create_time", ""),
                expires=a.get("expiration_time", ""))


def op(c):
    amt = c.get("amount") or {}
    return Op(id=c["id"], status=c.get("status", ""), amount_cents=cents(amt.get("value", "0")),
              currency=amt.get("currency_code", ""), final=bool(c.get("final_capture", False)))


def _authorizations(order):
    return [a for u in order.get("purchase_units", []) for a in u.get("payments", {}).get("authorizations", [])]
