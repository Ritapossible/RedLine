"""The public log: append-only and hash-chained. Each entry stores the
SHA-256 of the one before it, so editing or deleting a past entry breaks
every hash after it (``verify``). The newest hash is anchored on GenLayer.

Entries hold ids, statuses, amounts and hashes of what was read; never a
customer's or payer's personal details, and never PayPal's response bodies.
Adapted from Remit for PayPal's ledger.
"""

import hashlib
import json
import threading

GENESIS = "0" * 64


def entry_hash(prev, seq, at, kind, body_text):
    payload = json.dumps([prev, seq, at, kind, body_text], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self, db):
        self.db = db
        self.lock = threading.RLock()

    def append(self, at, kind, body):
        """Add one entry. Another process (the scheduled worker) may append at
        the same time: a lost race on the sequence number is retried on the
        new head; a replay of this very entry is not a second entry."""
        text = json.dumps(body, separators=(",", ":"), sort_keys=True)
        with self.lock:
            for _ in range(5):
                row = self.db.execute("SELECT seq, hash FROM log ORDER BY seq DESC LIMIT 1").fetchone()
                seq, prev = (row[0] + 1, row[1]) if row else (1, GENESIS)
                h = entry_hash(prev, seq, int(at), kind, text)
                try:
                    self.db.execute("INSERT INTO log VALUES (?,?,?,?,?,?)", (seq, int(at), kind, text, prev, h))
                    return seq, h
                except self.db.integrity:
                    if self.hash_at(seq) == h:
                        return seq, h
            raise RuntimeError("the log is too busy to append to")

    def entries(self, since=0, limit=None):
        sql = "SELECT seq, at, kind, body, prev, hash FROM log WHERE seq > ? ORDER BY seq"
        params = (int(since),)
        if limit is not None:
            sql, params = sql + " LIMIT ?", params + (int(limit),)
        rows = self.db.execute(sql, params)
        return [{"seq": s, "at": a, "kind": k, "body": json.loads(b), "prev": p, "hash": h} for s, a, k, b, p, h in rows]

    def head(self):
        row = self.db.execute("SELECT seq, hash FROM log ORDER BY seq DESC LIMIT 1").fetchone()
        return {"seq": row[0], "hash": row[1]} if row else None

    def hash_at(self, seq):
        row = self.db.execute("SELECT hash FROM log WHERE seq = ?", (int(seq),)).fetchone()
        return row[0] if row else None

    def verify(self):
        prev = GENESIS
        for s, a, k, b, p, h in self.db.execute("SELECT seq, at, kind, body, prev, hash FROM log ORDER BY seq"):
            if p != prev or entry_hash(p, s, a, k, b) != h:
                return False, s
            prev = h
        return True, None
