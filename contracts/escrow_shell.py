"""RedLine escrow ledger: RedLine's rules for a prepay held somewhere else.

Built by ``deploy/build_contract.py`` into ``contracts/build/redline_escrow.py``
(and ``redline_escrow.min.py``, the bytes deployed). Do not edit the build.

The treasury (``treasury_shell.py``) holds the prepay itself, in GEN. This
contract holds nothing. The prepay sits in an escrow on another chain (an
Arkhai Alkahest escrow on Base Sepolia); this contract runs the same cover,
with the same rules (``redline_core``) and the same watcher, and publishes a
**ruling**: how much of the escrow the vendor earned and how much goes back
to the buyer. A relayer carries the ruling to the escrow's arbiter, which
pays out exactly that.

It works with the watcher already deployed, unchanged: the watcher reads a
cover from whichever contract asks it to (``get_cover``) and reports back by
message (``note_pin``, ``note_check``).

What this contract cannot see: the escrow itself. It records the escrow the
buyer names; the relayer must verify, on the escrow's chain, that the escrow
exists, was created by the cover's buyer, holds the cover's amount and names
the relayer as its oracle, before it carries any ruling there.
"""


def _hex_ok(value, digits):
    s = str(value).lower()
    return len(s) == 2 + digits and s.startswith("0x") and all(c in "0123456789abcdef" for c in s[2:])


