"""The panel: several models read one pinned passage against today's page.

Asked only when code cannot decide (``redline_prompts.jury_question`` returned
a question). Each answer is read by ``redline_prompts.read_answer``. The panel
fails closed toward the vendor (architecture 8.2):

- breach: at least ``quorum`` models read narrowed or removed with confidence
  >= MIN_BREACH_CONFIDENCE, and no model reads same with that confidence;
- contested: confident cut readings and a confident same reading disagree.
  Counted as kept; asked again at the next check. Contested never cuts;
- kept: everything else, including errors, timeouts and cannot_tell.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from .core import core, prompts

CUT = core.BREACH_READINGS
SURE = core.MIN_BREACH_CONFIDENCE


class Panel:
    def __init__(self, models, quorum=None, timeout=60):
        if not models:
            raise ValueError("a panel needs at least one model")
        self.models = dict(models)
        self.quorum = int(quorum) if quorum else len(self.models) // 2 + 1
        if not 1 <= self.quorum <= len(self.models):
            raise ValueError("quorum %d is outside 1..%d" % (self.quorum, len(self.models)))
        self.timeout = timeout

    def _ask(self, name, question):
        try:
            answer = prompts.read_answer(self.models[name](question))
            return {"seat": name, **answer}
        except Exception as exc:  # an error is doubt, never a cut
            return {"seat": name, "reading": core.READ_CANNOT_TELL, "confidence": 0, "reason": "",
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

    def read(self, question):
        """``{reading, confidence, contested, votes}`` for one passage."""
        names = list(self.models)
        pool = ThreadPoolExecutor(max_workers=len(names))
        try:
            futures = {n: pool.submit(self._ask, n, question) for n in names}
            deadline = time.monotonic() + self.timeout
            votes = []
            for n in names:
                try:
                    votes.append(futures[n].result(timeout=max(0.0, deadline - time.monotonic())))
                except Exception:
                    votes.append({"seat": n, "reading": core.READ_CANNOT_TELL, "confidence": 0, "reason": "",
                                  "error": "no answer in time"})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return aggregate(votes, self.quorum)


def aggregate(votes, quorum):
    cut = [v for v in votes if v["reading"] in CUT and v["confidence"] >= SURE]
    same = [v for v in votes if v["reading"] == core.READ_SAME and v["confidence"] >= SURE]
    if cut and same:
        return {"reading": core.READ_CANNOT_TELL, "confidence": 0, "contested": True, "votes": votes}
    if len(cut) >= quorum:
        reading = core.READ_REMOVED if sum(v["reading"] == core.READ_REMOVED for v in cut) * 2 > len(cut) else core.READ_NARROWED
        return {"reading": reading, "confidence": min(v["confidence"] for v in cut), "contested": False, "votes": votes}
    if same:
        return {"reading": core.READ_SAME, "confidence": min(v["confidence"] for v in same), "contested": False, "votes": votes}
    return {"reading": core.READ_CANNOT_TELL, "confidence": 0, "contested": False, "votes": votes}
