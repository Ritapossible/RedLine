"""RedLine for PayPal's HTTP API: the routes of paypal/web/src/api/http.ts,
returning the types of paypal/web/src/api/types.ts unchanged. Errors are
``{"detail": sentence}``.

    uvicorn redline_paypal.web:app

A tick every 15 seconds runs what fell due for demo covers; the scheduled
worker (worker.py) covers the rest while this process sleeps.
"""

import asyncio
import contextlib
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from . import demo
from .config import App
from .covers import CoverError
from .vendors import VendorError, vendor_json

TICK_SECONDS = 15
MAX_BODY = 32_000


def create_app(env=os.environ, **kw):
    state = {}

    def app_():
        if "app" not in state:
            state["app"] = App(env, **kw)
        return state["app"]

    @contextlib.asynccontextmanager
    async def lifespan(_):
        app_()
        task = asyncio.create_task(ticker()) if env.get("REDLINE_TICK", "1") == "1" else None
        yield
        if task:
            task.cancel()

    async def ticker():
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                await asyncio.to_thread(app_().covers.tick)
            except Exception as exc:  # the next tick tries again; the journal makes that safe
                print("tick failed: %s" % type(exc).__name__, flush=True)

    api = FastAPI(title="RedLine for PayPal", lifespan=lifespan, docs_url=None, redoc_url=None)
    origins = [o.strip() for o in env.get("REDLINE_WEB_ORIGINS", "https://redline-paypal.vercel.app").split(",") if o.strip()]
    api.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["Content-Type"])

    @api.exception_handler(CoverError)
    @api.exception_handler(VendorError)
    async def refused(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @api.exception_handler(Exception)
    async def failed(_, exc):
        print("error: %s" % type(exc).__name__, flush=True)
        return JSONResponse({"detail": "Something went wrong on RedLine's server. Nothing was charged twice; try again."},
                            status_code=500)

    async def body(request):
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise CoverError(413, "That request is too large.")
        try:
            import json
            data = json.loads(raw or b"{}")
        except ValueError:
            raise CoverError(400, "The request is not JSON.")
        if not isinstance(data, dict):
            raise CoverError(400, "The request is not a JSON object.")
        return data

    def passages_from(data):
        ps = data.get("passages")
        if not isinstance(ps, list) or not all(isinstance(p, dict) for p in ps):
            raise CoverError(422, "passages must be a list of {id, text, label}.")
        out = []
        for p in ps[:8]:
            pid, text, label = p.get("id"), p.get("text"), p.get("label", "")
            if not isinstance(pid, str) or not isinstance(text, str) or not isinstance(label, str):
                raise CoverError(422, "Each passage has a string id, text and label.")
            out.append({"id": pid.strip()[:40], "text": text[:2000], "label": label.strip()[:60] or pid.strip()[:40]})
        return out

    def run(fn, *args):
        return asyncio.to_thread(fn, *args)

    # ------------------------------------------------------------- routes
    @api.get("/api/health")
    async def health():
        a = app_()
        return {"mode": "preview" if a.offline else "sandbox",
                "build": (os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or None}

    @api.post("/api/demo/vendors")
    async def create_vendor():
        a = app_()
        v = await run(a.vendors.create_demo)
        a.ledger.append(int(a.clock()), "demo_vendor", {"vendor": v["token"][:8]})
        return vendor_json(v)

    @api.get("/api/demo/terms-versions")
    async def versions():
        return demo.VERSIONS

    @api.get("/api/vendors/{token}")
    async def vendor(token: str):
        return vendor_json(await run(app_().vendors.get, token))

    @api.get("/api/vendors/{token}/terms")
    async def terms(token: str):
        a = app_()
        return await run(a.vendors.page, token, a.read_page)

    @api.put("/api/demo/vendors/{token}/version")
    async def set_version(token: str, request: Request):
        a = app_()
        data = await body(request)
        v = await run(a.vendors.set_version, token, str(data.get("version", "")))
        a.ledger.append(int(a.clock()), "terms_version", {"vendor": token[:8], "version": v["version"]})
        return vendor_json(v)

    @api.get("/api/vendors/{token}/covers")
    async def vendor_covers(token: str):
        a = app_()
        await run(a.vendors.get, token)
        return await run(a.covers.vendor_covers, token)

    @api.get("/api/vendors/{token}/suggestions")
    async def suggestions(token: str):
        a = app_()
        return await run(a.vendors.suggestions, token, a.read_page)

    @api.post("/api/vendors/{token}/pins/verify")
    async def verify(token: str, request: Request):
        a = app_()
        v = await run(a.vendors.get, token)
        return await run(a.covers.pin_problems, v, passages_from(await body(request)))

    @api.post("/api/checkout")
    async def checkout(request: Request):
        a = app_()
        data = await body(request)
        v = await run(a.vendors.get, str(data.get("vendor", "")))
        c = await run(a.covers.start_checkout, v, passages_from(data))
        return {"cover": a.covers.view(c), "orderId": c["order_id"]}

    @api.post("/api/covers/{token}/approve")
    async def approve(token: str, request: Request):
        a = app_()
        data = await body(request)
        c = await run(a.covers.approve, token, str(data.get("orderId", "")))
        return a.covers.view(c)

    @api.post("/api/covers/{token}/test-card")
    async def test_card(token: str):
        a = app_()
        return a.covers.view(await run(a.covers.pay_with_test_card, token, a.card))

    @api.get("/api/covers/{token}")
    async def cover(token: str):
        a = app_()
        return a.covers.view(await run(a.covers.catch_up, token))

    @api.post("/api/covers/{token}/check")
    async def check(token: str):
        a = app_()
        c = await run(a.covers.load, token)
        if not c["demo"]:
            raise CoverError(403, "Checks of a real vendor run on schedule.")
        return a.covers.view(await run(a.covers.check_now, token))

    @api.get("/api/log")
    async def log(tail: int = 200):
        a = app_()
        tail = max(1, min(int(tail), 500))
        head = a.ledger.head()
        n = head["seq"] if head else 0
        ok, _ = await run(a.ledger.verify)
        return {"verifies": ok, "head": n, "entries": await run(a.ledger.entries, max(0, n - tail)),
                "anchor": {"network": "GenLayer Studio", "matches": None}}

    # ------------------------------------------------- the demo's own pages
    @api.get("/demo/v/{token}/terms", response_class=HTMLResponse)
    async def demo_terms(token: str):
        try:
            page = await run(app_().vendors.demo_html, token)
        except VendorError:
            return HTMLResponse("Not found", status_code=404)
        if page is None:
            return HTMLResponse("Service unavailable", status_code=503)
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})

    api.state.redline = app_
    return api


app = create_app()
