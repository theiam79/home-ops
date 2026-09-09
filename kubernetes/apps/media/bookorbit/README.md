# BookOrbit

Ebook library manager evaluated **side by side with Grimmory** (`books.${SECRET_DOMAIN}`).
Goal: replace Grimmory after a bake-in, and compare its Requests (beta) feature
against Shelfmark. Served at `bookorbit.${SECRET_DOMAIN}` on `envoy-external`
(Kobo devices and KOReader need public reachability).

Single image (`ghcr.io/bookorbit/bookorbit`, semver tags without `v`, port 3000),
Postgres via CNPG (`bookorbit-pg`, PG18 `standard` flavour for pgvector), state in
`/data` (VolSync-backed PVC). Migrations run on every boot; `/api/v1/health` is
the probe endpoint. No Redis or search sidecar.

## Storage layout (deliberate for the bake-in)

| Mount               | Source                                          | Mode | Purpose                                                        |
| ------------------- | ----------------------------------------------- | ---- | -------------------------------------------------------------- |
| `/data`             | PVC `bookorbit`                                 | rw   | covers, `book-bucket` (kepub cache), `book-dock`, plugins      |
| `/books/library`    | `snotra:/mnt/user/media/books`                  | **ro** | Grimmory's live library: scan, importer target, Kobo/KOReader tests |
| `/books/bookorbit`  | `snotra:/mnt/user/media/bookorbit`              | rw   | BookOrbit-owned library: uploads, Book Dock finalize, request downloads |
| `/downloads`        | `snotra:/mnt/disks/85AAZU6GS/cluster/downloads` | rw   | qBittorrent completed downloads (Requests path mapping)         |

Grimmory identifies files by partial-MD5 for Kobo/KOReader sync; any file
rewrite (metadata write-back, kepub conversion in place, reorganisation) by
BookOrbit would break Grimmory's sync identity while it is still primary. Hence
the read-only mount. Uploads or Book Dock imports into `/books/library` will fail
by design; point them at `/books/bookorbit`. At cutover, drop `readOnly: true`.

Book Dock lives on the PVC (`/data/book-dock`) because its watcher is
inotify-based and NFS does not emit inotify events. Shelfmark cannot drop files
there; for Shelfmark → BookOrbit handoff use the Requests feature instead, or add
an NFS Book Dock later and rely on the manual Rescan button.

## Auth model

OIDC is configured **in the BookOrbit UI**, not via env. Access is gated in
Authelia with the custom `books` authorization policy (deny-by-default,
`group:books` or `group:admins`, two_factor) because BookOrbit auto-provisions
anyone the IdP lets through; its own group mappings only grant permissions.

- Client `bookorbit`: confidential, `client_secret_post` (the only method
  BookOrbit supports), PKCE S256 required, redirect
  `https://bookorbit.${SECRET_DOMAIN}/oauth2-callback`.
- BookOrbit calls the userinfo endpoint, so no `claims_policy` is needed.
- **The first account created by the setup wizard is the superuser**; there is no
  OIDC → superuser mapping. Create it locally, then link it to Authelia.
- `OIDC_ALLOW_LOCAL_ISSUERS=true` is set so the SSRF guard accepts an issuer that
  resolves to a LAN address from inside the cluster.
- Local login can be disabled later with `DISABLE_LOCAL_AUTH=true`; the app
  refuses to start unless an active superuser is linked to an enabled provider.

## Bootstrap order

1. Bitwarden SM secrets, then fill the `REPLACE_WITH_BWS_UUID_*` placeholders in
   `app/externalsecret.yaml` and `../../auth/authelia/app/externalsecret.yaml`
   **before merging** (an unresolvable UUID stalls the whole Authelia secret):
   - `BOOKORBIT_JWT_SECRET` — `openssl rand -hex 32` (min 16 chars)
   - `BOOKORBIT_SETUP_BOOTSTRAP_TOKEN` — `openssl rand -hex 16`; required in
     production, consumed once by the setup wizard
   - `BOOKORBIT_BOOK_REQUEST_ENCRYPTION_KEY` — `openssl rand -hex 32` (must be
     64 hex chars; encrypts indexer/download-client credentials)
   - `BOOKORBIT_MIGRATION_ENCRYPTION_KEY` — `openssl rand -hex 32` (encrypts the
     Grimmory MariaDB credentials stored by the importer)
   - `BOOKORBIT_CLIENT_SECRET_DIGEST` — pbkdf2 digest for Authelia; keep the
     plaintext to paste into BookOrbit's OIDC settings:
     `authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 72 --random.charset rfc3986`
