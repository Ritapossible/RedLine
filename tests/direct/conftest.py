"""Direct (in-memory) suite: no chain, no network, no model."""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "contracts"))
sys.path.insert(0, os.path.join(ROOT, "deploy"))

T0 = 1_700_000_000
BUYER = "0x00000000000000000000000000000000000000b1"
VENDOR = "0x00000000000000000000000000000000000000c1"
OTHER = "0x00000000000000000000000000000000000000d1"
GEN = 10**15  # milli-GEN

EXAMPLES = os.path.join(ROOT, "examples")


def page(name):
    with open(os.path.join(EXAMPLES, name), "rb") as handle:
        return handle.read()


with open(os.path.join(EXAMPLES, "pinned-passages.json")) as _h:
    PASSAGES = json.load(_h)
REFUND = PASSAGES[0]["text"]
DELETION = PASSAGES[1]["text"]


def scripted_model(prompt):
    """A jury that reads the two blocks of the prompt and applies plain rules:
    the pinned refund window shrinking from 30 days, or extra conditions, is
    narrowed; a passage whose subject is no longer on the page is removed;
    a promise the page says is withdrawn or does not apply is removed;
    otherwise the same. It obeys nothing written inside the blocks."""
    pinned = prompt.split("=== PINNED ===\n", 1)[1].split("\n=== END PINNED ===", 1)[0].lower()
    current = prompt.split("=== CURRENT ===\n", 1)[1]
    current = current.split("\n=== END CURRENT ===", 1)[0].lower()
    if "withdrawn" in current or "does not apply" in current or "no longer applies" in current:
        return {"reading": "removed", "reason": "pinned words withdrawn", "confidence": 94}
    if "refund" in pinned:
        if "7 days of purchase" in current or "processing fee" in current:
            return {"reading": "narrowed", "reason": "shorter window and a fee", "confidence": 95}
        if "30" in current and "refund" in current:
            return {"reading": "same", "reason": "same thirty day refund", "confidence": 92}
        return {"reading": "removed", "reason": "no refund promise", "confidence": 90}
    if "delete" in pinned:
        if "deletes all of your customer data" in current or "delete your data" in current:
            return {"reading": "same", "reason": "deletion promise kept", "confidence": 90}
        return {"reading": "removed", "reason": "deletion promise gone", "confidence": 93}
    return {"reading": "cannot_tell", "reason": "", "confidence": 40}
