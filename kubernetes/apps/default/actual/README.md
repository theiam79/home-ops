# Actual Budget

Self-hosted envelope/zero-based budgeting (YNAB replacement — see issue #495).
Single container, SQLite in `/data` (VolSync-backed PVC), no Postgres/Redis.
Served at `budget.${SECRET_DOMAIN}` on `envoy-internal`.

## Auth model

Login is OIDC-only (`ACTUAL_LOGIN_METHOD=openid` + `ACTUAL_OPENID_ENFORCE=true`,
no password fallback). Access is gated **in Authelia**, not in Actual: the
`actual` OIDC client uses the custom `finance` authorization policy
(deny-by-default; `group:finance` or `group:admins`, two_factor). Actual ignores
OIDC group claims — its own roles live in Settings → User Directory.

- `ACTUAL_USER_CREATION_MODE=login`: anyone Authelia authorizes gets a Basic
  account automatically on first login.
- **The very first user to log in becomes the server owner/admin** — log in
  yourself before adding others to the `finance` group.
- Sharing a budget file with another user is done per-file in Actual's UI.

## Bootstrap order

1. Merge the Authelia PR (client + `finance` policy) — Authelia must know the
   client before Actual's login redirect can work.
2. Create the `finance` group in lldap (UI; lldap groups aren't gitops-managed)
   and add members. Admins don't need to join.
3. Bitwarden SM secrets (fill both ExternalSecret UUIDs before merging):
   - `ACTUAL_OIDC_CLIENT_SECRET` — plaintext, consumed here
   - `ACTUAL_CLIENT_SECRET_DIGEST` — pbkdf2 digest of the same value, consumed
     by Authelia. Generate both at once:
     `authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 72 --random.charset rfc3986`
4. Merge this PR; first login (owner) at `https://budget.${SECRET_DOMAIN}`.

## YNAB migration

Use the **nYNAB JSON export** (via YNAB API personal access token — e.g.
json-exporter-for-ynab.netlify.app or `ynab-export`), *not* the register CSV.
File → Import → nYNAB brings over transactions, accounts, categories **and
monthly allocation history**. Known cleanup afterwards:

- Recreate credit-card payment mechanics manually (a "Credit Card" category +
  rollover-overspending on the card's category).
- Leftover money in To Budget → "Hold for next month".
- Duplicate categories arrive suffixed `-1` (hidden-category dupes) — merge.

Keep YNAB authoritative while running in parallel; re-import is cheap.

## Notes

- Image: `ghcr.io/actualbudget/actual` (versioned tags, no `v` prefix).
  Anything ≥ 26.2.1 is required — CVE-2026-27638 (multi-user sync endpoints
  didn't check file ownership before that).
- Bank sync (SimpleFIN/GoCardless) is configured in-app later; no manifests
  needed unless we add provider secrets.
- `/health` is the probe endpoint; `/info` returns build info.
