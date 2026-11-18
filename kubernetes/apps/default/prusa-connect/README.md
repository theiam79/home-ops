# Prusa Connect Local

Prusa's self-hosted Connect server ([prusa3d/prusa-connect](https://github.com/prusa3d/prusa-connect)),
public beta since 2026-11-17. Printers dial **out** to it over a websocket; the web app, REST API,
event stream and metrics are served by one Go binary backed by SQLite.

**Current stage: trial, no printer linked.** Internal route only (`prusa.${SECRET_DOMAIN}`),
local accounts, no printer listener. Supersedes #154 (prusalink-proxy).

## Layout

| path in pod | from | holds |
|---|---|---|
| `/config/config.yaml` | ConfigMap `prusa-connect-config` (subPath, `resources/config.yaml`) | operator config |
| `/config/config.d` | PVC `prusa-connect` (VolSync, 20Gi) | `authz.db`, `setup.yaml` (wizard output), `resources.json`, `modules/`, `module-data/`, `storage/` (uploads), history db, `upgrade/backups` |
| `/tmp` | emptyDir | uploads > 32 MiB spill here |

Why not upstream's `deploy/kubernetes` layout: it mounts the config at a read-only
`/etc/prusa-connect`, but the setup wizard writes `config.d/setup.yaml` **beside the config file**
(`internal/app/config/setupfile.go`), so the wizard would fail there. With the image's default
layout every derived path lands on the PVC. `setup.yaml` is merged *under* `config.yaml`: keys in
git always win.

The core reads its config once and has no env vars and no SIGHUP. Reloader restarts the pod on a
ConfigMap change, and an unknown key fails startup (check the pod log).

## First run

1. Get the one-time setup code from the log:
   `kubectl -n default logs deploy/prusa-connect | grep -i 'setup code'`
2. Open `https://prusa.${SECRET_DOMAIN}`, enter the code, and create the admin account. Require
   sign-in and approve each printer. Storage is already declared in git, so the wizard skips it.
3. The wizard restarts the server, which is expected.
4. Extensions: Settings → Extensions offers fleet-stats, threemf, parts, and materials (bundled in
   the image under `/opt/modules`). The marketplace is off on purpose: extension processes run
   **unsandboxed** inside this pod, and their release signatures aren't verified.
   - materials is Prusa's spool inventory and overlaps with Spoolman. It downloads its catalogue
     from GitHub.
   - server-slicing is not offered: it needs a self-supplied headless PrusaSlicer and ~2.5 GiB.

## Next stages (not done)

- **Link the Core One** (firmware 8.0.2, needs ≥ 6.4.0):
  - Add a connector with its own `listener.addr` (e.g. `:8081`). That port serves only
    `/p/register` and `/p/ws`.
  - Expose it alone on a LoadBalancer IP (pin `lbipam.cilium.io/ips`, check the pool for a free
    address) and add a NetworkPolicy rule for it.
  - Set `core.frontend.printer_address` to a hostname of **≤ 20 characters** (the firmware
    silently truncates longer names, which then fail with "DNS error"), e.g. `pcl.internal` with an
    OPNsense override.
  - USB stick with `prusa_printer_settings.ini` → Settings → Network → Prusa Connect → Load
    Settings → Add Printer to Connect → approve the code. Save the printer's cloud Connect config
    first, which is the way back. Cloud and local Connect can't be used at the same time.
- **Printer TLS:**
  - The firmware requirements are strict: an ECDSA certificate, TLS 1.2 with
    `ECDHE-ECDSA-AES128-GCM-SHA256`, and the whole certificate message must be **≤ 1024 bytes**.
    That means no intermediates, so Let's Encrypt is impossible.
  - The SAN must match the INI hostname. The CA goes to the printer as `connect.der` with
    `custom_cert = 1`.
  - Approach: a cert-manager self-signed ECDSA root plus a leaf, or the wizard-generated certs. The
    printer listener hot-reloads a mounted Secret.
- **Authelia:**
  - Set `core.auth.issuer`/`client_id`/`client_secret`/`redirect_uri`
    (`/api/v1/auth/callback`). This replaces local accounts; the two are mutually exclusive.
  - Use a confidential client with `client_secret_basic` and PKCE S256, gated by an
    `authorization_policies` group.
  - `client_secret` is a plain config value, so `config.yaml` moves to an ExternalSecret template.
  - `core.principal` = the admin's Authelia subject (`authelia storage user identifiers add <user>`).
- **Remote access:** envoy-external with an ext-authz SecurityPolicy in front (aurral pattern) plus
  native OIDC. Cloudflare's 100 MB request limit blocks large uploads remotely.
- **Home Assistant:** HACS "Prusa Connect (on-premise)" pointed at
  `http://prusa-connect.default.svc.cluster.local:8080`, paired with the `operate` scope.
- **Upgrades:** the beta changes its config, API and SDK between 0.x releases. Read the changelog
  before merging Renovate bumps; the `upgrade-check` init container rehearses migrations first.
  Prefer `prusa_connect backup create` (online SQLite snapshot into `config.d/upgrade/backups`)
  before an upgrade.
