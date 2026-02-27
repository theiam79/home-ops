# Batch 2: Light Prep — Minor Config or Verification Before Merge ✅ COMPLETE

All 7 PRs resolved on 2026-02-27.

| PR | Title | Prep Done | Status |
|----|-------|-----------|--------|
| #51 | actions/labeler v5.0.0 → v6.0.1 | Verified no dotfile matching issues | ✅ Merged |
| #106 | NFS mount scoping and shelfmark permissions | Deferred — Shelfmark blocked on Deluge VPN | ✅ Closed |
| #78 | Snapshot Controller 4.0.2 → 5.0.3 | CRDs already Helm-managed with CreateReplace | ✅ Merged |
| #84 | Envoy Gateway v1.6.3 → v1.7.0 | No deprecated buffer/timeout settings found | ✅ Merged |
| #90 | SM-Operator 0.1.0 → 2.0.0 | Updated semver constraint to `<3.0.0` | ✅ Closed (applied manually) |
| #37 | VolSync 0.12.1 → 0.14.0 | `disableAuth: true` already set | ✅ Merged |
| #14 | OpenEBS 4.2.0 → 4.4.0 | Added `loki.enabled: false` and `alloy.enabled: false` | ✅ Merged |

## Prep commits

- `9e43294` — SM-Operator semver constraint and OpenEBS loki/alloy disable
- `b516696` — SM-Operator constraint aligned with Renovate (`<3.0.0`)
