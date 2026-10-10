"""RedLine watcher: the only contract that fetches the page or runs a model.

Built by ``deploy/build_contract.py`` into ``contracts/build/redline_watcher.py``
(and ``redline_watcher.min.py``, the bytes deployed). Do not edit the build.

It holds no GEN. It reads a cover from the treasury (a view), fetches the
vendor's terms page, records what it found here, and tells the treasury by a
message (``note_pin``, ``note_check``) that only this contract may send.

**Pinning** (``pin``, sent by the treasury when a cover is funded): every
validator fetches the page and checks that each pinned passage is on it word
for word. No model. A page that answers without them refuses the cover.

**Checking** has two steps, so that a check always ends in a record:

- ``check`` (anyone, at most once per ``check_gap_seconds``) is
  deterministic: it records a request and opens an observation window (half
  the gap), and the watcher sends itself ``observe``.
- ``observe`` (sent by the watcher; anyone may send it again inside the
  window) fetches the page and, if needed, asks the jury. What it finds:

- every passage still on the page word for word: kept. No model.
- a passage gone: the jury compares it with the parts of today's page most
  like it, and answers same, narrowed, removed or cannot_tell. A confident
  narrowed or removed is a breach; anything else is kept.
- no page (no answer, or 404/410): absent. ``ABSENT_LIMIT`` absent checks
  running are "gone", which ends the cover like a breach. No model.

- ``expire`` (anyone, after the window): a request with no agreed
  observation is recorded as **contested** - validators could not agree on
  what the page says, or no round completed. Contested counts exactly like
  absent: it holds the vendor's accrual, and ``ABSENT_LIMIT`` running end
  the cover. A vendor that shows the pinned text to some readers and not to
  others cannot keep being paid by making every round fail to agree.

Validators fail closed toward the vendor on what a page says: a breach
stands only if a validator re-reading the page finds it too. They fail
closed toward the buyer on whether the page can be read at all.

Hard rules (see docs/ARCHITECTURE.md):
- The fetch is written inline in both closures.
- Every value a closure captures is a plain Python value.
"""


