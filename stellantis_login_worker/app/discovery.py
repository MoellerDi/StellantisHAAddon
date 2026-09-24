"""Announce the worker to Home Assistant via Supervisor discovery.

On start the add-on tells the Supervisor where it can be reached. Home
Assistant turns that message into a config flow for the domain named in
"service" (source "hassio"), so an integration that implements
async_step_hassio can pick up the Login service URL on its own instead of
the user typing it in.

    POST http://supervisor/discovery
         {"service": "stellantis_vehicles",
          "config": {"host": "<add-on hostname>", "port": 3000}}

The hostname is the add-on's name on the internal Supervisor network (e.g.
"0e0578fd-stellantis-login-worker"), which Home Assistant resolves without
the port being published on the host. Discovery needs no extra permission
beyond listing the service under "discovery:" in config.yaml.
"""
import logging
import os

import aiohttp

_LOGGER = logging.getLogger("loginworker.discovery")

SERVICE = "stellantis_vehicles"


class DiscoveryError(Exception):
    """The Supervisor refused or could not answer a request."""


async def _call(session: aiohttp.ClientSession, method: str, url: str,
                token: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with session.request(method, url, json=payload, headers=headers) as res:
        try:
            body = await res.json(content_type=None)
        except ValueError:
            body = None
    if res.status != 200 or not isinstance(body, dict) or body.get("result") != "ok":
        message = body.get("message") if isinstance(body, dict) else None
        raise DiscoveryError(f"{method} {url} -> {res.status} {message or ''}".strip())
    return body.get("data") or {}


async def announce(port: int, token: str | None = None,
                   base_url: str | None = None) -> dict | None:
    """Publish the discovery message. Returns the announced config, or None
    when not running under the Supervisor (local runs, tests)."""
    token = token or os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        _LOGGER.debug("No SUPERVISOR_TOKEN, skipping discovery")
        return None
    base_url = (base_url or os.environ.get("SUPERVISOR_URL", "http://supervisor")).rstrip("/")

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        info = await _call(session, "GET", f"{base_url}/addons/self/info", token)
        hostname = info.get("hostname")
        if not hostname:
            raise DiscoveryError("Supervisor did not report the add-on hostname")
        config = {"host": hostname, "port": port}
        result = await _call(session, "POST", f"{base_url}/discovery", token,
                             {"service": SERVICE, "config": config})
    _LOGGER.info("Announced to Home Assistant as http://%s:%d (discovery %s)",
                 hostname, port, result.get("uuid", "?"))
    return config