2. Merge. `bookorbit-pg` bootstraps with `initdb` and pre-creates the four
   extensions (`uuid-ossp`, `pg_trgm`, `unaccent`, `vector`; pgvector is not a
   trusted extension so the app user could not create it). After the first
   backup shows in `kubectl get backups -n media`, switch `bootstrap` to
   `recovery.source: bookorbit-pg-v1` (only matters if the cluster is recreated).
3. Open `https://bookorbit.${SECRET_DOMAIN}`, run the setup wizard with the
   bootstrap token, create the superuser (local account).
4. Settings → OIDC / SSO → add provider: issuer `https://auth.${SECRET_DOMAIN}`,
   client id `bookorbit`, the plaintext client secret, scopes
   `openid profile email groups`, claim mapping defaults (`preferred_username`,
   `name`, `email`, `groups`), enable auto-provision. Optionally map the `books`
   group to a permission set. Link the superuser from Settings → Account.
5. Add libraries: `/books/library` (Grimmory's books) and `/books/bookorbit`.
   Leave any metadata write-back / file organisation options **off** for the
   read-only library.
6. `lldap`: the `books` group already gates the other book apps; no new group.

## Grimmory importer

Settings → Migration → Grimmory. It reads Grimmory's MariaDB **directly** (no API
token): host `mariadb.media.svc.cluster.local`, port 3306, database `booklore`,
user `booklore`, password = Grimmory's `MARIADB_PASSWORD` (or better: create a
read-only MariaDB user for the importer). Path mapping: source prefix
`/data/media/books` → `/books/library`. Run the dry run first; the live run
**replaces** author/narrator/genre/tag links on matched books and is safe to
re-run. The ABS-importer data-loss bug (#1104) is fixed in 2.9.0, but dump the
target user's read statuses before a live run anyway. Grimmory covers live on its
own PVC, so leave `mediaRootPath` empty.

## Requests (beta) vs Shelfmark

Enabled by `BOOK_REQUEST_ENCRYPTION_KEY` + permissions `book_request_access`,
`manage_book_requests`, `book_request_auto_approve`, `book_request_self_fulfill`.
Sources: Prowlarr via torznab (tick "Allow private address"); no Shelfmark or
Anna's Archive backend ships, indexer plugins go in `/data/plugins/indexers/`.
Download client: qBittorrent with path mapping `/data/downloads` → `/downloads`
(qBittorrent's view → BookOrbit's view). Downloads are copied into the Book Dock
(different filesystem, so no hardlinks) and finalize into `/books/bookorbit`.

## Kobo / KOReader

- Kobo: `api_endpoint=https://bookorbit.${SECRET_DOMAIN}/api/v1/kobo/<deviceToken>`
  in `Kobo eReader.conf`. Needs `APP_URL` and forwarded proto/host headers (set
  on the route). Root-level `/api/v3/` and `/api/UserStorage/` are also used.
- KOReader: stock kosync URL `https://bookorbit.${SECRET_DOMAIN}/api/v1/koreader`,
  credentials from Settings → KOReader; or the bundled BookOrbit plugin
  (enter the bare host, it appends `/api/v1`). Matching is by partial-MD5, so files
  must be byte-identical to what BookOrbit indexed.
- Do **not** put Authelia forward-auth (SecurityPolicy) on this route; devices
  cannot complete it and the app has its own auth.

## Cutover checklist (when the bake-in is done)

- Flip `/books/library` to rw, enable write-back/kepub options as desired.
- `DISABLE_LOCAL_AUTH=true` once superusers are OIDC-linked.
- Retire Grimmory and Booksync (Hardcover sync is native in BookOrbit), drop the
  `grimmory`/`booksync` Authelia clients, remove `books.${SECRET_DOMAIN}` or
  re-point it here (then update `APP_URL`, the Authelia redirect URI and Kobo
  `api_endpoint`).
- Keep Audiobookshelf: BookOrbit has no ABS-compatible API for Plappa/ABS apps.
