# Batch 4: Heavy Prep — CRD Updates, Bootstrap Changes, Coordinated Upgrades ✅ COMPLETE

All 4 PRs resolved on 2026-02-27.

## kube-prometheus-stack 73.2.2 → 82.4.1

The original plan called for a two-step sequence (#79 → #89), but #79 only bumped
bootstrap CRDs (not the cluster). Since bootstrap CRDs were already at 81.4.2 and
the HelmRelease has `crds.upgradeJob.enabled: true` with `forceConflicts: true`,
the intermediate step added no safety. Went directly to 82.4.1.

| PR | Title | Status |
|----|-------|--------|
| #79 | kps bootstrap CRDs 81.4.2 → 81.6.9 | ✅ Closed (superseded by #89) |
| #89 | kps 73.2.2 → 82.4.1 (bootstrap + cluster) | ✅ Merged |

Verified: Prometheus targets scraping, Alertmanager receiving alerts, Grafana
dashboards rendering, custom PrometheusRules (dockerhub, oom, zfs) intact.

## External Secrets 0.17.0 → 2.0.1 (two-step sequence)

Executed as planned. CRD size handling validated on the 0.20.4 step (no issues).

| PR | Title | Status |
|----|-------|--------|
| #24 | External Secrets 0.17.0 → 0.20.4 (bootstrap + cluster) | ✅ Merged |
| #86 | External Secrets 0.20.4 → 2.0.1 (bootstrap + cluster) | ✅ Merged |

Verified after each step: ExternalSecrets syncing, bitwarden-sdk-server running,
forced secret sync successful. Bootstrap and cluster versions kept in sync
throughout.
