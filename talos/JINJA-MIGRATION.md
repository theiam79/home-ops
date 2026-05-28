# Jinja-templated Talos config — migration in progress

The Talos machine config is migrating from `talhelper` (which renders
`talconfig.yaml` + `patches/`) to Jinja2 templates rendered with
[`minijinja-cli`](https://github.com/mitsuhiko/minijinja/tree/main/minijinja-cli),
matching the pattern onedr0p uses. Installed via `aqua:mitsuhiko/minijinja`.

Both paths coexist during the migration. **talhelper remains the source of
truth until every node has been validated against the new templates.**

## Layout

- `talos/machineconfig.yaml.j2` — base config (all nodes, with
  `{% if ENV.CONTROLPLANE == "true" %}` blocks for CP-only sections).
- `talos/nodes/<hostname>.yaml.j2` — per-node patch (machine type, hostname,
  network interfaces, disk selector, mgmt0 `LinkAliasConfig`).
- `talos/schematic.yaml.j2` — documentation only for now. Schematic ID is still
  hardcoded in the generated config (`factory.talos.dev/installer/dc8730aa…`).
  Switching to dynamic schematic ID is a follow-up.
- `talos/talenv.yaml` — Talos + Kubernetes versions (Renovate-managed).
- `talos/talsecret.yaml` — legacy; describes the env vars that the templates
  expect from `bws run --`. Will be retired in Phase 5.

## Render flow

`task talos:render-config NODE=<hostname>` does:

1. Detect CP vs worker by grepping `machine.type:` in the per-node template.
2. Render `machineconfig.yaml.j2` with `ENV.*` available (all current env vars
   + `ENV.CONTROLPLANE`).
3. Render the per-node template.
4. `talosctl machineconfig patch <global> -p @<node>` to merge.

Must be run under `bws run --` so secrets from Bitwarden are present in env.

## Validation gate

Before applying jinja-rendered config to any node:

```
bws run -- task talos:diff-config NODE=<hostname>
```

This generates the talhelper output (canonical), renders the new jinja output,
normalizes both with `yq eval-all 'sort_keys(..)'`, and shows a unified diff.

**Acceptance for cutover:** the diff is empty, or every line is in the
documented allowlist (see below).

### Expected-diff allowlist

After Phase-1 iteration, all 8 nodes are byte-equivalent under
`yq eval-all 'sort_keys(..)'` normalization **except** for one intentional
deviation:

- **`ceph0` `LinkAliasConfig` is emitted only on storage nodes** (dvergar-00,
  -01, -02, -03, -05). talhelper emitted it on every node because it was a
  cluster-wide global patch; the jinja layout scopes it to the per-node
  templates of nodes that actually have the I226-V card. Non-storage nodes
  (dvergar-04, -06, elli) no longer get a no-op alias config. This is
  cosmetic — Talos applies the alias only when the selector matches, so the
  runtime behavior is unchanged.

All other diffs were resolved by:
- Switching from the legacy `machine.network.interfaces[]` block to the modern
  standalone `LinkConfig` / `VLANConfig` / `Layer2VIPConfig` / `HostnameConfig`
  documents that Talos v1.13 prefers.
- Adding explicit Talos defaults that talhelper writes out (image refs,
  audit policy, kube prism, discovery, install image, kubelet defaults, etc.).
- Moving the CP-only `node.kubernetes.io/exclude-from-external-load-balancers`
  label out of the global template and into the per-node templates of the
  CPs that don't have their own `nodeLabels:`, matching talhelper's auto-add
  behavior.
- Gating `cluster.secretboxEncryptionSecret` to control planes only.
- Adding `--autoescape none` to the `minijinja-cli` invocation so YAML-aware
  autoescape doesn't quote string env var values.

## Apply

```
bws run -- task talos:apply-node-jinja IP=192.168.100.24 NODE=dvergar-04
```

Suggested rollout order (lowest blast radius first):

1. dvergar-04 (worker, no Ceph OSD)
2. dvergar-06 (worker, no Ceph OSD)
3. dvergar-03 (worker, Ceph OSD — first OSD node)
4. dvergar-05 (worker, Ceph OSD)
5. elli (worker)
6. dvergar-00 (CP, has the unusual Realtek + I226 NIC layout)
7. dvergar-01 (CP)
8. dvergar-02 (CP)

## Rollback

Per node:
```
bws run -- task talos:apply-node IP=<ip>      # old talhelper path
```

The talhelper-based tasks remain in `Taskfile.yaml` through Phase 4 of the
migration to keep this rollback intact.
