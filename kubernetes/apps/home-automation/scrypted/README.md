# Scrypted

Bridges the **Nest Hello doorbell** (Google SDM, WebRTC-only) into an RTSP feed
that Frigate can consume. Frigate's bundled go2rtc cannot hold a stable video
track from Nest's WebRTC (upstream go2rtc issues #2386 / #2365), so Scrypted
does the WebRTC handshake, keyframe requests, and stream-session renewal, then
rebroadcasts plain RTSP. No Nest Aware subscription is needed — that only gates
cloud history, not live streaming.

## How it fits together

```
Google SDM (WebRTC) ──> Scrypted (Nest plugin + Rebroadcast) ──RTSP──> Frigate
```

- Web UI: `https://scrypted.${SECRET_DOMAIN}` (gateway terminates TLS, backend is
  Scrypted's insecure HTTP port 11080 — login works over it, only the cookie name
  differs from the HTTPS port).
- Data lives in the `scrypted` PVC at `/server/volume`. Scrypted self-updates its
  server and plugins into that volume, so the image tag is only a bootstrap; the
  running server version floats and is backed up by VolSync.

## First-time setup (all in the Scrypted UI)

1. Open `https://scrypted.${SECRET_DOMAIN}` and create the admin account (first
   visit). This account is local to Scrypted.
2. Install the **Google Nest** plugin and the **Rebroadcast** plugin from the
   plugin catalog.
3. Configure the Nest plugin with the same Google Device Access project the Home
   Assistant Nest integration already uses. Reuse these (already provisioned, no
   new Google project or $5 fee):
   - OAuth client id / secret: from HA `application_credentials` (domain `nest`).
   - Project id: `d1ab497e-39a7-4a4b-ab42-84d5dfc874c2`.
   - Refresh token: from HA's Nest config entry.

   If Scrypted's OAuth flow wants its own redirect, add the Scrypted callback URL
   to the same Google OAuth client in the Google Cloud console.
4. Adopt the **Front Door** doorbell. In its **Stream** / **Rebroadcast**
   settings, set **Rebroadcast Port** to **8554** (the fixed port this chart
   exposes on the Service). Note the stream path Scrypted shows — the RTSP URL is
   `rtsp://scrypted.home-automation.svc.cluster.local:8554/<streamId>`.

## Wiring the doorbell into Frigate

Add to Frigate's config (via its UI editor — Frigate keeps `config.yml`):

```yaml
cameras:
  front_door:
    enabled: true
    ffmpeg:
      inputs:
        - path: rtsp://scrypted.home-automation.svc.cluster.local:8554/<streamId>
          input_args: preset-rtsp-restream
          roles:
            - detect
            - record
    detect:
      width: 1600      # match the doorbell's stream (roughly 3:4 portrait)
      height: 1200
      fps: 5
```

Pin `detect.width`/`height` explicitly — an un-pinned detect input makes Frigate
run a UDP `ffprobe` that hangs on this cluster. Confirm the real resolution from
Scrypted's stream info first.

## Adding more Scrypted cameras later

Each Scrypted camera needs its own fixed Rebroadcast Port. Add a matching port to
the Service in `app/helmrelease.yaml` for every extra camera.

## Notes

- Pod (not host) networking is used. Host networking is only needed for HomeKit
  mDNS, which this deployment does not use.
- Runs as root by image design; the server tree in `/server/volume` is owned by
  root with `fsGroup: 1000`.
