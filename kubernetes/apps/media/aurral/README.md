# aurral

Lidarr companion for music discovery/requests, trialled alongside musicseerr.
Standard app-template HelmRelease; the non-obvious parts are all about how it
authenticates.

## Forward auth (the load-bearing bits)

`securitypolicy.yaml` is the cluster's first Envoy Gateway `SecurityPolicy`. It
does ext-authz against Authelia's built-in `/api/authz/ext-authz` endpoint, and
`headersToBackend` hands `Remote-User` / `Remote-Groups` to Aurral, which is
configured for proxy auth (`AUTH_PROXY_ENABLED`). Admin comes from the `admins`
LDAP group via `Remote-Groups`, so no usernames are hardcoded.

Three constraints follow from this, and breaking any one of them silently turns
external SSO into an open admin door:

1. **The NetworkPolicy is a security control, not tidiness.** Aurral trusts
   `Remote-User` on *any* request: upstream `isTrustedProxy()` returns true when
   `AUTH_PROXY_TRUSTED_IPS` is unset, and proxy identity is checked before API
   key and Basic auth. The gateway policy only guards the gateway path, so
   without `networkpolicy.yaml` any pod in the cluster could `curl` the Service
   with a forged header and be provisioned as an admin (and promote existing
   users). `AUTH_PROXY_TRUSTED_IPS` is deliberately *not* used instead: it is
   exact-string match with no CIDR support (breaks on Envoy pod-IP churn) and is
   itself defeatable via `X-Forwarded-For`, since the app sets `trust proxy`.

2. **Never add an Authelia `bypass` rule for this hostname.** Envoy's
   `allowed_upstream_headers` *overwrites* `Remote-*` only when the auth response
   actually contains them; it does not scrub client-supplied copies on requests
   the auth server waves through. Today every 200 for this host comes from the
   `two_factor` path and carries the headers, so client values can't survive. A
   future bypass rule — the usual reflex for an API or webhook path — would let
   an unauthenticated internet client send its own `Remote-Groups: admins`.
   Grant per-path exemptions inside Aurral instead, or re-test the header path.

3. **Fail-closed is intentional.** `failOpen` is left unset (defaults false), so
   Authelia being down makes Aurral unreachable through *both* gateways rather
   than exposing it. Setting `failOpen: true` would also bypass ext-authz on
   invalid config, not just backend outage.

The SecurityPolicy applies to every parentRef of the HTTPRoute, so the internal
route requires SSO too — unlike the sibling *arr apps.

## Storage

`/data/media` is mounted **read-only**: Lidarr does the importing and moving,
and Aurral's own downloads land in `/data/downloads`. If a feature turns out to
need library writes, narrow the NFS `path` to the music subtree rather than
making all of `/mnt/user/media` writable.

## Container user

The image's entrypoint starts as root, chowns `/config`, then `gosu`s down to
uid 1001 — so `runAsNonRoot` is not available here (unlike the *arr apps).
Capabilities are dropped to only what that dance needs.
