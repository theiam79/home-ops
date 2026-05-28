# Jinja-templated Talos config — migration in progress

The Talos machine config is migrating from `talhelper` (which renders
`talconfig.yaml` + `patches/`) to Jinja2 templates rendered via a small Python
wrapper around `jinja2.Environment` (`scripts/render-talos-template.py`),
matching the pattern onedr0p uses with `minijinja-cli`.

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

### Expected-diff allowlist (TBD)

Will be populated during the diff-iteration loop. Document each accepted
difference with rationale (e.g. "key ordering — semantically identical",
"comment lines stripped by yq round-trip"). Treat unexplained diffs as bugs in
the templates.

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
