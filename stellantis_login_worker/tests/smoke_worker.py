"""Offline smoke test for the login worker's HTTP contract (app/server.py).

Stubs the browser login; drives the aiohttp app with a test client and checks
the wire format the homeassistant-stellantis-vehicles integration expects:
success carries "code", failures carry "message", /health answers "ok".

    ../.venv/Scripts/python tests/smoke_worker.py
"""
import asyncio
import os
import sys

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP_DIR)

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import server  # noqa: E402
from login import OauthBrowserError  # noqa: E402

OAUTH_URL = "https://idpcvs.peugeot.com/am/oauth2/authorize?client_id=x"
CREDS = {"url": OAUTH_URL, "email": "me@example.org", "password": "s3cret"}

failures: list[str] = []


def check(condition: bool, what: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + what)
    if not condition:
        failures.append(what)


async def main() -> int:
    calls: list[dict] = []

    async def fake_login(url, email, password, timeout_s=60.0, debug_dir=None,
                         on_event=None, locale=None):
        calls.append({"url": url, "email": email, "password": password,
                      "timeout_s": timeout_s, "locale": locale})
        if password == "wrong":
            raise OauthBrowserError("Stellantis IdP rejected the login: bad credentials")
        if password == "boom":
            raise RuntimeError("chromium vanished")
        return "AUTH-CODE-123"

    server.fetch_oauth_code = fake_login

    async with TestClient(TestServer(server.create_app())) as client:
        print("health")
        res = await client.get("/health")
        check(res.status == 200, "GET /health -> 200")
        check((await res.json()) == {"status": "ok"}, 'body is {"status": "ok"}')

        print("successful login")
        res = await client.post("/", json=CREDS)
        body = await res.json()
        check(res.status == 200, "POST / -> 200")
        check(body.get("code") == "AUTH-CODE-123", 'body carries the code')
        check(calls[-1]["url"] == OAUTH_URL, "OAuth URL passed through unchanged")
        check(calls[-1]["timeout_s"] == server.DEFAULT_TIMEOUT_S, "default timeout applied")

        print("timeout_page is milliseconds")
        await client.post("/", json=dict(CREDS, timeout_page=90000))
        check(calls[-1]["timeout_s"] == 90.0, "90000 ms -> 90 s")
        await client.post("/", json=dict(CREDS, timeout_page=5))
        check(calls[-1]["timeout_s"] == 10.0, "absurdly small value clamped to 10 s")
        await client.post("/", json=dict(CREDS, timeout_page=9_000_000))
        check(calls[-1]["timeout_s"] == 300.0, "absurdly large value clamped to 300 s")

        print("bad requests")
        for missing in ("url", "email", "password"):
            payload = {k: v for k, v in CREDS.items() if k != missing}
            res = await client.post("/", json=payload)
            body = await res.json()
            check(res.status == 400 and body.get("code") == 400, f"missing {missing} -> 400")
            check("message" in body, f"missing {missing} -> body carries a message")
        res = await client.post("/", data="not json", headers={"Content-Type": "application/json"})
        check(res.status == 400, "invalid JSON -> 400")

        print("login errors")
        res = await client.post("/", json=dict(CREDS, password="wrong"))
        body = await res.json()
        check(res.status == 400, "rejected login -> 400")
        check("rejected" in body.get("message", ""), "reason is passed on")
        check("code" not in body or body["code"] == 400, "no authorization code in an error body")

        res = await client.post("/", json=dict(CREDS, password="boom"))
        body = await res.json()
        check(res.status == 500, "unexpected error -> 500")
        check("chromium vanished" in body.get("message", ""), "error type and text reported")

        print("concurrency")
        gate = asyncio.Event()
        entered = asyncio.Event()
        overlap = False

        async def slow_login(*args, **kwargs):
            nonlocal overlap
            if entered.is_set():
                overlap = True
            entered.set()
            await gate.wait()
            entered.clear()
            return "SLOW-CODE"

        server.fetch_oauth_code = slow_login
        first = asyncio.ensure_future(client.post("/", json=CREDS))
        second = asyncio.ensure_future(client.post("/", json=CREDS))
        await asyncio.sleep(0.1)
        gate.set()
        for res in await asyncio.gather(first, second):
            check(res.status == 200, "queued request answered with 200")
        check(not overlap, "only one login runs at a time")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for what in failures:
            print("  -", what)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
