"""RedLine for PayPal, built from the environment. Every secret comes from
here (Render's dashboard, or GitHub Actions secrets), never from the repository.

    REDLINE_DB                 postgresql://... (Neon) or a SQLite path; default redline.sqlite3
    REDLINE_PUBLIC_URL         this server's https URL; demo terms pages live under it
    REDLINE_WEB_ORIGINS        comma-separated origins allowed to call the API (the Vercel site)
    PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET
                               a PayPal sandbox REST app (live hosts are refused)
    REDLINE_SANDBOX_CARD       optional "number,YYYY-MM" for the test-card path
    REDLINE_MODEL_API_KEY      a key for an OpenAI-compatible API
    REDLINE_MODEL_BASE_URL     that API's base URL
    REDLINE_PANEL_MODELS       comma-separated model names, one per panel seat
    REDLINE_PANEL_QUORUM       default: a strict majority of the seats
    REDLINE_ALLOWED_HOSTS      comma-separated hosts the checker may fetch (vendors' terms pages)
    REDLINE_OFFLINE=1          the PayPal stand-in and stand-in models: no keys needed
"""

import os
import time

from . import demo, fetch
from .core import core
from .covers import Covers
from .ledger import Ledger
from .panel import Panel
from .store import open_store
from .vendors import Vendors

TEST_CARD = {"number": "4111111111111111", "expiry": "2030-12", "security_code": "123"}


class ConfigError(Exception):
    pass


def card_from(value):
    number, _, expiry = (value or "").partition(",")
    if not number.strip():
        return dict(TEST_CARD)
    return {"number": number.strip(), "expiry": expiry.strip() or TEST_CARD["expiry"], "security_code": "123"}


def env_list(env, name):
    return [v.strip() for v in env.get(name, "").split(",") if v.strip()]


class App:
    """Everything one process needs, built once."""

    def __init__(self, env=os.environ, *, clock=time.time, paypal=None, models=None, transport=None):
        self.env, self.clock = env, clock
        self.offline = env.get("REDLINE_OFFLINE") == "1"
        self.db = open_store(env.get("REDLINE_DB", "redline.sqlite3"))
        self.ledger = Ledger(self.db)
        self.public_url = env.get("REDLINE_PUBLIC_URL", "https://redline-paypal-api.onrender.com").rstrip("/")
        if core.url_error(self.public_url + "/demo/v/x/terms"):
            raise ConfigError("REDLINE_PUBLIC_URL must be an https URL with no query: %s" % self.public_url)
        self.vendors = Vendors(self.db, self.public_url, clock=clock)
        self.allowed = env_list(env, "REDLINE_ALLOWED_HOSTS")
        self.transport = transport
        self.card = card_from(env.get("REDLINE_SANDBOX_CARD", ""))

        if paypal is None:
            if self.offline:
                from .offline import offline_paypal
                paypal = offline_paypal(clock=clock)
            else:
                from .paypal_api import RestPayPal
                paypal = RestPayPal(env.get("PAYPAL_CLIENT_ID", ""), env.get("PAYPAL_CLIENT_SECRET", ""))
        if models is None:
            if self.offline:
                models = demo.stand_in_models()
            else:
                from .models import ChatModel
                names = env_list(env, "REDLINE_PANEL_MODELS")
                key, base = env.get("REDLINE_MODEL_API_KEY", ""), env.get("REDLINE_MODEL_BASE_URL", "")
                if not names or not key or not base:
                    raise ConfigError("set REDLINE_MODEL_API_KEY, REDLINE_MODEL_BASE_URL and REDLINE_PANEL_MODELS, "
                                      "or REDLINE_OFFLINE=1")
                models = {"Panel model %d" % (i + 1): ChatModel(n, key, base) for i, n in enumerate(names)}
        quorum = env.get("REDLINE_PANEL_QUORUM")
        self.panel = Panel(models, quorum=int(quorum) if quorum else None)
        self.covers = Covers(self.db, self.ledger, paypal, self.panel, self.read_page, clock=clock)

    def read_page(self, url):
        """``(page, body)``. A demo vendor's page is read in process, so a
        server woken from sleep never reads its own page as absent."""
        token = self.vendors.demo_token(url)
        if token is not None:
            try:
                body = self.vendors.demo_html(token)
            except Exception:
                return core.PAGE_MISSING, ""
            return (core.PAGE_UNREAD, "") if body is None else (core.PAGE_READ, body)
        page, _, body = fetch.fetch(url, allowed=self.allowed, transport=self.transport)
        return page, body