class RedLineWatcher(gl.Contract):
    release: str
    records: TreeMap[str, str]
    pending: TreeMap[str, str]
    last_request: TreeMap[str, u256]
    checks: u256

    def __init__(self):
        self.release = "redline-watcher/2"
        self.checks = u256(0)

    def _now(self) -> int:
        return int(datetime.datetime.now().timestamp())

    def _key(self, treasury: str, cover_id: int) -> str:
        return "%s:%d" % (str(treasury).lower(), int(cover_id))

    def _cover(self, treasury: str, cover_id: int) -> dict:
        return json.loads(str(gl.get_contract_at(Address(treasury)).view().get_cover(int(cover_id))))

    @gl.public.write
    def pin(self, treasury: str, cover_id: int) -> None:
        """Fetch the page of a cover being pinned and check every passage is on
        it. Sent by the treasury when the cover is funded; anyone may send it
        again if that round could not fetch the page."""
        source = str(treasury).lower()
        cover = self._cover(source, cover_id)
        if cover["state"] != COVER_PINNING:
            raise Exception("[EXPECTED] the cover is not being pinned")
        uri = str(cover["url"])
        passages = [[str(p["id"]), str(p["text"])] for p in cover["passages"]]

        def leader() -> str:
            _page = PAGE_UNREAD
            _found = []
            try:
                # INLINE fetch - do not factor this into a helper.
                _resp = gl.nondet.web.get(uri)
                _status = int(_resp.status)
                if _status in MISSING_STATUS:
                    _page = PAGE_MISSING
                elif 200 <= _status < 300:
                    _page = PAGE_READ
                    _text = page_text(_resp.body or b"")
                    _found = [p[0] for p in passages if passage_present(_text, p[1])]
            except Exception:
                _page = PAGE_UNREAD
            return json.dumps({"page": _page, "found": _found})

        def validator(leader_result) -> bool:
            _page = PAGE_UNREAD
            _found = []
            try:
                # INLINE fetch again - the duplication is deliberate.
                _resp = gl.nondet.web.get(uri)
                _status = int(_resp.status)
                if _status in MISSING_STATUS:
                    _page = PAGE_MISSING
                elif 200 <= _status < 300:
                    _page = PAGE_READ
                    _text = page_text(_resp.body or b"")
                    _found = [p[0] for p in passages if passage_present(_text, p[1])]
            except Exception:
                _page = PAGE_UNREAD
            _theirs = as_dict(leader_result)
            return str(_theirs.get("page", "")) == _page and list(_theirs.get("found", [])) == _found

        decoded = as_dict(gl.vm.run_nondet(leader, validator, compare_user_errors=True))
        page = str(decoded.get("page", PAGE_UNREAD))
        if page == PAGE_UNREAD:
            raise Exception("[EXPECTED] the page could not be fetched, so nothing was pinned; send pin again before the acceptance deadline")
        found = [str(f) for f in decoded.get("found", [])]
        missing = [p[0] for p in passages if p[0] not in found]
        ok = page == PAGE_READ and not missing
        reason = "" if ok else ("the page answered 404/410" if page == PAGE_MISSING else "not on the page: " + ", ".join(missing))
        now = self._now()
        self.records[self._key(source, cover_id) + ":pin"] = json.dumps({"page": page, "found": found, "ok": ok, "reason": reason, "at": now})
        gl.get_contract_at(Address(source)).emit(on="accepted").note_pin(int(cover_id), ok, now, reason[:200])

    def _record(self, source: str, cover_id: int, key: str, previous: dict, pending: dict, page: str, finding: dict, at: int) -> None:
        """Record one check, close its request, and report it to the treasury."""
        record = next_record(previous, seq=int(pending["seq"]), page=page, finding=finding, now=at)
        self.records[key] = json.dumps(record)
        self.pending[key] = ""
        self.checks = u256(int(self.checks) + 1)
        gl.get_contract_at(Address(source)).emit(on="accepted").note_check(
            int(cover_id), int(record["seq"]), str(record["kind"]), int(record["at"]), int(record["since"])
        )

    @gl.public.write
    def check(self, treasury: str, cover_id: int) -> None:
        """Request a check of an active cover's page. Anyone may call it, at
        most once per ``check_gap_seconds``. Deterministic: it always records
        the request, and the watcher sends itself ``observe`` at once."""
        source = str(treasury).lower()
        cover = self._cover(source, cover_id)
        if cover["state"] != COVER_ACTIVE:
            raise Exception("[EXPECTED] the cover is not active")
        now = self._now()
        key = self._key(source, cover_id)
        previous = json.loads(self.records.get(key, "{}"))
        if previous.get("kind") in ENDS_COVER:
            raise Exception("[EXPECTED] this cover already ended in a %s; settle closes it" % previous["kind"])
        pending = json.loads(self.pending.get(key, "") or "{}")
        gap = int(cover["check_gap_seconds"])
        wait = request_error(pending=pending, last_request_at=int(self.last_request.get(key, u256(0))), now=now, gap=gap, end=int(cover["end"]))
        if wait:
            raise Exception("[EXPECTED] " + wait)
        self.pending[key] = json.dumps({"seq": int(previous.get("seq", 0)) + 1, "requested_at": now, "due": now + observe_window(gap)})
        self.last_request[key] = u256(now)
        gl.get_contract_at(self.address).emit(on="accepted").observe(source, int(cover_id))

    @gl.public.write
    def expire(self, treasury: str, cover_id: int) -> None:
        """Close a request that got no agreed observation in its window. It is
        recorded as contested, which counts like a page that did not answer."""
        source = str(treasury).lower()
        key = self._key(source, cover_id)
        pending = json.loads(self.pending.get(key, "") or "{}")
        if not pending:
            raise Exception("[EXPECTED] no check is open for this cover")
        if self._now() <= int(pending["due"]):
            raise Exception("[EXPECTED] the check is open until %d; observe it until then" % int(pending["due"]))
        previous = json.loads(self.records.get(key, "{}"))
        self._record(source, cover_id, key, previous, pending, PAGE_CONTESTED, {}, int(pending["requested_at"]))

    @gl.public.write
    def observe(self, treasury: str, cover_id: int) -> None:
        """Fetch the page for the open request and decide what it shows. Sent by
        the watcher when a check is requested; anyone may send it again while
        the request is open, if a round did not agree."""
        source = str(treasury).lower()
        key = self._key(source, cover_id)
        pending = json.loads(self.pending.get(key, "") or "{}")
        if not pending:
            raise Exception("[EXPECTED] no check is open for this cover; request one with check")
        now = self._now()
        if now > int(pending["due"]):
            raise Exception("[EXPECTED] the check closed at %d; expire records it as contested" % int(pending["due"]))
        cover = self._cover(source, cover_id)
        if cover["state"] != COVER_ACTIVE:
            raise Exception("[EXPECTED] the cover is not active")
        previous = json.loads(self.records.get(key, "{}"))
        uri = str(cover["url"])
        passages = [[str(p["id"]), str(p["text"])] for p in cover["passages"]]

        def leader() -> str:
            _page = PAGE_UNREAD
            _text = ""
            try:
                # INLINE fetch - do not factor this into a helper.
                _resp = gl.nondet.web.get(uri)
                _status = int(_resp.status)
                if _status in MISSING_STATUS:
                    _page = PAGE_MISSING
                elif 200 <= _status < 300:
                    _page = PAGE_READ
                    _text = page_text(_resp.body or b"")
            except Exception:
                _page = PAGE_UNREAD
            if _page != PAGE_READ:
                return json.dumps({"page": _page})
            _results = []
            for _p in passages:
                if passage_present(_text, _p[1]):
                    _results.append({"passage": _p[0], "present": True, "reading": READ_SAME, "confidence": 100, "reason": "word_for_word"})
                    continue
                _ans = read_answer(gl.nondet.exec_prompt(build_prompt(pinned=_p[1], excerpts=excerpts(_text, _p[1])), response_format="json"))
                _results.append({"passage": _p[0], "present": False, "reading": _ans["reading"],
                                 "confidence": _ans["confidence"], "reason": _ans["reason"]})
                if reading_to_kind(_ans["reading"], _ans["confidence"]) == CHECK_BREACH:
                    break
            _finding = decide(_results)
            return json.dumps({"page": _page, "present": [r["passage"] for r in _results if r["present"]], "finding": _finding})

        def validator(leader_result) -> bool:
            _page = PAGE_UNREAD
            _text = ""
            try:
                # INLINE fetch again - the duplication is deliberate.
                _resp = gl.nondet.web.get(uri)
                _status = int(_resp.status)
                if _status in MISSING_STATUS:
                    _page = PAGE_MISSING
                elif 200 <= _status < 300:
                    _page = PAGE_READ
                    _text = page_text(_resp.body or b"")
            except Exception:
                _page = PAGE_UNREAD
            _theirs = as_dict(leader_result)
            if str(_theirs.get("page", "")) != _page:
                return False
            if _page != PAGE_READ:
                return True
            _finding = _theirs.get("finding", {})
            if not isinstance(_finding, dict) or _finding.get("kind") not in (CHECK_KEPT, CHECK_BREACH):
                return False
            # Which passages are still word for word must match exactly, in pin
            # order, up to the passage the leader stopped at.
            _mine_present = []
            _own_kind = CHECK_KEPT
            for _p in passages:
                if passage_present(_text, _p[1]):
                    _mine_present.append(_p[0])
                    continue
                if _finding["kind"] == CHECK_BREACH and _p[0] != _finding.get("passage"):
                    continue  # a breach is judged on the passage the leader ruled
                _ans = read_answer(gl.nondet.exec_prompt(build_prompt(pinned=_p[1], excerpts=excerpts(_text, _p[1])), response_format="json"))
                if reading_to_kind(_ans["reading"], _ans["confidence"]) == CHECK_BREACH:
                    _own_kind = CHECK_BREACH
                    break
            _leader_present = [str(x) for x in _theirs.get("present", [])]
            if _finding["kind"] == CHECK_KEPT and _leader_present != _mine_present:
                return False
            if _finding["kind"] == CHECK_BREACH and _finding.get("passage") in _mine_present:
                return False
            return jury_agrees(leader_kind=_finding["kind"], own_kind=_own_kind)

        decoded = as_dict(gl.vm.run_nondet(leader, validator, compare_user_errors=True))
        page = str(decoded.get("page", PAGE_UNREAD))
        finding = decoded.get("finding", {}) if page == PAGE_READ else {}
        if page == PAGE_READ and finding.get("kind") not in (CHECK_KEPT, CHECK_BREACH):
            finding = {"kind": CHECK_KEPT, "passage": "", "reading": READ_CANNOT_TELL, "confidence": 0, "reason": "unreadable_answer"}
        self._record(source, cover_id, key, previous, pending, page, finding, now)

    @gl.public.view
    def record_of(self, treasury: str, cover_id: int) -> str:
        """The latest check of a cover, or {}."""
        return self.records.get(self._key(treasury, cover_id), "{}")

    @gl.public.view
    def pending_of(self, treasury: str, cover_id: int) -> str:
        """The open check request of a cover, or {}."""
        return self.pending.get(self._key(treasury, cover_id), "") or "{}"

    @gl.public.view
    def pin_of(self, treasury: str, cover_id: int) -> str:
        return self.records.get(self._key(treasury, cover_id) + ":pin", "{}")

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"release": self.release, "checks": int(self.checks)})
