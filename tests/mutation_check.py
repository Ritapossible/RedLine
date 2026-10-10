"""Mutation harness: every rule must have a test that fails without it.

Each entry weakens or deletes one rule in a source file. The contracts are
rebuilt from the mutant (so the tests that run the deployed bytes see it), the
suite runs, and it must FAIL. A mutant that survives names an untested rule.

    python3 tests/mutation_check.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "contracts", "redline_core.py")
TEXT = os.path.join(ROOT, "contracts", "redline_text.py")
PROMPTS = os.path.join(ROOT, "contracts", "redline_prompts.py")
TREASURY = os.path.join(ROOT, "contracts", "treasury_shell.py")
WATCHER = os.path.join(ROOT, "contracts", "watcher_shell.py")
BUILD = os.path.join(ROOT, "contracts", "build")

# (name, what it breaks, original fragment, mutated fragment, file)
MUTATIONS = [
    # --- money ---
    ("vendor-overpaid", "the vendor never earns more than the prepay",
     "    if elapsed >= duration:\n        return int(cover[\"amount\"])", "    if False:\n        return int(cover[\"amount\"])", CORE),
    ("accrual-ignores-hold", "a held check stops the vendor accruing",
     "    if held:\n        cap = min(cap, int(held[\"from\"]))", "    if False:\n        cap = min(cap, int(held[\"from\"]))", CORE),
    ("close-claws-back", "closing never claws back what was credited",
     "    vendor_total = max(int(cover[\"paid\"]), earned(cover, at))", "    vendor_total = earned(cover, at)", CORE),
    ("refund-keeps-rest", "a breach refunds the buyer the rest",
     "    _credit(credits, cover[\"buyer\"], int(cover[\"amount\"]) - vendor_total)", "    pass", CORE),
    ("breach-pays-vendor", "a breach closes as of the check, not the end",
     "        return close(cover, COVER_BREACHED, int(held[\"from\"]), now)\n    if now > int(cover[\"end\"])",
     "        return close(cover, COVER_BREACHED, int(cover[\"end\"]), now)\n    if now > int(cover[\"end\"])", CORE),
    ("breach-skips-appeal", "a breach waits out its appeal window",
     "now >= int(held[\"noted_at\"]) + int(appeal_seconds)", "now >= int(held[\"noted_at\"])", CORE),
    ("end-skips-appeal", "the end waits out the appeal window",
     "    if now > int(cover[\"end\"]) + int(appeal_seconds):", "    if now > int(cover[\"end\"]):", CORE),
    ("absent-at-end-paid", "a page absent at the end is not paid for",
     "        if held and held[\"kind\"] == CHECK_ABSENT:\n            return close(cover, COVER_BREACHED", "        if False:\n            return close(cover, COVER_BREACHED", CORE),
    ("never-accepted-kept", "an offer nobody accepts refunds whole",
     "        if now > int(cover[\"accept_by\"]):\n            return refund_all(", "        if False:\n            return refund_all(", CORE),
    ("failed-pin-kept", "a failed pin refunds at once",
     "    return refund_all(cover, now, \"not pinned: \" + str(reason))", "    return {}", CORE),
    ("older-check-applied", "an older check is ignored",
     "    if seq < int(cover[\"seq\"]):\n        return {}", "    if False:\n        return {}", CORE),
    ("breach-undone", "a reported breach stands against later checks",
     "    if held and int(held[\"seq\"]) != seq and held[\"kind\"] in ENDS_COVER:\n        return {}", "    if False:\n        return {}", CORE),
    ("absence-start-lost", "gone dates from the first absence",
     "        start = int(since) if kind in (CHECK_ABSENT, CHECK_GONE) else int(at)", "        start = int(at)", CORE),
    ("check-after-end", "a check after the end is refused",
     "    if int(at) > int(cover[\"end\"]):\n        raise RedlineError(\"the check came after", "    if False:\n        raise RedlineError(\"the check came after", CORE),
    ("vendor-accepts-anyone", "only the vendor accepts",
     "    if normalize_address(by) != cover[\"vendor\"]:", "    if False:", CORE),
    ("late-accept", "acceptance has a deadline",
     "    if int(now) > int(cover[\"accept_by\"]):\n        raise RedlineError(\"the acceptance deadline", "    if False:\n        raise RedlineError(\"the acceptance deadline", CORE),
    ("cancel-active", "an active cover cannot be cancelled",
     "    if cover[\"state\"] not in (COVER_PINNING, COVER_OFFERED):\n        raise RedlineError(\"cover %d can no longer", "    if False:\n        raise RedlineError(\"cover %d can no longer", CORE),
    ("anyone-cancels", "only the buyer cancels",
     "    if normalize_address(by) != cover[\"buyer\"]:\n        raise RedlineError(\"only the buyer may cancel\")", "    if False:\n        raise RedlineError(\"only the buyer may cancel\")", CORE),
    # --- opening ---
    ("same-party", "buyer and vendor differ",
     "            errors.append(\"the buyer and the vendor must differ\")", "            pass", CORE),
    ("free-cover", "a cover needs a prepay",
     "    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:", "    if False:", CORE),
    ("gap-too-wide", "three checks must fit in the cover",
     "    if not errors and ABSENT_LIMIT * int(check_gap_seconds) > int(coverage_seconds):", "    if False:", CORE),
    ("empty-passage", "a pinned passage must say something",
     "    if len(p) < MIN_PASSAGE:", "    if False:", TEXT),
    # --- the watcher's rules ---
    ("hesitant-breach", "a hesitant breach is not a breach",
     "    if reading in BREACH_READINGS and int(confidence) >= MIN_BREACH_CONFIDENCE:", "    if reading in BREACH_READINGS:", CORE),
    ("breach-without-agreement", "a breach stands only on agreement",
     "    return leader_kind == own_kind", "    return True", CORE),
    ("gone-at-once", "gone needs three absences",
     "    record[\"kind\"] = CHECK_GONE if streak >= ABSENT_LIMIT else CHECK_ABSENT", "    record[\"kind\"] = CHECK_GONE", CORE),
    ("streak-never-grows", "absences running count up",
     "        streak = int(previous.get(\"streak\", 1)) + 1", "        streak = 1", CORE),
    ("missing-passage-kept-wrongly", "a breach on any passage decides",
     "        if not r[\"present\"] and reading_to_kind(r[\"reading\"], r[\"confidence\"]) == CHECK_BREACH:", "        if False:", CORE),
    # --- the page text ---
    ("scripts-are-text", "hidden elements are not text",
     "        if name in HIDDEN_ELEMENTS and not tag.endswith(\"/\"):", "        if False:", TEXT),
    ("case-matters", "case and spacing are not words",
     "    return \" \".join(\"\".join(folded).lower().split())", "    return \"\".join(folded)", TEXT),
    ("comments-are-text", "comments are not text",
     "        if html.startswith(\"<!--\", lt):", "        if False:", TEXT),
    # --- the prompt ---
    ("page-not-neutralized", "the page cannot forge the prompt's structure",
     "    current = \"\\n...\\n\".join(neutralize(e[:MAX_EXCERPT]) for e in excerpts[:2])", "    current = \"\\n...\\n\".join(e[:MAX_EXCERPT] for e in excerpts[:2])", PROMPTS),
    ("unreadable-is-narrowed", "an unreadable answer is never a breach",
     "    else:\n        reading = READ_CANNOT_TELL\n    reason", "    else:\n        reading = READ_NARROWED\n    reason", PROMPTS),
    # --- the treasury ---
    ("note-from-anyone", "only the watcher reports",
     "        if self._me() != self.watcher:", "        if False:", TREASURY),
    ("refusal-keeps-value", "a refused cover credits its value back",
     "        if value > 0:\n            self.owed[me]", "        if False:\n            self.owed[me]", TREASURY),
    ("refusal-reverts", "a refused cover must not revert (a reverted call keeps its value)",
     "            self._refuse(\"; \".join(errors), value)", "            raise Exception(\"; \".join(errors))", TREASURY),
    ("no-auto-pin", "a funded cover asks the watcher to pin it",
     "        gl.get_contract_at(Address(self.watcher)).emit(on=\"accepted\").pin(", "        (lambda *a: None)(", TREASURY),
    ("double-withdraw", "withdraw zeroes what it sends",
     "        self.owed[me] = u256(0)", "        pass", TREASURY),
    # --- the watcher ---
    ("pin-ignores-missing", "a passage not on the page fails the pin",
     "        ok = page == PAGE_READ and not missing", "        ok = page == PAGE_READ", WATCHER),
    ("pin-validator-trusts", "pin validators compare what they found",
     "            return str(_theirs.get(\"page\", \"\")) == _page and list(_theirs.get(\"found\", [])) == _found", "            return True", WATCHER),
    ("check-unspaced", "the watcher enforces the gap",
     "        if wait:\n            raise", "        if False:\n            raise", WATCHER),
    ("request-twice", "one request is open at a time",
     "    if pending:\n        return \"a check requested at", "    if False:\n        return \"a check requested at", CORE),
    ("request-unspaced", "requests are spaced by the gap",
     "    if last_request_at and int(now) < int(last_request_at) + int(gap):", "    if False:", CORE),
    ("request-at-the-end", "a request needs room before the end",
     "    if int(now) + observe_window(gap) > int(end):", "    if False:", CORE),
    ("expire-early", "a request expires only after its window",
     "        if self._now() <= int(pending[\"due\"]):", "        if False:", WATCHER),
    ("observe-late", "an observation after the window is refused",
     "        if now > int(pending[\"due\"]):\n            raise Exception(\"[EXPECTED] the check closed", "        if False:\n            raise Exception(\"[EXPECTED] the check closed", WATCHER),
    ("contested-forgiven", "a contested check counts like an absent page",
     "        self._record(source, cover_id, key, previous, pending, PAGE_CONTESTED, {}, int(pending[\"requested_at\"]))",
     "        self._record(source, cover_id, key, previous, pending, PAGE_READ, {\"kind\": CHECK_KEPT, \"passage\": \"\", \"reading\": \"\", \"confidence\": 0, \"reason\": \"\"}, int(pending[\"requested_at\"]))", WATCHER),
    ("no-auto-observe", "a request observes the page at once",
     "        gl.get_contract_at(self.address).emit(on=\"accepted\").observe(", "        (lambda *a: None)(", WATCHER),
    ("check-after-ended", "a cover that ended in a breach is not checked again",
     "        if previous.get(\"kind\") in ENDS_COVER:", "        if False:", WATCHER),
    ("validator-skips-page", "validators agree on what the page is",
     "            if str(_theirs.get(\"page\", \"\")) != _page:\n                return False", "            if False:\n                return False", WATCHER),
    ("validator-skips-presence", "validators agree on which passages are word for word",
     "            if _finding[\"kind\"] == CHECK_KEPT and _leader_present != _mine_present:", "            if False:", WATCHER),
    ("check-not-reported", "every check is reported to the treasury",
     "        gl.get_contract_at(Address(source)).emit(on=\"accepted\").note_check(", "        (lambda *a: None)(", WATCHER),
    ("model-on-every-passage", "a passage still word for word never reaches the jury",
     "                if passage_present(_text, _p[1]):\n                    _results.append(", "                if False:\n                    _results.append(", WATCHER),
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def main():
    files = sorted({m[4] for m in MUTATIONS})
    originals = {f: open(f).read() for f in files}
    snap = tempfile.mkdtemp()
    shutil.copytree(BUILD, os.path.join(snap, "build"))
    suite = [sys.executable, "-m", "pytest", "tests/direct", "-q", "-x", "-p", "no:cacheprovider"]
    if run(suite).returncode != 0:
        print("BASELINE SUITE IS RED")
        return 2
    killed, survived, unapplied = [], [], []
    try:
        for name, why, old, new, target in MUTATIONS:
            src = originals[target]
            if old == new or src.count(old) != 1:
                unapplied.append((name, why))
                continue
            try:
                open(target, "w").write(src.replace(old, new, 1))
                if run([sys.executable, "deploy/build_contract.py"]).returncode != 0:
                    killed.append(name)
                    continue
                result = run(suite)
            finally:
                open(target, "w").write(src)
            (killed if result.returncode != 0 else survived).append(name if result.returncode != 0 else (name, why))
    finally:
        for f, text in originals.items():
            open(f, "w").write(text)
        shutil.rmtree(BUILD)
        shutil.copytree(os.path.join(snap, "build"), BUILD)
        shutil.rmtree(snap)
    if run(suite).returncode != 0:
        print("RESTORE FAILED")
        return 3
    print("mutants killed   : %d" % len(killed))
    print("mutants survived : %d" % len(survived))
    print("not applied      : %d" % len(unapplied))
    for name, why in unapplied:
        print("  ?  %-30s %s" % (name, why))
    for name, why in survived:
        print("  !  %-30s UNTESTED: %s" % (name, why))
    return 1 if survived or unapplied else 0


if __name__ == "__main__":
    sys.exit(main())
