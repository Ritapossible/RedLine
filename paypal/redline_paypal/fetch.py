"""Fetching a vendor's terms page, safely.

The server fetches URLs that came from outside, so (architecture 9.1):
only ``https`` hosts on the allow-list; never a private, loopback, link-local
or reserved address (checked on every hop); at most 3 redirects; a 10 s
timeout; at most ``MAX_PAGE_BYTES``; no cookies or credentials. The result
is one of redline_core's page states, never an exception.

Limit: the address is checked before the request, not pinned for it, so a
DNS answer that changes between the two is not caught. Vendors are
registered hosts, which narrows that to hosts we already trust.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from .core import core, text

MAX_REDIRECTS = 3
TIMEOUT = 10.0
AGENT = "RedLine terms checker (+https://redline-paypal.vercel.app)"


class Refused(Exception):
    """A URL RedLine will not fetch."""


def host_allowed(host, allowed):
    host = host.lower().rstrip(".")
    return any(host == a or host.endswith("." + a) for a in allowed)


def public_address(host, resolve=socket.getaddrinfo):
    """Every address the host resolves to must be public."""
    try:
        infos = resolve(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise Refused("cannot resolve %s" % host) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise Refused("%s resolves to a non-public address" % host)


def fetch(url, *, allowed, transport=None, resolve=socket.getaddrinfo):
    """``(page, status, body_text)``: page is PAGE_READ (2xx), PAGE_MISSING
    (404/410) or PAGE_UNREAD (anything else, or refused)."""
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=False,
                          headers={"User-Agent": AGENT, "Accept": "text/html"}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                parts = urlsplit(url)
                if parts.scheme != "https" or not parts.hostname or not host_allowed(parts.hostname, allowed):
                    raise Refused("not an allowed https host: %s" % url)
                if transport is None:
                    public_address(parts.hostname, resolve)
                with client.stream("GET", url) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code in core.MISSING_STATUS:
                        return core.PAGE_MISSING, r.status_code, ""
                    if not 200 <= r.status_code < 300:
                        return core.PAGE_UNREAD, r.status_code, ""
                    body = b""
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) >= text.MAX_PAGE_BYTES:
                            break
                    return core.PAGE_READ, r.status_code, body[: text.MAX_PAGE_BYTES].decode("utf-8", "replace")
            raise Refused("too many redirects")
    except (Refused, httpx.HTTPError):
        return core.PAGE_UNREAD, 0, ""
