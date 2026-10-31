"""RedLine's memory: SQLite (a file, or ``:memory:`` for tests) or Postgres
(a ``postgresql://`` URL, for hosts whose disk does not persist), behind one
small adapter: ``execute(sql, params)`` with ``?`` placeholders, and
``script(sql)``. Adapted from Remit for PayPal's store.

What is kept, and why, is in docs/PAYPAL-ARCHITECTURE.md section 5. In short:
a cover's ``core`` column is the redline_core cover dict, the only truth for
its state and money; the columns beside it exist for queries. PayPal appears
only as ids, statuses and amounts, never a response body.
"""

import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS vendors (
  token        TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  product      TEXT NOT NULL,
  terms_url    TEXT NOT NULL,
  price_cents  BIGINT NOT NULL,
  cover_seconds BIGINT NOT NULL,
  gap_seconds  BIGINT NOT NULL,
  version      TEXT NOT NULL,
  demo         INTEGER NOT NULL,
  created_at   BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS covers (
  token        TEXT PRIMARY KEY,
  vendor_token TEXT NOT NULL,
  state        TEXT NOT NULL,
  amount_cents BIGINT NOT NULL,
  currency     TEXT NOT NULL,
  demo         INTEGER NOT NULL,
  created_at   BIGINT NOT NULL,
  core         TEXT NOT NULL,
  extra        TEXT NOT NULL,
  order_id     TEXT NOT NULL,
  authorizations TEXT NOT NULL,
  next_check_at BIGINT,
  lease_owner  TEXT,
  lease_until  BIGINT,
  version      BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
  cover_token  TEXT NOT NULL,
  seq          BIGINT NOT NULL,
  at           BIGINT NOT NULL,
  body         TEXT NOT NULL,
  PRIMARY KEY (cover_token, seq)
);
CREATE TABLE IF NOT EXISTS snapshots (
  sha256       TEXT PRIMARY KEY,
  text         TEXT NOT NULL,
  first_seen_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS paypal_ops (
  request_id   TEXT PRIMARY KEY,
  cover_token  TEXT NOT NULL,
  step         INTEGER NOT NULL,
  kind         TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  amount_cents BIGINT NOT NULL,
  final        INTEGER NOT NULL,
  state        TEXT NOT NULL,
  result_id    TEXT NOT NULL,
  paypal_status TEXT NOT NULL,
  error        TEXT NOT NULL,
  created_at   BIGINT NOT NULL,
  finished_at  BIGINT
);
CREATE TABLE IF NOT EXISTS log (
  seq   BIGINT PRIMARY KEY,
  at    BIGINT NOT NULL,
  kind  TEXT NOT NULL,
  body  TEXT NOT NULL,
  prev  TEXT NOT NULL,
  hash  TEXT NOT NULL
);
"""


class _Sqlite:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.integrity = sqlite3.IntegrityError
        self.lock = threading.RLock()

    def execute(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params)

    def script(self, sql):
        with self.lock:
            self.conn.executescript(sql)


class _Postgres:
    """Postgres through psycopg, autocommit. A dropped connection (a hosted
    database sleeping when idle) is reopened once and the statement retried."""

    def __init__(self, url):
        import psycopg

        self.psycopg, self.url = psycopg, url
        self.integrity = psycopg.errors.IntegrityError
        self.lock = threading.RLock()
        self.conn = psycopg.connect(url, autocommit=True)

    def execute(self, sql, params=()):
        sql = sql.replace("?", "%s")
        with self.lock:
            try:
                return self.conn.execute(sql, params)
            except self.psycopg.OperationalError:
                self.conn = self.psycopg.connect(self.url, autocommit=True)
                return self.conn.execute(sql, params)

    def script(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)


def open_store(path=":memory:"):
    db = _Postgres(path) if str(path).startswith(("postgres://", "postgresql://")) else _Sqlite(path)
    db.script(SCHEMA)
    return db
