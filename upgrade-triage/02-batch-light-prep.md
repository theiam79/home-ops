# Batch 2: Light Prep — Minor Config or Verification Before Merge

These PRs are low risk but need a small config tweak, a value override, or a
quick verification before or immediately after merging.

## PRs in this batch (7)

### #51 — actions/labeler v5.0.0 → v6.0.1
- **Risk**: Low
- **Rating rationale**: CI-only change. The only breaking change is that `dot:
  true` is now the default (matches dotfiles in glob patterns). If your
  `.github/labeler.yaml` uses glob patterns, labels may start matching dotfiles.
- **onedr0p**: N/A.
- **Extra steps before merge**: Review `.github/labeler.yaml` for any glob
  patterns where matching dotfiles would be undesirable. If unsure, add
  `dot: false` to any affected patterns to preserve v5 behavior.

### #106 — NFS mount scoping and shelfmark permissions (community PR)
- **Risk**: Low
- **Rating rationale**: Manual PR from theiam79, not an automated dependency
  bump. Small diff (9 additions, 5 deletions). Modifies NFS mount paths and
  permissions for the media stack.
- **onedr0p**: N/A (different contributor).
- **Extra steps before merge**: Read the diff carefully. Verify the NFS paths
  and permission changes match your NAS export configuration. Test that media
  apps can still read/write after merge.

### #78 — Snapshot Controller 4.0.2 → 5.0.3
- **Risk**: Low-Medium
- **Rating rationale**: Initially rated Medium due to CRD ownership annotation
  concerns. **Downgraded after onedr0p evidence**: he merged 4.2.0 → 5.0.0
  (#10349, Jan 14) cleanly with no visible drama, touching only the
  HelmRelease and OCIRepository files. The breaking changes are RBAC-related
  (Update→Patch operations) which Helm handles automatically.
- **onedr0p**: Merged cleanly. Now on 5.0.3 (#10524).
- **Extra steps before merge**: Verify your snapshot CRDs aren't manually
  managed. If they are Helm-managed already, this should be seamless. If you see
  CRD ownership errors after merge, annotate them:
  ```bash
  for crd in volumesnapshotclasses.snapshot.storage.k8s.io \
              volumesnapshotcontents.snapshot.storage.k8s.io \
              volumesnapshots.snapshot.storage.k8s.io; do
    kubectl annotate crd "$crd" \
      meta.helm.sh/release-name=snapshot-controller \
      meta.helm.sh/release-namespace=kube-system --overwrite
    kubectl label crd "$crd" \
      app.kubernetes.io/managed-by=Helm --overwrite
  done
  ```

### #84 — Envoy Gateway v1.6.3 → v1.7.0
- **Risk**: Low-Medium
- **Rating rationale**: Initially rated Medium. **Downgraded after onedr0p
  evidence**: he merged this cleanly (#10458, Feb 5). He did prep work a week
  earlier (#10267) removing connection buffer limit and timeout settings from
  his envoy config.
- **onedr0p**: Merged cleanly. Prep: removed deprecated envoy config values.
- **Extra steps before merge**:
  1. Review your envoy gateway config for any deprecated connection buffer or
     timeout settings and remove them.
  2. After merge, check Grafana dashboards — `stats_tags` metric names changed
     in 1.7. Update any panels referencing old metric names.
  3. Note: invalid HTTPRoute filters now return HTTP 500 instead of being
     silently ignored. This surfaces latent config errors — check logs after
     deploy.

### #90 — SM-Operator 0.1.0 → 2.0.0
- **Risk**: Low (with fix)
- **Rating rationale**: Despite the large version number jump, the SM-Operator
  2.0.0 release has no real breaking changes for users. However, the upgrade
  will fail without a version constraint fix.
- **onedr0p**: N/A.
- **Extra steps before merge**: Your HelmRelease likely has a version constraint
  like `>=0.1.0 <1.0.0` that will block the upgrade. Update the semver
  constraint to `>=2.0.0 <3.0.0` (or remove it) before merging. Check with:
  ```bash
  grep -r "sm-operator" kubernetes/ --include="*.yaml" -l
  ```
  Then update the version constraint in the HelmRelease.

### #37 — VolSync 0.12.1 → 0.14.0
- **Risk**: Low-Medium
- **Rating rationale**: The `kube-rbac-proxy` sidecar was removed in this range.
  If you have `disableAuth: true` already set, this is a non-issue. The chart
  also introduced new replication features but existing ReplicationSources/
  Destinations are unaffected.
- **onedr0p**: Uses a different VolSync fork (`perfectra1n/volsync` 0.18.x), so
  no direct comparison. He did do a "chore: update volsync schedules" (#10554)
  around the same time.
- **Extra steps after merge**: Verify that Prometheus metrics scraping from
  VolSync still works. If you relied on the kube-rbac-proxy for metrics auth,
  you'll need to update your ServiceMonitor.

### #14 — OpenEBS 4.2.0 → 4.4.0
- **Risk**: Low-Medium (with fix)
- **Rating rationale**: OpenEBS chart 4.3.0 introduced a bundled observability
  stack (Loki, Alloy, MinIO) that is **enabled by default**. Without disabling
  these, the upgrade will deploy unwanted pods that consume resources and
  conflict with your existing Loki/monitoring stack.
- **onedr0p**: N/A.
- **Extra steps before merge**: Add these values to your OpenEBS HelmRelease
  before or alongside the version bump:
  ```yaml
  loki:
    enabled: false
  alloy:
    enabled: false
  ```
  Verify with `kubectl get pods -n openebs` after deploy that no unexpected
  Loki/Alloy/MinIO pods appear.
