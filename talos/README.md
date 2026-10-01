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

## Hardware watchdog

`machineconfig.yaml.j2` carries a `WatchdogTimerConfig` document for every
node: machined opens `/dev/watchdog0` and pets it on a schedule; if nothing
pets it for `timeout` (2m) the chipset asserts a hardware reset, exactly as
if someone pressed the reset button. On this fleet `/dev/watchdog0` is the
Intel PCH TCO timer (`iTCO_wdt`), a countdown that lives in the chipset and
keeps running when the CPU and kernel are wedged. That is the only mechanism
that recovers from a true hard hang: the Talos kernel ships no lockup
detector sysctls and no pstore backend, so a frozen node can neither notice
nor record the freeze itself.

**Why:** four unexplained hard freezes on three different machines in two
months (dvergar-00 2026-08-04 and 08-06, elli 2026-09-13, dvergar-06
2026-09-18), all the same shape: every process stops in the same second,
display dead, no ARP, nothing in pstore, nothing in the next boot's dmesg.
The 09-18 one went unnoticed for 12 days because Prometheus lived on the
dead node. With the watchdog a hung node resets itself ~2 minutes after the
hang and is `Ready` about a minute later.

**Verified 2026-10-01 on all 8 nodes:** `identity=iTCO_wdt`, `nowayout=0`,
and dmesg shows `iTCO_wdt: Found a Intel PCH TCO device` with no
`failed to reset NO_REBOOT flag, device disabled by hardware/BIOS` line.
That NO_REBOOT line is the one firmware setting that silently turns the TCO
timer into a no-op; check for it on any new node before trusting the
watchdog there.

**Rollout:** it is a runtime document, so `task talos:apply-node IP=<ip>`
applies it live, no reboot. Do dvergar-06 first, verify, then the rest.

```
talosctl -n <ip> get watchdogtimerstatus                   # DEVICE /dev/watchdog0  TIMEOUT 2m0s
talosctl -n <ip> read /sys/class/watchdog/watchdog0/state  # active
```

**Caveats:**

- A reset destroys whatever evidence was in RAM. The watchdog recovers the
  node; it does not explain the hang. Shipping kernel logs off-node
  (`KmsgLogConfig` → VictoriaLogs) is the complement and is tracked
  separately.
- A watchdog reset is a hard reset, with the same consequences as the manual
  power cycles we do today (in-flight RBD writes lost, mon/etcd member
  restarts). Nothing new to tolerate.
- 2m instead of the Talos default 1m is deliberate: machined is the only
  feeder, and a one-minute stall of machined on a node that is otherwise
  serving should not reset it. Minimum allowed is 10s.
- Talos closes the device cleanly (`nowayout=0`) on reboot, shutdown and
  kexec upgrades, so normal maintenance is unaffected.
- `/sys/class/watchdog/watchdog0/bootstatus` non-zero after a boot means the
  driver recorded a watchdog-triggered reset; 0 is inconclusive on iTCO, so
  also look at uptime and the absence of a graceful shutdown in VictoriaLogs.
- The `# Watchdog` comments on the `fs.inotify.*` sysctls in the same file
  are an unrelated application, not this.

## Schematic ID

Hardcoded in `machineconfig.yaml.j2`:

```
factory.talos.dev/installer/dc8730aa…
```

Switching to dynamic schematic ID (POSTing `schematic.yaml.j2` to
`factory.talos.dev/schematics` at render time) is a follow-up.
