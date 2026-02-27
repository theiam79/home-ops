# Batch 1: Immediate Merges — No Prep Required

Merge these in any order. All are patch bumps, cosmetic major bumps, or minor
versions with no documented breaking changes. None required extra work when
merged by onedr0p (where applicable).

## PRs in this batch (15)

### #87 — Reloader 2.2.7 → 2.2.8
- **Risk**: Negligible (patch)
- **Rating rationale**: Patch release with only bug fixes. Stakater Reloader is
  a simple controller that watches ConfigMaps/Secrets and triggers rollouts.
  Patch versions never change behavior.
- **onedr0p**: Merged same version (#10496, Feb 13). No issues.
- **Extra steps**: None.

### #83 — mc-router 1.4.0 → 1.4.1
- **Risk**: Negligible (patch)
- **Rating rationale**: itzg mc-router Helm chart patch. Bug fixes only.
- **onedr0p**: N/A (different stack).
- **Extra steps**: None.

### #64 — Promtail 6.17.0 → 6.17.1
- **Risk**: Negligible (patch)
- **Rating rationale**: Grafana Promtail chart patch release.
- **onedr0p**: N/A (uses VictoriaLogs).
- **Extra steps**: None.

### #54 — tnu 0.4.3 → 0.4.4
- **Risk**: Negligible (patch)
- **Rating rationale**: jfroy/tnu patch release. Minimal blast radius.
- **onedr0p**: N/A.
- **Extra steps**: None.

### #74 — cert-manager v1.19.2 → v1.19.4
- **Risk**: Low (security patch)
- **Rating rationale**: Contains fixes for CVE-2025-68121 and CVE-2026-24051.
  Maintainers recommend all users upgrade. No behavior changes.
- **onedr0p**: Merged through v1.19.3 (#10443) and v1.19.4 (#10556). No issues.
- **Extra steps**: None.

### #80 — Cloudflared container 2026.1.2 → 2026.2.0
- **Risk**: Low (minor)
- **Rating rationale**: Cloudflare tunnel daemon update. The `proxy-dns` feature
  was removed in 2026.x but this repo doesn't use it. Security fixes included.
- **onedr0p**: Merged same version (#10465, Feb 7). No issues.
- **Extra steps**: None.

### #82 — Cloudflared tool (mise) 2025.11.1 → 2026.2.0
- **Risk**: Low (local tool only)
- **Rating rationale**: Updates the local CLI tool version in `.mise.toml`. Does
  not affect running cluster. Same codebase as #80.
- **Extra steps**: None.

### #81 — Reflector 9.1.7 → 10.0.12
- **Risk**: Low (cosmetic major bump)
- **Rating rationale**: Despite being a "major" version bump, v10.0.0 of
  Emberstack Reflector changed ZERO application code. The v10.0.0 commit
  (e367cd4) only bumped CI dependencies (GitHub Actions upload/download
  artifact). All subsequent 10.0.x releases are also automated dependency bumps.
  No Helm values changes, no API changes, no behavioral changes.
- **onedr0p**: Not visible in recent PRs (may auto-merge or not use).
- **Extra steps**: None.

### #88 — Flux Operator 0.40.0 → 0.42.1
- **Risk**: Low (minor)
- **Rating rationale**: Additive features only. No breaking changes documented.
- **onedr0p**: Merged multiple flux-operator updates through Feb. Also did a
  separate "add anon auth to flux operator" chore (#10561) adding a
  ClusterRoleBinding — check if you need the same.
- **Extra steps**: Review whether you need an anonymous auth ClusterRoleBinding
  similar to onedr0p's #10561. If your Flux setup requires anonymous access to
  OCI registries, you may need this.

### #13 — app-template 4.0.1 → 4.6.2
- **Risk**: Low (minor within same major)
- **Rating rationale**: bjw-s app-template chart. Minor version bumps within the
  4.x line are additive (new features, helpers). No breaking changes.
- **onedr0p**: Already at 4.6.2 (#10370, Jan 16). No issues.
- **Extra steps**: None.

### #29 — System Upgrade Controller v0.15.2 → v0.19.0
- **Risk**: Low (minor)
- **Rating rationale**: Rancher system-upgrade-controller. No breaking API
  changes across this range. Incremental Kubernetes version compatibility.
- **onedr0p**: N/A (different upgrade approach).
- **Extra steps**: None.

### #39 — Gatus v5.18.1 → v5.35.0
- **Risk**: Low (17 minor versions, but no breaking changes documented)
- **Rating rationale**: Large version range but Gatus v5.x maintains backward
  compatibility. Config format unchanged. New features are additive (more
  endpoint types, alerting providers).
- **onedr0p**: Already at v5.35.0 (#10542, Feb 20). No issues.
- **Extra steps**: Monitor UI and alerting after deploy to confirm dashboards
  render correctly.

### #71 — actions/checkout v4.3.1 → v6.0.2
- **Risk**: Low (CI only)
- **Rating rationale**: No functional API changes for callers. Internal change:
  git credentials now stored in `$RUNNER_TEMP` instead of `$RUNNER_WORKSPACE`.
  Transparent to workflows that just use `actions/checkout`.
- **onedr0p**: N/A (different CI setup).
- **Extra steps**: None.

### #68 — flux-local v7.11.0 → v8.1.0
- **Risk**: Low (CI only)
- **Rating rationale**: Used as a GitHub Action (Docker image). Python version
  requirement changed internally but doesn't affect Docker-based usage. CLI
  arguments unchanged.
- **onedr0p**: N/A.
- **Extra steps**: None.

### #53 — tj-actions/changed-files v46.0.5 → v47.0.4
- **Risk**: Low (CI only) — BUT verify SHA
- **Rating rationale**: No breaking changes in v47. However, this action had a
  **supply chain attack in March 2025 (CVE-2025-30066)** where malicious code
  was injected via a compromised maintainer token. The action was restored but
  trust was damaged.
- **onedr0p**: N/A.
- **Extra steps**: **Verify the pinned SHA in the PR matches the official
  tj-actions/changed-files v47.0.4 release tag.** Run:
  `gh api repos/tj-actions/changed-files/git/ref/tags/v47.0.4 --jq '.object.sha'`
  and compare to the SHA in the workflow file.
