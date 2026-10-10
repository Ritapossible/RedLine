# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import hashlib


# Elements whose content is never visible text.
HIDDEN_ELEMENTS = ("script", "style", "noscript", "template", "svg", "head", "iframe")

ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " ",
    "rsquo": "'", "lsquo": "'", "rdquo": '"', "ldquo": '"', "ndash": "-", "mdash": "-",
    "hellip": "...", "sect": "§", "copy": "©", "reg": "®", "trade": "™", "bull": "*",
    "middot": "*", "shy": "", "zwj": "", "zwnj": "",
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


def strip_markup(html):
    """Visible text of an HTML document: tags become spaces, comments and the
    content of hidden elements are dropped. A plain-text page passes through."""
    lower = html.lower()
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
        if name in HIDDEN_ELEMENTS and not tag.endswith("/"):
            close = lower.find("</" + name, i)
            if close == -1:
                break
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


def best_excerpt(text, passage, width=1200):
    """The part of the new page most likely to hold what became of the pinned
    passage: the window of ``width`` characters sharing the most distinct
    words with it. Deterministic, so every validator that fetched the same
    text shows the jury the same excerpt."""
    if len(text) <= width:
        return text
    wanted = set(w for w in _words(normalize(passage)) if len(w) > 2)
    if not wanted:
        return text[:width]
    step = max(1, width // 4)
    best_at, best_score = 0, -1
    start = 0
    while start < len(text):
        window = text[start : start + width]
        score = len(wanted.intersection(_words(window)))
        if score > best_score:
            best_at, best_score = start, score
        if start + width >= len(text):
            break
        start += step
    return text[best_at : best_at + width]


def as_dict(value):
    """Decode a model answer or a consensus payload into a dict, however it
    arrives (a dict, JSON text, JSON text inside prose, a wrapper object whose
    ``str()`` is the payload). Never raises; {} when nothing readable."""
    data = value
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", "replace")
    elif not isinstance(data, (dict, str)):
        data = str(data)
    for _ in range(4):
        if isinstance(data, dict):
            return data
        if not isinstance(data, str):
            return {}
        text = data.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start and not text.startswith('"'):
            text = text[start : end + 1]
        try:
            data = json.loads(text)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}



class ProbeTerms(gl.Contract):
    out: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def probe(self, uri: str, passage: str, mode: str) -> None:
        def read() -> dict:
            try:
                if mode == "render":
                    raw = gl.nondet.web.render(uri, mode="text")
                    status = 200
                else:
                    r = gl.nondet.web.get(uri)
                    status = int(r.status)
                    raw = r.body or b""
                t = page_text(raw)
                return {"status": status, "len": len(t), "digest": hashlib.sha256(t.encode("utf-8")).hexdigest()[:16],
                        "present": passage_present(t, passage), "head": t[:120]}
            except Exception as e:
                return {"raised": type(e).__name__, "msg": str(e)[:200]}

        def leader() -> str:
            return json.dumps(read())

        def validator(res) -> bool:
            theirs = as_dict(res)
            mine = read()
            if mode.endswith("strict") or mode == "get":
                return theirs.get("digest") == mine.get("digest")
            return theirs.get("present") == mine.get("present")

        self.out[uri + "|" + mode] = str(gl.vm.run_nondet(leader, validator))

    @gl.public.view
    def get(self, key: str) -> str:
        return self.out.get(key, "")
