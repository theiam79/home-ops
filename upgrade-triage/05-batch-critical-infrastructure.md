# Batch 5 — Critical Infrastructure (maintenance window)

---

## #85 — Cilium 1.18.6 → 1.19.1 — HOLD

- **Risk:** Critical
- **Rating rationale:** Multiple **open, unresolved regressions** that directly affect your feature set:
  1. **[#44430](https://github.com/cilium/cilium/issues/44430)** — External access to host services broken after upgrade. SSH to nodes stops working. Outbound connections fail. Multiple users confirm NOT fixed in 1.19.1. Suspected cause: new "wildcard service" logic introducing `DROP_NO_SERVICE` BPF datapath rules.
  2. **[#44221](https://github.com/cilium/cilium/issues/44221)** — BPF map allocation failure (`failed to create neighbors v4 bpf map: cannot allocate memory`). Cilium agent crashes, nodes become unreachable. **Reported on Talos Linux v1.12.3 with kernel 6.18.8-talos** — your exact platform.
  3. Both issues affect the exact feature combination you use: **L2 announcements + kubeProxyReplacement + native routing + DSR + LoadBalancer**.
- **Reference repo:** onedr0p merged 1.19.0 (#10451, Feb 4), **reverted to 1.18.5 two days later** (#10459, Feb 6), then **re-reverted back to 1.19.0** hours later (#10461). They removed `tproxy: true` during the upgrade. Currently stable on 1.19.1 (#10528). The revert-then-re-revert suggests a transient issue or manual intervention was needed.
- **Helm values to review when upgrading:**
  - `kubeProxyReplacementHealthzBindAddr: 0.0.0.0:10256` — may be deprecated/renamed in 1.19.
  - `--l2-pod-announcements-interface` removed — must use `--l2-pod-announcements-interface-pattern` instead.
- **HOLD condition:** Wait for Cilium **v1.19.2+** that explicitly fixes issues [#44430](https://github.com/cilium/cilium/issues/44430) and [#44221](https://github.com/cilium/cilium/issues/44221). Monitor both issues for resolution.
- **When ready:**
  1. Ensure out-of-band access to all nodes via `talosctl` on a separate network path.
  2. Have rollback ready: change OCI tag back to `1.18.6`.
  3. Verify `kubeProxyReplacementHealthzBindAddr` is still valid in 1.19 chart.
  4. Upgrade during a maintenance window with monitoring of node connectivity.

---

## #115 — Gluetun v3.39.1 → v3.41.1 — HOLD

- **Risk:** High
- **Rating rationale:** Two blocking issues remain **unresolved** in v3.41.1:
  1. **DNS resolver (v3.40.0+):** Unbound replaced with a custom Go resolver (`qdm12/dns@v2.0.0-rc8`). Your config uses `DOT: "off"` + `DNS_KEEP_NAMESERVER: "on"` for cluster DNS — these env vars were **renamed** in v3.41.0.
  2. **Startup health check (v3.41.0+):** Health check overhauled with a **hardcoded 6-second startup timeout**. `HEALTH_VPN_DURATION_INITIAL` was removed. WireGuard often needs >6s to establish, causing repeated tun0 teardown/recreation that corrupts libtorrent connection state (torrents stall permanently).
  3. [#2942](https://github.com/qdm12/gluetun/issues/2942) is closed but appears to be housekeeping, not a confirmed fix for the startup timeout.
  4. [#3000](https://github.com/qdm12/gluetun/issues/3000) is closed — was user-specific config, not a code fix.
- **Reference repo:** onedr0p does not use gluetun (no comparison).
- **HOLD condition:** Wait for a release that either:
  - Makes `HEALTH_VPN_DURATION_INITIAL` configurable again, OR
  - Increases the hardcoded startup timeout to accommodate WireGuard
  - Monitor [#2942](https://github.com/qdm12/gluetun/issues/2942) for reopening or a new tracking issue.
