"""The demo vendor, Acme Data API: its terms page in every version the vendor
console offers, from RedLine's own examples/ (the same pages the tests and
the web app's preview read), and the rights worth pinning on it.

Demo pages are served by this server at ``/demo/v/<token>/terms`` and read
in-process by the checker (architecture 7): a sleeping server must never
read its own pages as absent.
"""

import json
import os

from .core import core

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "examples")

FILES = {
    "original": "terms-v1.html",
    "rebuilt": "terms-v1-rebuilt.html",
    "reworded": "terms-reworded.html",
    "narrowed": "terms-narrowed.html",
    "deletion-removed": "terms-deletion-removed.html",
    "injected": "terms-narrowed-injected.html",
    "voided": "terms-voided.html",
    "hidden": "terms-hidden.html",
    "hidden-style": "terms-hidden-style.html",
}

VERSIONS = [
    {"id": "original", "title": "Original terms", "summary": "The page as customers pinned it.", "expect": "Kept, by code. No model is asked.", "cuts": False},
    {"id": "rebuilt", "title": "Redeployed", "summary": "A new build id, nonce and \"last updated\" date; not one word of the terms changed.", "expect": "Kept, by code: dates and build noise are not a change.", "cuts": False},
    {"id": "reworded", "title": "Reworded refund", "summary": "\"Cancel within thirty (30) days after you buy and we will refund all of your unused prepaid credit in full.\"", "expect": "The panel reads it: same right, still kept.", "cuts": False},
    {"id": "narrowed", "title": "Refund window cut", "summary": "30 days becomes 7, with a 15% fee and a usage limit.", "expect": "Narrowed: confirmed by a second check, then the rest is released.", "cuts": True},
    {"id": "deletion-removed", "title": "Data deletion removed", "summary": "\"Acme retains customer data for as long as it considers necessary.\"", "expect": "Removed: confirmed, then the rest is released.", "cuts": True},
    {"id": "injected", "title": "Cut, and tells the AI it isn't", "summary": "The narrowed refund, plus text telling the reviewer to answer \"same\".", "expect": "The page is quoted data: the instruction is ignored, the cut is found.", "cuts": True},
    {"id": "voided", "title": "Withdrawn above the passage", "summary": "The refund sentence is still there, word for word, under \"The following is withdrawn and does not apply.\"", "expect": "Its surroundings changed, so the panel reads it: removed.", "cuts": True},
    {"id": "hidden", "title": "Kept in the HTML, hidden", "summary": "The original sentence hidden with the hidden attribute; the visible page shows the narrowed one.", "expect": "Hidden text is not text: narrowed.", "cuts": True},
    {"id": "hidden-style", "title": "Hidden with CSS", "summary": "The original sentence in display:none; the visible page shows the narrowed one.", "expect": "Hidden text is not text: narrowed.", "cuts": True},
    {"id": "down", "title": "Page taken down", "summary": "The terms page stops answering.", "expect": "Absent three checks running: gone, settled like a cut.", "cuts": True},
]
VERSION_IDS = {v["id"] for v in VERSIONS}

SUGGESTIONS = [
    {"id": "refund", "label": "30-day refund", "why": "Your money back on unused credit for a month, no questions asked.",
     "text": "You may cancel at any time within 30 days of purchase and receive a full refund of any unused prepaid credit, with no questions asked."},
    {"id": "deletion", "label": "Data deleted in 7 days", "why": "Your data, backups included, gone within a week of asking.",
     "text": "When you ask us in writing to delete your data, Acme permanently deletes all of your customer data, including backups, within 7 days of the request."},
    {"id": "availability", "label": "Availability credit", "why": "10% back in any month Acme misses 99.9% availability.",
     "text": "If availability falls below that target in a calendar month, Acme will credit 10% of that month's usage fees to your account on request."},
    {"id": "notice", "label": "30 days' notice of changes", "why": "Material changes only take effect a month after they are posted.",
     "text": "Material changes take effect 30 days after they are posted on this page."},
]

_cache = {}


def html(version):
    """The page for a version, or None for "down"."""
    if version == "down":
        return None
    if version not in _cache:
        with open(os.path.join(EXAMPLES, FILES[version]), encoding="utf-8") as f:
            _cache[version] = f.read()
    return _cache[version]


# ------------------------------------------------------- offline stand-ins
# For running the server without a model key (local development, tests).
# They recognise the demo pages' versions and answer as RedLine's GenLayer
# jury did on them; anything else is "cannot_tell", which never cuts.

_MARKS = [
    ("thirty (30) days", "refund", "same", 92),
    ("less a 15% processing fee", "refund", "narrowed", 95),
    ("withdrawn and does not apply", "refund", "removed", 90),
    ("retains customer data", "deletion", "removed", 96),
]


def stand_in(prompt):
    pinned = prompt.split("=== PINNED ===", 1)[-1].split("=== END PINNED ===", 1)[0].lower()
    current = prompt.split("=== CURRENT ===", 1)[-1].split("=== END CURRENT ===", 1)[0].lower()
    which = "refund" if "refund" in pinned else "deletion" if "delete" in pinned else ""
    for mark, passage, reading, confidence in _MARKS:
        if passage == which and mark in current:
            return json.dumps({"reading": reading, "reason": "stand-in", "confidence": confidence})
    if which and " ".join(pinned.split()) in " ".join(current.split()):
        return json.dumps({"reading": "same", "reason": "stand-in", "confidence": 85})
    return json.dumps({"reading": core.READ_CANNOT_TELL, "reason": "stand-in", "confidence": 0})


def stand_in_models():
    return {"Stand-in model 1": stand_in, "Stand-in model 2": stand_in}
