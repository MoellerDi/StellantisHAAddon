# Stellantis HA Add-ons

Home Assistant add-on repository with two add-ons. Both keep the Stellantis login on
your own hardware instead of a third-party server; pick the one that fits your setup,
you do not need both.

**Stellantis Vehicles** bundles the HACS integration
[homeassistant-stellantis-vehicles](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles)
and its OAuth login in one container. Vehicle data reaches Home Assistant via MQTT
discovery, HACS is not needed.

**Stellantis Login Worker** is the small alternative: keep the HACS integration as it
is and point its *Login service URL* at this add-on, so only the login moves to your
machine. See `stellantis_login_worker/DOCS.md`.

Supported brands are the ones the upstream integration supports: Peugeot, Citroën, DS,
Opel and Vauxhall (the former PSA apps). Fiat, Jeep, Alfa Romeo and the other FCA brands
use a different backend and are not covered.

## Disclaimer

This is an unofficial community project. It is not affiliated with, endorsed by or
supported by Stellantis or any of its brands, and it uses the same non-public vehicle
APIs as the upstream integration, which may change or stop working at any time.
Stellantis, Peugeot, Citroën, DS, Opel, Vauxhall and all other brand names and logos
mentioned here are trademarks of Stellantis N.V. and its subsidiaries. Use at your own risk.

## Installation

Settings → Add-ons → Add-on Store → ⋮ → Repositories →
`https://github.com/taubenhorst/StellantisHAAddon`

Both add-ons then appear in the store. **Stellantis Vehicles** requires the Mosquitto
broker add-on, the MQTT integration and Home Assistant 2025.10 or newer.
**Stellantis Login Worker** has no requirements beyond the HACS integration it serves.

## Layout

```
stellantis_vehicles/
├── config.yaml / build.yaml / Dockerfile     add-on packaging
├── rootfs/etc/services.d/stellantis/run     s6 service
├── tests/                                   offline smoke tests
└── app/
    ├── main.py               entry point
    ├── runtime.py            vehicles, coordinators, bridge wiring
    ├── hass_shim/            minimal stand-in for the `homeassistant` package
    ├── stellantis_vehicles/  upstream code (unchanged, see UPSTREAM.md) + own base.py
    ├── bridge/               MQTT discovery bridge
    ├── oauth_browser/        Playwright login (clean-room)
    └── web/                  ingress UI (login, OTP, status)

stellantis_login_worker/
├── config.yaml / build.yaml / Dockerfile     add-on packaging
├── rootfs/etc/services.d/loginworker/run    s6 service
├── tests/smoke_worker.py                    offline test of the HTTP contract
└── app/
    ├── server.py            aiohttp service, worker-v2 wire format
    ├── discovery.py         announces the worker to Home Assistant (Supervisor discovery)
    └── login.py             copy of oauth_browser/login.py, without its CLI
```

Design principle: the upstream code stays untouched, its Home Assistant dependencies are
provided by `hass_shim/`. Upstream fixes can therefore be taken over by copying files.

`stellantis_login_worker/app/login.py` is a copy, not a shared module: the add-on
builder uses each add-on folder as its own build context, so it cannot reach outside.
Keep the two copies in sync when the Stellantis login flow changes.

## Development

```bash
cd stellantis_vehicles
pip install -r requirements.txt
python -m playwright install chromium
python app/main.py          # uses ./data as data directory, UI on http://localhost:8099/
```

Offline tests (no network, no broker):

```bash
python tests/smoke_bridge.py
python tests/smoke_web.py
python tests/smoke_runtime.py
cd ../stellantis_login_worker && python tests/smoke_worker.py
```

Local image build: `docker build --build-arg BUILD_VERSION=0.1.0 -t stellantis-vehicles:dev stellantis_vehicles`.
CI builds aarch64 and amd64 images of both add-ons and pushes them to GHCR.

## Status

**Stellantis Vehicles** works end to end (login, OTP, vehicle status, MQTT discovery),
images are built by CI — see `stellantis_vehicles/CHANGELOG.md`. Not yet tested in
long-term operation on a Pi.

**Stellantis Login Worker** is new in 0.1.0. Its HTTP contract is covered by offline
tests, but it has not yet been run against the live Stellantis login as a standalone
add-on — the same login code is what the other add-on uses in production.

## License

MIT, see `LICENSE`. Upstream parts are MIT as well (Andrea De Giovine).
