"""RedLine treasury: holds the prepay, runs every clock, never runs a model.

Built by ``deploy/build_contract.py`` into ``contracts/build/redline.py`` (and
``redline.min.py``, the bytes deployed). Do not edit the build.

It never reads the watcher contract. The watcher reports to it by messages
(``note_pin``, ``note_check``) that only the watcher may send, and the
treasury sends the watcher one message of its own: when a cover is funded, it
asks the watcher to pin the page. Every payout is the treasury's own
arithmetic on its own clock (``settle``), so if the watcher is appealed into
an unreadable state, a breach already reported still refunds once its appeal
window passes, and a cover with none still pays the vendor at its end.

**Money.** A payable call never reverts once value has arrived: measured on
Studio, the value sent with a call that reverts stays in the contract. A
refused funding is recorded instead and its value credited straight back
(``_refuse``). Settling *credits* what each party is owed (``owed``); only
``withdraw`` sends GEN.
"""


@gl.evm.contract_interface
class _Payee:
    """Any address, as a value recipient."""

    class View:
        pass

    class Write:
        pass


class RedLine(gl.Contract):
    release: str
    watcher: str
    appeal_seconds: u256
    cover_count: u256
    covers: TreeMap[u256, str]
    owed: TreeMap[str, u256]
    owed_total: u256
    held: u256
    refusals: TreeMap[str, str]

    def __init__(self, watcher: str, appeal_seconds: int):
        if int(appeal_seconds) < 0 or int(appeal_seconds) > MAX_WINDOW:
            raise Exception("[EXPECTED] the appeal window is 0-%d seconds" % MAX_WINDOW)
        self.release = "redline/1"
        self.watcher = normalize_address(watcher, "watcher")
        self.appeal_seconds = u256(int(appeal_seconds))
        self.cover_count = u256(0)
        self.owed_total = u256(0)
        self.held = u256(0)

    # -------------------------------------------------------------- helpers

    def _now(self) -> int:
        return int(datetime.datetime.now().timestamp())

    def _me(self) -> str:
        return str(gl.message.sender_address).lower()

    def _load(self, cover_id: int) -> dict:
        if int(cover_id) < 0 or int(cover_id) >= int(self.cover_count):
            raise Exception("[EXPECTED] unknown cover")
        return json.loads(self.covers[u256(int(cover_id))])

    def _save(self, cover: dict) -> None:
        self.covers[u256(int(cover["id"]))] = json.dumps(cover)

    def _pay(self, credits: dict) -> None:
        """Move credited GEN from held prepay to what each party is owed."""
        total = 0
        for who, amount in credits.items():
            key = str(who).lower()
            self.owed[key] = u256(int(self.owed.get(key, u256(0))) + int(amount))
            total += int(amount)
        self.held = u256(int(self.held) - total)
        self.owed_total = u256(int(self.owed_total) + total)

    def _refuse(self, reason: str, value: int) -> None:
        me = self._me()
        if value > 0:
            self.owed[me] = u256(int(self.owed.get(me, u256(0))) + value)
            self.owed_total = u256(int(self.owed_total) + value)
        self.refusals[me] = json.dumps({"reason": str(reason)[:600], "at": self._now(), "returned": value})

    def _from_watcher(self) -> None:
        if self._me() != self.watcher:
            raise Exception("[EXPECTED] only the watcher contract reports on a cover")

    # ---------------------------------------------------------- entrypoints

    @gl.public.write.payable
    def open_cover(self, vendor: str, url: str, passages_json: str, coverage_seconds: int, accept_seconds: int,
                   check_gap_seconds: int) -> int:
        """The buyer prepays a vendor and pins the passages of its terms page it
        relies on. The value sent is the prepay. Returns the cover id, or -1
        when refused - the value is then credited back and ``refusal_of`` says
        why. A funded cover asks the watcher to pin the page at once."""
        value = int(gl.message.value)
        try:
            passages = json.loads(str(passages_json))
        except Exception:
            passages = None
        errors = ["the passages are not valid JSON"] if passages is None else cover_errors(
            buyer=self._me(), vendor=str(vendor), url=str(url), passages=passages, value=value,
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), passage_error=passage_error,
        )
        if errors:
            self._refuse("; ".join(errors), value)
            return -1
        cover_id = int(self.cover_count)
        cover = open_cover(
            cover_id=cover_id, buyer=self._me(), vendor=str(vendor), url=str(url), passages=passages, amount=value,
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), now=self._now(),
        )
        self._save(cover)
        self.cover_count = u256(cover_id + 1)
        self.held = u256(int(self.held) + value)
        # A message, not a read: if the watcher fails, the cover simply is not
        # pinned and refunds at its acceptance deadline.
        gl.get_contract_at(Address(self.watcher)).emit(on="accepted").pin(str(self.address).lower(), cover_id)
        return cover_id

    @gl.public.write
    def note_pin(self, cover_id: int, ok: bool, at: int, reason: str) -> None:
        """Sent by the watcher once it has fetched the page at funding."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            credits = apply_pin(cover, ok=bool(ok), at=int(at), now=self._now(), reason=str(reason))
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def accept(self, cover_id: int) -> None:
        """The vendor accepts the pinned terms; the cover starts now."""
        cover = self._load(cover_id)
        try:
            accept(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)

    @gl.public.write
    def cancel(self, cover_id: int) -> None:
        """The buyer withdraws an offer the vendor has not accepted."""
        cover = self._load(cover_id)
        try:
            credits = cancel(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def note_check(self, cover_id: int, seq: int, kind: str, at: int, since: int) -> None:
        """Sent by the watcher after each check of the page."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            credits = apply_check(cover, seq=int(seq), kind=str(kind), at=int(at), since=int(since), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def settle(self, cover_id: int) -> None:
        """Apply every clock of a cover. Anyone may call it; it reads no other
        contract, so a cover always resolves."""
        cover = self._load(cover_id)
        credits = apply_deadlines(cover, self._now(), int(self.appeal_seconds))
        self._save(cover)
        self._pay(credits)

    @gl.public.write
    def withdraw(self) -> None:
        """Send the caller everything it is owed."""
        me = self._me()
        amount = int(self.owed.get(me, u256(0)))
        if amount <= 0:
            raise Exception("[EXPECTED] nothing is owed to this address")
        self.owed[me] = u256(0)
        self.owed_total = u256(int(self.owed_total) - amount)
        _Payee(gl.message.sender_address).emit_transfer(value=u256(amount))

    # ---------------------------------------------------------------- views

    @gl.public.view
    def get_cover(self, cover_id: int) -> str:
        cover = self._load(cover_id)
        cover["now"] = self._now()
        cover["outstanding"] = outstanding(cover)
        return json.dumps(cover)

    @gl.public.view
    def owed_to(self, address: str) -> int:
        return int(self.owed.get(str(address).lower(), u256(0)))

    @gl.public.view
    def refusal_of(self, address: str) -> str:
        return self.refusals.get(str(address).lower(), "{}")

    @gl.public.view
    def status(self) -> str:
        return json.dumps(
            {
                "release": self.release,
                "watcher": self.watcher,
                "appeal_seconds": int(self.appeal_seconds),
                "covers": int(self.cover_count),
                "held": int(self.held),
                "owed": int(self.owed_total),
                "balance": int(self.balance),
            }
        )
