"""HTTP front end for the headless Stellantis login.

Speaks the same wire format as the community "worker-v2" service, so this
add-on is a drop-in replacement for the shared Render.com instance that
homeassistant-stellantis-vehicles uses by default:

    POST /          {"url": ..., "email": ..., "password": ...}
                    -> 200 {"code": "<authorization code>"}
                    -> 400 {"message": "...", "code": 400}
    GET  /health    -> {"status": "ok"}

Only the wire format is shared. The login itself is our own clean-room
implementation in login.py; no code was taken from the (unlicensed)
worker-v2 repository.

Credentials arrive in the request body and are handed straight to the
browser. They are never logged, and neither is the resulting code.
"""
import asyncio
import logging
import os

from aiohttp import web

from login import OauthBrowserError, fetch_oauth_code

_LOGGER = logging.getLogger("loginworker")

PORT = int(os.environ.get("WORKER_PORT", "3000"))
DEFAULT_TIMEOUT_S = float(os.environ.get("WORKER_TIMEOUT", "60"))

# One Chromium at a time. The add-on is meant to run on small hosts, and two
# concurrent browsers are a reliable way to run a Raspberry Pi out of memory.
_login_lock = asyncio.Lock()


def _error(message: str, status: int = 400) -> web.Response:
    """Error shape of worker-v2: a message plus the status repeated as "code"."""
    return web.json_response({"message": message, "code": status}, status=status)


async def handle_login(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - any parse problem is the same to the caller
        return _error("Body is not valid JSON")

    url = payload.get("url")
    email = payload.get("email")
    password = payload.get("password")
    if not url or not email or not password:
        return _error("Missing required params")

    # worker-v2 clients send milliseconds; keep accepting them.
    try:
        timeout_s = float(payload.get("timeout_page", DEFAULT_TIMEOUT_S * 1000)) / 1000
    except (TypeError, ValueError):
        return _error("timeout_page is not a number")
    timeout_s = min(max(timeout_s, 10.0), 300.0)

    if _login_lock.locked():
        _LOGGER.info("Another login is in progress, queuing this one")

    async with _login_lock:
        _LOGGER.info("Starting login (timeout %.0fs)", timeout_s)
        try:
            code = await fetch_oauth_code(url, email, password, timeout_s=timeout_s,
                                          locale=payload.get("locale"))
        except OauthBrowserError as err:
            _LOGGER.warning("Login failed: %s", err)
            return _error(str(err))
        except Exception as err:  # noqa: BLE001 - never leak a stack trace to the caller
            _LOGGER.exception("Unexpected error during login")
            return _error(f"{type(err).__name__}: {err}", 500)

    _LOGGER.info("Authorization code captured (%d characters)", len(code))
    return web.json_response({"code": code})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/", handle_login)
    app.router.add_get("/health", handle_health)
    return app


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "info").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _LOGGER.info("Stellantis Login Worker %s listening on port %d",
                 os.environ.get("ADDON_VERSION", "dev"), PORT)
    web.run_app(create_app(), host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
