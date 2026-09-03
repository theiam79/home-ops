# netbird

Self-hosted [NetBird](https://netbird.io) control plane: the overlay VPN that
lets friends reach the WoW realm (and nothing else) without any game port on
the WAN. Access is gated by LLDAP group membership through Authelia. This is
phase 1 of the WoW-realm plan; the routing peer that publishes the realm into
the overlay is a later PR.

## Design

- **One pod, three containers.** `server` is the combined
  `netbirdio/netbird-server` image (management + signal + relay + STUN + the
  embedded Dex identity provider, single binary since v0.65). `dashboard` is
  the SPA served by its own nginx on `:80`. `caddy` terminates TLS on `:8443`
  and is the only thing the Service points at for HTTPS.
- **Ports inside the pod.** Server HTTP/h2c on `:8080` (moved off its `:80`
  default because the dashboard's nginx owns `:80`), health on `:9000`,
  metrics on `:9090`, STUN on UDP `:3478`. Caddy routes gRPC (by
  `Content-Type: application/grpc*`) and `/relay*`, `/ws-proxy/*`, `/api/*`,
  `/oauth2/*` to the server, everything else to the dashboard. This is the
  upstream reverse-proxy layout with in-pod addresses.
- **TLS.** Caddy serves the existing wildcard certificate
  (`${SECRET_DOMAIN/./-}-production-tls`, issued by cert-manager for
  envoy-gateway in this namespace). Caddy does not re-read certificate files,
  so `reloader.stakater.com/auto` restarts the pod when the secret rotates
  (every few days at the current 160h duration). Peer data-plane traffic is
  unaffected by a control-plane restart; the dashboard just blips.
- **Relay.** Built-in, riding the same listener at `/relay`. The advertised
  relay address is derived from `exposedAddress`, so `server.relays` is
  deliberately unset: setting it disables the local relay.
- **Exposure.** LoadBalancer pinned to `192.168.100.39` (TCP 443, UDP 3478).
  opnsense-dns publishes `netbird.${SECRET_DOMAIN}` on the LAN from the service
  annotation, so LAN peers reach the LB IP directly (hairpin NAT does not work
  on this WAN). The public name is a DNS-only CNAME to `ipv4.${SECRET_DOMAIN}`
  via `dnsendpoint.yaml`, the same pattern as abiotic and mc-router. OPNsense
  forwards WAN TCP 443 and UDP 3478 to the LB IP (see below).
- **Not behind the Cloudflare tunnel, on purpose.** The tunnel runs QUIC, which
  strips the gRPC trailers the management and signal streams depend on, and
  the free-tier proxy tears down long-lived streams roughly every 100 s, so
  peers flap. STUN is UDP and cannot be proxied at all.
- **Storage.** `/var/lib/netbird` (SQLite store, events, IdP DB, GeoLite) on
  the VolSync-managed `netbird` PVC (1Gi). Server and Caddy run as uid 1000
  with `fsGroup: 1000`; the dashboard image needs root for nginx on `:80`.
- **Resources.** Requests only, per repo convention.

### Why the config is a secret

The combined server reads `config.yaml` with a plain YAML unmarshal: no
environment-variable substitution, no `NB_*` overrides (those belong to the
legacy split binaries). Three values in that file are secrets (`authSecret`
for the relay, `store.encryptionKey`, `auth.sessionCookieEncryptionKey`), so
the ExternalSecret templates the whole file and it is mounted from
`netbird-secret`. Non-secret settings therefore also live in
`externalsecret.yaml`. If `store.encryptionKey` were left empty the server
would generate one per start and only log it, which would make the store
unreadable after every restart.

## Bootstrap order

1. **Bitwarden Secrets Manager.** Consumed by manifests (UUIDs in
   `app/externalsecret.yaml` and Authelia's):
   - `NETBIRD_RELAY_SECRET`: any string; `openssl rand -base64 32 | tr -d =`.
   - `NETBIRD_DATASTORE_KEY`: `openssl rand -base64 32` (keep the padding).
   - `NETBIRD_SESSION_COOKIE_KEY`: 16, 24 or 32 bytes, raw or base64;
     `openssl rand -base64 32`.
   - `NETBIRD_CLIENT_SECRET_DIGEST` for Authelia (see step 4).

   Used by hand, never mounted: `NETBIRD_CLIENT_SECRET` (plaintext of the
   digest, pasted into the dashboard connector in step 6) and
   `NETBIRD_ADMIN_PASSWORD` (the break-glass local owner from step 5).
2. **Merge.** Flux creates the PVC, secret, DNSEndpoint and pod. Wait for
   `kubectl -n network get pod -l app.kubernetes.io/name=netbird` to show 3/3.
3. **OPNsense.** Firewall › NAT › Port Forward on WAN: TCP 443 →
   `192.168.100.39:443` and UDP 3478 → `192.168.100.39:3478`, each with an
   associated pass rule and **logging on**. Confirm the Cloudflare record for
   `netbird.${SECRET_DOMAIN}` shows a grey cloud.
4. **Authelia** is in the same PR: client `netbird` (confidential,
   `client_secret_basic`, scopes `openid profile email groups`, the
   `id_token_claims` policy so groups land in the ID token) gated by the `vpn`
   authorization policy (`group:wow` or `group:admins`, two-factor). Generate
   secret + digest together:
   `authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 72 --random.charset rfc3986`.
5. **First admin.** Open `https://netbird.${SECRET_DOMAIN}` from the LAN. With
   no users yet the dashboard shows the setup wizard; create the local owner
   account (this is the break-glass login, keep it in Bitwarden).
6. **Connector.** Settings › Identity Providers › Add › **Pocket ID** (not
   Generic OIDC, see Gotchas): name `authelia`, issuer
   `https://auth.${SECRET_DOMAIN}`, client id `netbird`, the plaintext
   secret. The callback URL the dashboard shows is
   `https://netbird.${SECRET_DOMAIN}/oauth2/callback` (no connector id in
   the path, despite what the upstream docs suggest) and logout is
   `/oauth2/logout/callback`; both are the Authelia client's `redirect_uris`.
7. **Group sync.** Settings › Groups: enable JWT group sync, claim `groups`,
   allowed groups `wow` and `admins`, user-group propagation on. Your own
   account must already be in `admins` in LLDAP or you lock yourself out.
   Sign out, sign in with Authelia: Groups now lists both, auto-created.
8. **Close the defaults.** Access Control › Policies: delete the default
   all-to-all policy. Settings › Authentication: require user approval.
9. **Later, once the Authelia path is proven twice**: set
   `auth.localAuthDisabled: true` in the templated config. Re-enabling is a
   one-line revert if Authelia is ever down.

## Verify

```sh
kubectl -n network get pod,svc,pvc -l app.kubernetes.io/name=netbird
kubectl -n network logs deploy/netbird -c server | grep -iE 'listen|stun|relay|error'
curl -sk https://192.168.100.39/api/users -o /dev/null -w '%{http_code}\n'   # 401 = healthy
dig +short netbird.${SECRET_DOMAIN} @192.168.100.1                            # 192.168.100.39
dig +short netbird.${SECRET_DOMAIN} @1.1.1.1                                  # ipv4 CNAME then WAN IP, never a Cloudflare edge
```

From outside (phone on cellular): the dashboard login page loads, and a STUN
client against `netbird.${SECRET_DOMAIN}:3478` returns a mapped address. After
enrolling a second device, `netbird status -d` should show the peer as
**P2P**; **Relayed** means STUN is not reachable.

## Gotchas

- **Add Authelia as connector type "Pocket ID", not "Generic OIDC".** The
  embedded Dex connector NetBird builds for the generic type requests only
  `openid profile email` from the upstream IdP, and neither the dashboard nor
  the API can add scopes (`idp/dex/config.go`, `applyOIDCDefaults`). Authelia
  releases `groups` only when the `groups` scope is requested, so a generic
  connector yields a token with no groups and every login fails with
  "user does not belong to any of the allowed JWT groups" (hit 2026-09-03).
  The Okta and Pocket ID types hard-code `groups` into the scope list and are
  otherwise plain OIDC with no claim-mapping quirks, so Pocket ID is the type
  to pick. Connector type only changes those defaults; Authelia does not care.
- **Do not probe the server with `/health`.** That endpoint includes a relay
  self-check that dials `exposedAddress` (the public hostname, which resolves
  to the LB IP in-cluster). The LB only has endpoints when the pod is Ready,
  and the pod is only Ready when the probe passes, so an HTTP probe on
  `/health` deadlocks on first boot (hit 2026-09-03). Kubelet probes are TCP
  on `:8080`; `/health` on `:9000` remains the right thing for Gatus or any
  external monitor, where the circularity does not exist.
- The Caddy image's binary carries `cap_net_bind_service` as a file
  capability, so the container must keep `NET_BIND_SERVICE` in its bounding
  set even though it listens on 8443; with capabilities fully dropped and no
  privilege escalation the kernel refuses to exec it.
- Dex's OIDC connector reads claims from the ID token, hence the Authelia
  `claims_policy`. Without it Authelia 4.39+ omits `groups` and group sync
  silently syncs nothing.
- The JWT allow-list is enforced on every login, including yours.
- `disableGeoliteUpdate` is left at its default (the server downloads the
  GeoLite DB into `dataDir` on start, used by posture checks). Set it to
  `true` if a namespace egress policy later blocks that download.
- Pinned LB IPs are listed in `kube-system/cilium/README.md`.
