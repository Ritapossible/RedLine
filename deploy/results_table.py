"""Print the README's on-chain tables from the scenario records.

    python3 deploy/results_table.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

LABELS = {
    "unchanged": "Page rebuilt (new build id, nonce, date), every pinned word kept",
    "reworded": "Refund sentence reworded, 30 days kept",
    "narrowed 1": "30 days becomes 7 days less a 15% fee (cover 1 of 3)",
    "narrowed 2": "the same, a fresh cover (2 of 3)",
    "narrowed 3": "the same, a fresh cover (3 of 3)",
    "removed": "Deletion promise deleted",
    "injected": 'Narrowed, plus text telling the jury to answer "same"',
    "voided": "Refund sentence kept word for word, a line above it saying it is withdrawn",
    "hidden": "Refund sentence kept only inside a hidden element, the visible page narrowed",
    "gone": "Page deleted: 404, three checks running",
    "real": "A passage of GitHub's live terms page",
    "real-bogus": "A passage that is not on GitHub's page",
}


def gen(x):
    return "%.4f" % (int(x) / 1e18)


def found(name, case):
    checks = case.get("checks", [])
    if name == "real-bogus":
        return "refused at pinning, no model"
    if name == "gone":
        kinds = [c.get("kind") or "third check refused: too close to the end" for c in checks]
        if kinds and kinds[-1] == "gone":
            return ", ".join(kinds[:-1]) + ", **gone**, no model"
        return ", ".join(kinds) + "; no model"
    c = checks[-1]
    text = "**%s**" % c.get("kind", "?")
    text += " (%s, %s)" % (c["reading"], c["confidence"]) if c.get("reading") else ", word for word, no model"
    retries = len(c.get("retries", []))
    if retries:
        text += "; %d observation retried" % retries
    if c.get("expired"):
        text += "; expired as contested"
    return text


def table(path):
    r = json.load(open(os.path.join(HERE, path)))
    rows = ["| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |", "| --- | --- | --- | --- | --- |"]
    for name, case in r["cases"].items():
        v = r["verified"]["covers"][name]
        rows.append("| %s | %s | %s | %s | %s |" % (LABELS[name], found(name, case), v["state"], gen(v["paid"]), gen(v["refunded"])))
    return "\n".join(rows), r


if __name__ == "__main__":
    for path in ("scenario-studio.json", "scenario-bradbury.json", "scenario-bradbury-gone.json"):
        if os.path.exists(os.path.join(HERE, path)):
            print(path)
            print(table(path)[0])
            print()
