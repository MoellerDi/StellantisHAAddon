# Stellantis Login Worker

A local replacement for the shared login service that the
[homeassistant-stellantis-vehicles](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles)
integration uses to obtain its OAuth authorization code.

Use this add-on if you want to keep the HACS integration but not send your
Stellantis credentials through a third-party server. If you would rather have
integration and login in one package, install the **Stellantis Vehicles**
add-on from this repository instead — you do not need both.

## How it works

The integration cannot log in by itself: Stellantis has no public B2C API, so
the login runs through the brand's normal web form, and the authorization code
arrives as a redirect to an app scheme (`mym…://oauth2redirect?code=…`) that a
browser cannot follow. This add-on drives a headless Chromium through that
flow and returns the code.

Your e-mail address and password are passed straight to the browser. They are
not stored, not written to the log and not sent anywhere except the Stellantis
identity provider.

## Installation

1. Install and start the add-on.
2. In the integration's config flow, at the **remote login** step, enter the
   add-on's address as **Login service URL**:

   ```
   http://<home-assistant-ip>:3000
   ```

   `homeassistant.local` works too if your network resolves it.
3. Complete the login. Afterwards you can stop the add-on again — it is only
   needed for the initial login and for re-authentication, which is why it is
   set to start manually.

Check that it is reachable with:

```bash
curl http://<home-assistant-ip>:3000/health
```

which answers `{"status": "ok"}`.

## Options

| Option      | Default | Meaning                                                              |
| ----------- | ------- | -------------------------------------------------------------------- |
| `log_level` | `info`  | Set to `debug` to see every URL the browser visits (query values are masked). |
| `timeout`   | `60`    | Seconds to wait for the login to complete. The integration may send its own value. |

## API

The add-on speaks the same wire format as the community `worker-v2` service,
so it is a drop-in replacement:

```
POST /        {"url": "<oauth authorize url>", "email": "…", "password": "…"}
              → 200 {"code": "<authorization code>"}
              → 400 {"message": "<reason>", "code": 400}
GET  /health  → {"status": "ok"}
```

Only one login runs at a time; further requests queue. Chromium is started per
login and closed afterwards, so the add-on idles at a few MB.

## Troubleshooting

**"Stellantis IdP rejected the login"** — wrong credentials, or the account is
locked. The message contains the text of the page the login stopped on.

**"No authorization code captured (timeout)"** — the flow got past the login
but the redirect never arrived. Set `log_level` to `debug` and try again; the
log then lists every URL that was seen.

**The add-on does not start on a Raspberry Pi** — Chromium needs a few hundred
MB while a login is running. Stop other memory-hungry add-ons, or run the
login once from a stronger machine.

## Security

Port 3000 is open on your Home Assistant host and is not authenticated —
anyone on your network could send it a login request of their own (with their
own credentials; it will not reveal yours). Keeping the add-on stopped except
during logins avoids this entirely.
