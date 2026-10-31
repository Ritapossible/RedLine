"""Vendors, and the demo vendor's terms page as the web app shows it.

A demo vendor is created per visitor: Acme Data API, its terms page served
by this server at ``<public url>/demo/v/<token>/terms`` in the version the
vendor console last chose. The checker reads demo pages in process, never
over the network (architecture 7).
"""

import hashlib
import html.parser
import secrets
import time

from . import demo
from .core import core, text

PRICE_CENTS = 2000
COVER_SECONDS = 600
GAP_SECONDS = 60
BLOCKS = {"h1": "title", "h2": "heading", "h3": "heading", "p": "text", "li": "text", "nav": "chrome", "footer": "chrome"}
VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "track"}


class VendorError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Vendors:
    def __init__(self, db, public_url, *, clock=time.time):
        self.db, self.public_url, self.clock = db, public_url.rstrip("/"), clock

    def create_demo(self):
        token = secrets.token_hex(12)
        url = "%s/demo/v/%s/terms" % (self.public_url, token)
        self.db.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (token, "Acme Data API", "Prepaid API credit", url, PRICE_CENTS, COVER_SECONDS, GAP_SECONDS,
                         "original", 1, int(self.clock())))
        return self.get(token)

    def get(self, token):
        row = self.db.execute("SELECT token, name, product, terms_url, price_cents, cover_seconds, gap_seconds, version, "
                              "demo FROM vendors WHERE token = ?", (token,)).fetchone()
        if not row:
            raise VendorError(404, "No vendor with this link. Start a new demo.")
        keys = ("token", "name", "product", "terms_url", "price_cents", "cover_seconds", "gap_seconds", "version", "demo")
        return dict(zip(keys, row))

    def set_version(self, token, version):
        v = self.get(token)
        if not v["demo"]:
            raise VendorError(403, "Only a demo vendor's terms can be switched.")
        if version not in demo.VERSION_IDS:
            raise VendorError(422, "Unknown terms version.")
        self.db.execute("UPDATE vendors SET version = ? WHERE token = ?", (version, token))
        return self.get(token)

    def demo_token(self, url):
        """The demo vendor a terms URL belongs to, or None for any other page."""
        prefix = self.public_url + "/demo/v/"
        if url.startswith(prefix) and url.endswith("/terms"):
            return url[len(prefix):-len("/terms")]
        return None

    def demo_html(self, token):
        """The page a demo vendor serves now; None when it is "down"."""
        return demo.html(self.get(token)["version"])

    def page(self, token, read_page):
        """The terms page as the web app shows it: visible blocks only."""
        v = self.get(token)
        state, body = read_page(v["terms_url"])
        if state != core.PAGE_READ:
            raise VendorError(503, "%s's terms page is not answering." % v["name"].split()[0])
        title, blocks = visible_blocks(body)
        return {"url": v["terms_url"], "title": title, "blocks": blocks,
                "sha256": hashlib.sha256(text.page_text(body).encode("utf-8")).hexdigest()}

    def suggestions(self, token, read_page):
        """Rights worth pinning, each on today's page word for word."""
        v = self.get(token)
        state, body = read_page(v["terms_url"])
        if state != core.PAGE_READ:
            return []
        visible = text.page_text(body)
        return [s for s in demo.SUGGESTIONS if not text.passage_error(s["text"]) and text.passage_present(visible, s["text"])]


def vendor_json(v):
    out = {"token": v["token"], "name": v["name"], "product": v["product"], "termsUrl": v["terms_url"],
           "priceCents": v["price_cents"], "currency": "USD", "coverSeconds": v["cover_seconds"],
           "checkGapSeconds": v["gap_seconds"]}
    if v["demo"]:
        out["version"] = v["version"]
    return out


class _Blocks(html.parser.HTMLParser):
    """Visible blocks for display. Hiding follows redline_text.is_hidden, so
    what is shown is what the rules read."""

    def __init__(self, hidden):
        super().__init__(convert_charrefs=True)
        self.hidden, self.stack, self.blocks, self.title, self.in_title = hidden, [], [], "", False
        self.current = None  # [kind, depth, parts]

    def handle_starttag(self, name, attrs):
        raw = (self.get_starttag_text() or "").lower().strip("<>/ ")
        if name == "title":
            self.in_title = True
        if name in VOID:
            return
        hide = text.is_hidden(name, raw, self.hidden)
        self.stack.append((name, hide))
        kind = BLOCKS.get(name)
        if name == "div" and "cookie" in dict(attrs).get("class", "").split():
            kind = "chrome"
        if kind and self.current is None and not self.hiding():
            self.current = [kind, len(self.stack), []]

    def handle_endtag(self, name):
        if name == "title":
            self.in_title = False
        if name in VOID:
            return
        while self.stack:
            top, _ = self.stack.pop()
            if self.current and len(self.stack) < self.current[1]:
                t = " ".join("".join(self.current[2]).split())
                if t:
                    self.blocks.append({"kind": self.current[0], "text": t})
                self.current = None
            if top == name:
                break

    def hiding(self):
        return any(h for _, h in self.stack)

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.current and not self.hiding():
            self.current[2].append(data)
        elif self.current is not None:
            pass

    def handle_startendtag(self, name, attrs):
        if self.current and not self.hiding():
            self.current[2].append(" ")


def visible_blocks(page):
    p = _Blocks(text.hidden_selectors(page))
    p.feed(page)
    p.close()
    return " ".join(p.title.split()), p.blocks
