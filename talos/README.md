# Talos

Day-2 ops on the cluster's Talos machine config are driven by Jinja2 templates
rendered with [`minijinja-cli`](https://github.com/mitsuhiko/minijinja/tree/main/minijinja-cli)
and pieced together with `talosctl machineconfig patch`. Secrets come from
Bitwarden Secrets Manager via `bws run --`.

## Layout

- `machineconfig.yaml.j2` — base config used by every node. `{% if ENV.CONTROLPLANE == "true" %}` blocks gate CP-only sections.
- `nodes/<hostname>.yaml.j2` — per-node patch (machine type, hostname, network interfaces, disk selector, per-node `LinkAliasConfig`).
- `talenv.yaml` — Talos + Kubernetes versions, Renovate-managed.
- `talsecret.yaml` — `${VAR}`-templated secrets file. `envsubst` fills it in at bootstrap time to feed `talosctl gen config --with-secrets`. Also serves as the canonical list of env vars `bws` must provide.
- `clusterconfig-jinja/` — generated, gitignored output of `task talos:generate-config`.
- `clusterconfig/` — holds `talosconfig` (the talosctl client config). Created at bootstrap by `task talos:talosconfig`.
- `../kubeconfig.oidc.yaml` — committed OIDC kubeconfig; see [Kubernetes OIDC](#kubernetes-oidc).

## Tasks

All `task talos:*` recipes need to be run under `bws run --` so secrets
populate the template env. The recipes look up which node a given IP belongs
to by grepping `nodes/*.yaml.j2`, so callers stay IP-driven (no NODE param
needed).

| Task | Use |
|---|---|
| `task talos:generate-config` | Render every node into `clusterconfig-jinja/<hostname>.yaml` |
| `task talos:render-config NODE=<hostname>` | Render one node to stdout (debugging) |
| `task talos:talosconfig [FORCE=true]` | Materialize `clusterconfig/talosconfig` from bws env vars |
| `task talos:apply-node IP=<ip>` | Render + apply to a running node |
| `task talos:join-node IP=<ip>` | Render + apply with `--insecure`, retry until accepted (maintenance-mode node) |
| `task talos:upgrade-node IP=<ip>` | `talosctl upgrade` using the install image from the rendered config |
| `task talos:upgrade-k8s` | `talosctl upgrade-k8s --to <talenv.yaml's kubernetesVersion>` |
| `task talos:reset` | Reset every node in the talosconfig context to maintenance mode |
| `task talos:shutdown-cluster` | `talosctl shutdown` every node |

## Bootstrap

```
bws run -- task bootstrap:talos
```

Drives, in order:
1. `task talos:generate-config` — render every node's machineconfig.
2. `task talos:talosconfig FORCE=true` — `talosctl gen config --with-secrets <envsubst talsecret.yaml>` → talosconfig, then `talosctl config node …` to add every node IP.
3. Per-node `talosctl apply-config --insecure` in a retry loop.
4. `talosctl bootstrap` (etcd).
5. `talosctl kubeconfig <root> --force`.

Nodes must be in maintenance mode (fresh install) for step 3 to succeed.

## Kubernetes OIDC

Day-to-day `kubectl` authenticates through Authelia; the bws-minted admin
kubeconfig (`system:masters`, from step 5 above) stays as the break-glass path
and is still what bootstrap produces. Nothing in bootstrap depends on OIDC.

Pieces:
- `machineconfig.yaml.j2` → kube-apiserver `oidc-*` extraArgs trust
  `https://auth.tylerhundley.dev` for audience `kubernetes`. Users map to
  `oidc:<lldap uid>`, groups to `oidc:<lldap group>`.
- Authelia client `kubernetes` (public, PKCE, `id_token_claims` so groups are
  in the ID token) behind authorization policy `kubernetes`: only lldap group
  `admins`, two-factor.
- `kubernetes/apps/auth/kube-oidc` → `oidc:admins` bound to `cluster-admin`.
- `kubeconfig.oidc.yaml` (repo root) → secret-free kubeconfig that runs
  `kubelogin get-token` (mise tool).

Use from any device with the mise tools installed:

```
KUBECONFIG=kubeconfig.oidc.yaml kubectl auth whoami   # browser opens → Authelia login
```

Expect `oidc:<you>` in groups `oidc:admins`. Tokens cache in
`~/.kube/cache/oidc-login`; refresh tokens keep the session alive while in use
(Authelia's 90m refresh lifespan), so an idle session re-prompts. `kubelogin
clean` clears the cache. Headless boxes: SSH-forward port 8000 to a machine
with a browser.

Notes:
- The issuer is the public Cloudflare-fronted hostname, so kube-apiserver needs
  outbound HTTPS to it to fetch JWKS. If Authelia or the internet path is down,
  use the admin kubeconfig.
- Talos 1.14+ deprecates `.cluster.apiServer` in favour of multi-doc configs.
  The legacy extraArgs keep working there (Talos passes them through on the
  legacy path), but when migrating to `KubeAPIServerConfig` the `oidc-*` flags
  are rejected and must move to a `KubeAuthenticationConfig` document
  (`jwt[].issuer.url`, `audiences`, `claimMappings`).

## Schematic ID

Hardcoded in `machineconfig.yaml.j2`:

```
factory.talos.dev/installer/dc8730aa…
```

Switching to dynamic schematic ID (POSTing `schematic.yaml.j2` to
`factory.talos.dev/schematics` at render time) is a follow-up.
