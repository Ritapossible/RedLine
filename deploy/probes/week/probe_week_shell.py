MIN_VISIBLE = 200  # characters of visible text below which a page is a shell, not a terms page


def classify(status, body, passage):
    """One check of one page, as a validator sees it: unreadable, present or absent."""
    if status < 200 or status >= 300:
        return {"class": "unreadable", "why": "status %d" % status}
    text = page_text(body or b"")
    if len(text) < MIN_VISIBLE:
        return {"class": "unreadable", "why": "under %d visible characters" % MIN_VISIBLE}
    if not passage:
        return {"class": "readable", "why": "no passage pinned"}
    return {"class": "present" if passage_present(text, passage) else "absent", "why": ""}


def as_dict(value):
    data = value
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", "replace")
    elif not isinstance(data, (dict, str)):
        data = str(data)
    for _ in range(3):
        if isinstance(data, dict):
            return data
        if not isinstance(data, str):
            return {}
        text = data.strip()
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start and not text.startswith('"'):
            text = text[start : end + 1]
        try:
            data = json.loads(text)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


class ProbeWeek(gl.Contract):
    """Milestone 1.5: a week of real terms pages, never the treasury.

    One check fetches one page with the watcher's call and text rules, and
    validators agree on its class only: unreadable, readable (no passage
    pinned), present or absent. A round where they cannot agree ends
    MAJORITY_DISAGREE and stores nothing; the runner records it as
    "disagreed". The last agreed result per page is kept.
    """

    last: TreeMap[str, str]
    checks: u256

    def __init__(self):
        pass

    @gl.public.write
    def check(self, key: str, url: str, passage: str) -> None:
        uri = str(url)
        pinned = str(passage)

        def leader() -> str:
            try:
                # INLINE fetch - the watcher's call.
                r = gl.nondet.web.get(uri)
                return json.dumps(classify(int(r.status), r.body, pinned))
            except Exception as e:
                return json.dumps({"class": "unreadable", "why": "fetch failed: " + type(e).__name__})

        def validator(leader_result) -> bool:
            try:
                # INLINE fetch again.
                r = gl.nondet.web.get(uri)
                mine = classify(int(r.status), r.body, pinned)
            except Exception as e:
                mine = {"class": "unreadable", "why": "fetch failed: " + type(e).__name__}
            return as_dict(leader_result).get("class") == mine["class"]

        self.last[str(key)] = json.dumps(as_dict(gl.vm.run_nondet(leader, validator)))
        self.checks = u256(int(self.checks) + 1)

    @gl.public.view
    def get(self, key: str) -> str:
        return self.last.get(str(key), "{}")
