"""Models behind any OpenAI-compatible chat API. Errors propagate; the
panel counts them as unsure. Adapted from Remit for PayPal's models: a
rate-limited call waits as asked (at most 20 s, twice), and a reasoning
model's <think> block is never read as its answer.

Model identifiers are configuration, never in the repository."""

import re
import time

import httpx

THINK = re.compile(r"<think>.*?(</think>|$)", re.S)
MAX_WAIT = 20.0


def without_thinking(text):
    return THINK.sub("", text or "").strip()


def retry_after(response):
    if response.status_code != 429:
        return None
    wait = None
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        m = re.search(r"try again in ([0-9.]+)\s*(ms|s)\b", response.text)
        if m:
            wait = float(m.group(1)) / (1000 if m.group(2) == "ms" else 1)
    wait = 2.0 if wait is None else wait + 0.5
    return wait if wait <= MAX_WAIT else None


class ModelError(Exception):
    """The API refused: its status and its own one-line message (never the prompt)."""

    def __init__(self, status, message):
        super().__init__("HTTP %d: %s" % (status, message))
        self.status = status


def api_message(r):
    try:
        e = r.json().get("error", {})
        msg = e.get("message") if isinstance(e, dict) else str(e)
    except Exception:
        msg = ""
    return " ".join(str(msg or r.reason_phrase).split())[:160]


class ChatModel:
    """A callable: prompt in, the model's answer text out. Temperature 0."""

    def __init__(self, model, api_key, base_url, timeout=45.0, transport=None, max_tokens=2000, sleep=time.sleep):
        if not api_key:
            raise ValueError("a model API key is required")
        self.model, self.max_tokens, self.sleep = model, max_tokens, sleep
        self.http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport,
                                 headers={"Authorization": "Bearer " + api_key})

    def __call__(self, prompt):
        body = {"model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        r = self.http.post("/chat/completions", json=body)
        for _ in range(2):
            wait = retry_after(r)
            if wait is None:
                break
            self.sleep(wait)
            r = self.http.post("/chat/completions", json=body)
        if r.status_code >= 400:
            raise ModelError(r.status_code, api_message(r))
        return without_thinking(r.json()["choices"][0]["message"]["content"])