class RedLineEscrow(gl.Contract):
    release: str
    watcher: str
    appeal_seconds: u256
    cover_count: u256
    covers: TreeMap[u256, str]
    escrows: TreeMap[u256, str]
    refusals: TreeMap[str, str]

    def __init__(self, watcher: str, appeal_seconds: int):
        if int(appeal_seconds) < 0 or int(appeal_seconds) > MAX_WINDOW:
            raise Exception("[EXPECTED] the appeal window is 0-%d seconds" % MAX_WINDOW)
        self.release = "redline-escrow/1"
        self.watcher = normalize_address(watcher, "watcher")
        self.appeal_seconds = u256(int(appeal_seconds))
        self.cover_count = u256(0)

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

    def _from_watcher(self) -> None:
        if self._me() != self.watcher:
            raise Exception("[EXPECTED] only the watcher contract reports on a cover")

    # ---------------------------------------------------------- entrypoints

    @gl.public.write
    def open_cover(self, vendor: str, url: str, passages_json: str, amount: int, coverage_seconds: int,
                   accept_seconds: int, check_gap_seconds: int, chain_id: int, escrow_uid: str, arbiter: str) -> int:
        """The buyer opens a cover for a prepay it has locked in an escrow:
        ``amount`` in that escrow's smallest unit, ``escrow_uid`` the escrow's
        id on chain ``chain_id``, ``arbiter`` the contract that will pay it
        out. Returns the cover id, or -1 when refused (``refusal_of`` says
        why). An opened cover asks the watcher to pin the page at once."""
        me = self._me()
        try:
            passages = json.loads(str(passages_json))
        except Exception:
            passages = None
        errors = ["the passages are not valid JSON"] if passages is None else cover_errors(
            buyer=me, vendor=str(vendor), url=str(url), passages=passages, value=int(amount),
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), passage_error=passage_error,
        )
        if int(chain_id) <= 0:
            errors.append("the escrow's chain id must be more than 0")
        if not _hex_ok(escrow_uid, 64):
            errors.append("the escrow id is 0x and 64 hex digits")
        if not _hex_ok(arbiter, 40):
            errors.append("the arbiter is an address")
        if errors:
            self.refusals[me] = json.dumps({"reason": "; ".join(errors)[:600], "at": self._now()})
            return -1
        cover_id = int(self.cover_count)
        cover = open_cover(
            cover_id=cover_id, buyer=me, vendor=str(vendor), url=str(url), passages=passages, amount=int(amount),
            coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds),
            check_gap_seconds=int(check_gap_seconds), now=self._now(),
        )
        self._save(cover)
        self.escrows[u256(cover_id)] = json.dumps(
            {"chain_id": int(chain_id), "escrow": str(escrow_uid).lower(), "arbiter": str(arbiter).lower(), "fulfillment": ""}
        )
        self.cover_count = u256(cover_id + 1)
        # A message, not a read: if the watcher fails, the cover simply is not
        # pinned and is refunded whole at its acceptance deadline.
        gl.get_contract_at(Address(self.watcher)).emit(on="accepted").pin(str(self.address).lower(), cover_id)
        return cover_id

    @gl.public.write
    def note_pin(self, cover_id: int, ok: bool, at: int, reason: str) -> None:
        """Sent by the watcher once it has fetched the page at opening."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            apply_pin(cover, ok=bool(ok), at=int(at), now=self._now(), reason=str(reason))
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)

    @gl.public.write
    def accept(self, cover_id: int, fulfillment_uid: str) -> None:
        """The vendor accepts the pinned terms and names its fulfillment of
        the escrow (the attestation the arbiter will pay against). The cover
        starts now."""
        if not _hex_ok(fulfillment_uid, 64):
            raise Exception("[EXPECTED] the fulfillment id is 0x and 64 hex digits")
        cover = self._load(cover_id)
        try:
            accept(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)
        escrow = json.loads(self.escrows[u256(int(cover_id))])
        escrow["fulfillment"] = str(fulfillment_uid).lower()
        self.escrows[u256(int(cover_id))] = json.dumps(escrow)

    @gl.public.write
    def cancel(self, cover_id: int) -> None:
        """The buyer withdraws an offer the vendor has not accepted."""
        cover = self._load(cover_id)
        try:
            cancel(cover, by=self._me(), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)

    @gl.public.write
    def note_check(self, cover_id: int, seq: int, kind: str, at: int, since: int) -> None:
        """Sent by the watcher after each check of the page."""
        self._from_watcher()
        cover = self._load(cover_id)
        try:
            apply_check(cover, seq=int(seq), kind=str(kind), at=int(at), since=int(since), now=self._now())
        except RedlineError as exc:
            raise Exception("[EXPECTED] " + str(exc))
        self._save(cover)

    @gl.public.write
    def settle(self, cover_id: int) -> None:
        """Apply every clock of a cover. Anyone may call it; it reads no other
        contract, so a cover always reaches a ruling."""
        cover = self._load(cover_id)
        apply_deadlines(cover, self._now(), int(self.appeal_seconds))
        self._save(cover)

    # ---------------------------------------------------------------- views

    @gl.public.view
    def get_cover(self, cover_id: int) -> str:
        cover = self._load(cover_id)
        cover["now"] = self._now()
        cover["outstanding"] = outstanding(cover)
        return json.dumps(cover)

    @gl.public.view
    def ruling_of(self, cover_id: int) -> str:
        """What the escrow should pay. ``final`` is false until the cover has
        closed; then ``vendor_amount`` + ``buyer_amount`` == ``amount``, and
        the ruling never changes again. ``started`` is false for a cover that
        closed before the vendor accepted: there is no fulfillment to pay
        against, and the buyer reclaims the escrow when it expires."""
        cover = self._load(cover_id)
        escrow = json.loads(self.escrows[u256(int(cover_id))])
        final = cover["state"] in CLOSED
        return json.dumps(
            {
                "cover": int(cover["id"]),
                "state": cover["state"],
                "final": final,
                "started": cover.get("start") is not None,
                "amount": int(cover["amount"]),
                "vendor": cover["vendor"],
                "buyer": cover["buyer"],
                "vendor_amount": int(cover["paid"]) if final else 0,
                "buyer_amount": int(cover.get("refunded", 0)) if final else 0,
                "as_of": int(cover.get("closed_as_of", cover.get("closed_at", 0))) if final else 0,
                "chain_id": escrow["chain_id"],
                "escrow": escrow["escrow"],
                "arbiter": escrow["arbiter"],
                "fulfillment": escrow["fulfillment"],
            }
        )

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
            }
        )
