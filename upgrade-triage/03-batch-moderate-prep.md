# Batch 3: Moderate Prep — Config Changes and Testing Required ✅ COMPLETE

5 of 6 PRs resolved on 2026-02-27. Helm CLI deferred.

| PR | Title | Prep Done | Status |
|----|-------|-----------|--------|
| #61 | Minecraft chart 4.26.3 → 5.1.1 | No nameOverride/fullnameOverride set, PVCs are existingClaim | ✅ Merged |
| #65 | k8s-sidecar 1.30.3 → 2.5.0 | Gatus init container memory bumped 128Mi → 256Mi | ✅ Merged |
| #36 | Loki chart 6.30.1 → 6.53.0 | Added `singleBinary.persistence.accessModes: [ReadWriteOnce]` | ✅ Merged |
| #9 | Grafana chart 9.2.2 → 9.4.5 | Step 1 of sequence, no prep needed | ✅ Merged |
| #55 | Grafana chart 9.4.5 → 10.5.15 | Removed Angular plugins and `GF_SECURITY_ANGULAR_SUPPORT_ENABLED` | ✅ Merged |
| #69 | Helm CLI 3.20.0 → 4.1.1 (mise) | Bootstrap uses flags needing Helm 4 validation | ⏸️ Deferred |

## Prep commits

- `039dfa1` — Loki accessModes fix and Gatus k8s-sidecar memory bump
- `d64d574` — Grafana Angular plugin removal (natel-discrete-panel, vonage-status-panel,
  GF_SECURITY_ANGULAR_SUPPORT_ENABLED)

## Notes

- **Grafana**: Upgraded in two steps (9.2.2 → 9.4.5 → 10.5.15). First reconciliation
  timed out with rate limiter error but succeeded on retry. Dashboards verified working.
  Angular plugins removed rather than replaced — will revisit if specific dashboards
  need panel replacements.
- **Helm CLI (#69)**: Deferred indefinitely. Helm 3 supported until November 2026.
  Bootstrap uses `--include-crds` and `--no-hooks` flags that need Helm 4 validation.
