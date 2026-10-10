"""RedLine: turning a fetched terms page into comparable text.

Pure Python, no ``gl.*``: inlined into the watcher contract by
``deploy/build_contract.py`` and tested directly.

A live terms page is never byte-stable: cookie banners, build ids, CSRF
tokens, "last updated" stamps and A/B variants change the raw HTML on every
fetch. So RedLine never compares bytes. It reduces the page to its visible
text, normalised (``page_text``), and asks only whether each passage the
buyer pinned is still there, word for word (``passage_present``). Dynamic
parts of the page do not touch that answer; an edit to the pinned sentence
does.
"""

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


def excerpts(text, passage, width=1500):
    """Up to two non-overlapping windows of the page, the ones sharing the
    most distinct words with the pinned passage, best first. Deterministic."""
    if len(text) <= width:
        return [text] if text else []
    wanted = set(w for w in _words(normalize(passage)) if len(w) > 2)
    step = max(1, width // 4)
    scored = []
    start = 0
    while True:
        window = text[start : start + width]
        scored.append((len(wanted.intersection(_words(window))), -start, start))
        if start + width >= len(text):
            break
        start += step
    scored.sort(reverse=True)
    first = scored[0][2]
    out = [text[first : first + width]]
    for score, _neg, at in scored[1:]:
        if score > 0 and abs(at - first) >= width:
            out.append(text[at : at + width])
            break
    return out
