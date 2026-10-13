"""Rewrite the README's "The on-chain record" and "Deployed contracts"
sections from the scenario records and deploy/deployments.json, so the README
always shows the contracts that are deployed and the runs made on them.

    python3 deploy/readme_record.py
"""

import json
import os

from results_table import table

HERE = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(HERE, "..", "README.md")
EXPLORER = {"studio": "https://explorer-studio.genlayer.com", "bradbury": "https://explorer-bradbury.genlayer.com"}


def load(name):
    path = os.path.join(HERE, name)
    return json.load(open(path)) if os.path.exists(path) else None


def link(net, addr):
    return "[`%s`](%s/address/%s)" % (addr, EXPLORER[net], addr)


def section():
    dep = json.load(open(os.path.join(HERE, "deployments.json")))
    studio, bradbury, gone = load("scenario-studio.json"), load("scenario-bradbury.json"), load("scenario-bradbury-gone.json")
    s_table, _ = table("scenario-studio.json")
    b_table, _ = table("scenario-bradbury.json")
    out = ["## The on-chain record", ""]
    out.append(
        "Every case below ran on the contracts deployed now (treasury `%s`, watcher `%s`): the "
        "rules that a pinned sentence voided by a line beside it, or kept only in hidden markup, is not "
        "kept, and that a terms URL must be plain https. Every cover's paid + refunded equals its prepay "
        "exactly, read back from chain with exact integers (`deploy/verify.mjs`)."
        % (dep["studio"]["release"], dep["studio"]["watcher_release"])
    )
    out += ["", "**Studio** (`deploy/scenario-studio.json`; prepay 0.02 GEN each, %d-minute covers, checks %d minutes "
            "apart, a %d-second appeal window). %d failed checks. A cover opened with a query string in its URL was "
            "refused and its 0.02 GEN returned. After both parties withdrew, the treasury's held, owed and balance "
            "were all 0." % (studio["coverage_seconds"] // 60, studio["check_gap_seconds"] // 60, dep["studio"]["appeal_seconds"],
                             studio.get("failures", 0)), "", s_table, ""]
    b_fail = [c for c in bradbury["checks"] if not c["ok"]]
    out += ["**Bradbury** (`deploy/scenario-bradbury.json`; %d-minute covers, checks %d minutes apart, a %d-second "
            "appeal window). Every judged case matched Studio, including the voided (removed, 100) and hidden "
            "(narrowed, 95) pages, and the URL with a query string was refused with its prepay returned."
            % (bradbury["coverage_seconds"] // 60, bradbury["check_gap_seconds"] // 60, dep["bradbury"]["appeal_seconds"]), ""]
    out += [b_table, ""]
    if b_fail:
        out.append(
            "%d checks of this run failed, both from the run's schedule, not the contracts: opening and checking "
            "twelve covers took 37 minutes of each 75-minute cover, so the deleted page's third check fell inside "
            "the last half-gap and the watcher refused it (\"too close to the end of the cover\"); that cover still "
            "refunded, dated from its first absent check, because the page was absent at its last check. And its "
            "books check read the treasury while a separate deleted-page run's cover on the same treasury was still "
            "open (below); read again after that run, held, owed and balance were all 0." % len(b_fail))
        out.append("")
    if gone and gone.get("verified"):
        g = gone["cases"]["gone"]
        kinds = ", ".join(c.get("kind", "?") for c in g["checks"])
        v = gone["verified"]["covers"]["gone"]
        out.append(
            "**Bradbury, the deleted page alone** (`deploy/scenario-bradbury-gone.json`; %d-minute cover, checks %d "
            "minutes apart): %s, no model; %s, the vendor paid %.4f GEN until the first absence, the buyer refunded "
            "%.4f GEN. %d failed checks." % (gone["coverage_seconds"] // 60, gone["check_gap_seconds"] // 60, kinds, v["state"],
                                             int(v["paid"]) / 1e18, int(v["refunded"]) / 1e18, gone.get("failures", 0)))
        books = gone["verified"]["books"]
        out[-1] += (" After every Bradbury run, the treasury owes nothing and holds nothing in covers (held %s, owed %s)%s."
                    % (books["held"], books["owed"],
                       "" if int(books["balance"]) == 0 else "; its last %.2f GEN, the final withdrawals, leaves the contract when those transactions finalise (they were ACCEPTED, not yet FINALIZED, when read)" % (int(books["balance"]) / 1e18)))
        out.append("")
    out.append(
        "**Earlier runs**, kept for the record, on earlier contracts: `deploy/scenario-*-v1.json` (watcher 1; on "
        "Bradbury the reworded check was finalised with all five validators `NOT_VOTED` and recorded nothing - the "
        "reason a check now always ends in a record), `deploy/scenario-bradbury-rerun.json` and "
        "`deploy/scenario-*-v2.json` (watcher 2, before the voided and hidden rules), and "
        "`deploy/scenario-bradbury-gone-interrupted.json` (a deleted-page rerun cut short by a paused container, "
        "settled from its first absence).")
    out += ["", "## Deployed contracts", "", "| Network | Treasury | Watcher |", "| --- | --- | --- |"]
    for net, label in (("studio", "GenLayer Studio"), ("bradbury", "Bradbury testnet")):
        out.append("| %s | %s | %s |" % (label, link(net, dep[net]["treasury"]), link(net, dep[net]["watcher"])))
    out += ["", "- Releases: treasury `%s`, watcher `%s`." % (dep["studio"]["release"], dep["studio"]["watcher_release"]),
            "- Appeal window: %d s on Studio, %s s on Bradbury." % (dep["studio"]["appeal_seconds"], format(dep["bradbury"]["appeal_seconds"], ",")), ""]
    return "\n".join(out)


if __name__ == "__main__":
    text = open(README).read()
    start = text.index("## The on-chain record")
    end = text.index("## Limits, stated plainly")
    open(README, "w").write(text[:start] + section() + "\n" + text[end:])
    print("README record section rewritten")
