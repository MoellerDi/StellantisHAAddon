## 0.2.0

- Supervisor discovery: on start the add-on announces itself as service
  `stellantis_vehicles` with its internal hostname and port, so the integration
  can take over the Login service URL without typing it in
  (`app/discovery.py`; best effort, a failure is logged and the worker still
  starts)
- The add-on log prints the internal URL, for integration versions without
  discovery support
- **Breaking:** port 3000 is no longer published on the host by default. Home
  Assistant reaches the worker via `http://<hostname>:3000` on the internal
  network. If you used `http://<home-assistant-ip>:3000`, either switch to the
  internal URL or set the host port again under the add-on's Network settings
- `tests/smoke_worker.py`: 8 more checks against a fake Supervisor (28 total)

## 0.1.0

First version.

- Standalone login service for the HACS integration `homeassistant-stellantis-vehicles`,
  for users who want to keep that integration but run the login locally
- `app/server.py`: aiohttp service speaking the wire format of the community
  `worker-v2` service (`POST /` → `{"code": …}`, `GET /health`), so it can be
  used as the integration's **Login service URL** without any other change
- `app/login.py`: our clean-room Playwright login, copied from the Stellantis
  Vehicles add-on minus its diagnostics CLI. No code from `worker-v2`, which
  carries no license
- Full Chromium instead of the headless shell (`channel="chromium"`); the shell
  is detected by the Stellantis identity provider, which then answers with
  `#failedLogin`
- One login at a time, Chromium started per request and closed afterwards, so
  the add-on idles at a few MB on small hosts
- `boot: manual` — the service is only needed for login and re-authentication
- Options: `log_level`, `timeout`
- `tests/smoke_worker.py`: 20 offline checks of the HTTP contract
