# v0.2.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


def as_dict(value):
    """The leader's result, however it arrives (dict, JSON text, or a wrapper
    whose str() is the payload), as the watcher decodes it. {} if unreadable."""
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


class ProbeRedirect(gl.Contract):
    """Milestone 1.3: does a validator's plain fetch follow an HTTP redirect?

    For one URL, every validator fetches it with gl.nondet.web.get and
    reports the status it saw, the size of the body and whether a known
    sentence is in it. They must agree on all three. A followed redirect
    shows the target's status (200) and the sentence; an unfollowed one
    shows the 3xx status and no sentence. The result is stored under the URL.
    """

    results: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def probe(self, url: str, marker: str) -> None:
        uri = str(url)
        mark = str(marker)

        def leader() -> str:
            try:
                # INLINE fetch - the same call the watcher makes.
                r = gl.nondet.web.get(uri)
                body = r.body or b""
                return json.dumps({"status": int(r.status), "bytes": len(body), "marker": mark.encode() in body, "error": ""})
            except Exception as e:
                return json.dumps({"status": 0, "bytes": 0, "marker": False, "error": type(e).__name__})

        def validator(leader_result) -> bool:
            try:
                # INLINE fetch again.
                r = gl.nondet.web.get(uri)
                body = r.body or b""
                mine = {"status": int(r.status), "bytes": len(body), "marker": mark.encode() in body, "error": ""}
            except Exception as e:
                mine = {"status": 0, "bytes": 0, "marker": False, "error": type(e).__name__}
            theirs = as_dict(leader_result)
            return theirs.get("status") == mine["status"] and theirs.get("marker") == mine["marker"] and theirs.get("error") == mine["error"]

        self.results[uri] = json.dumps(as_dict(gl.vm.run_nondet(leader, validator)))

    @gl.public.view
    def get(self, url: str) -> str:
        return self.results.get(str(url), "{}")
