# Batch 5: Critical Infrastructure — Maintenance Windows Required

These PRs affect the cluster's CNI, storage layer, and operating system. Each
requires a maintenance window, sequential multi-step upgrades, or is blocked
pending upstream fixes. Do not batch these together — upgrade one subsystem at
a time with stability verification between each.

---

## Rook Ceph (#47 + #48) — v1.17.7 → v1.19.2 ✅ COMPLETE

**Phase 1 (v1.17.7 → v1.18.9): ✅ COMPLETE** — deployed 2026-02-27.
- Ceph confirmed on Squid v19.2.3 (satisfies v1.19 prerequisite).
- Manual commit `36fa4a8` bumped both OCIRepositories to v1.18.9.
- OSDs rolled successfully, cluster reporting HEALTH_OK.

**Phase 2 (v1.18.9 → v1.19.2): ✅ COMPLETE** — deployed 2026-02-27.
- Soaked on v1.18.9 for 12+ hours before proceeding.
- Renovate rebased PRs #47 and #48 against v1.18.9, so both merged cleanly.
- MGR pods crashed during rollout (expected during minor upgrade), recovered.
- Cluster stable at v1.19.2.

---

## Cilium (#85) — v1.18.6 → v1.19.1 ⛔ ON HOLD

**Status**: Blocked on upstream regressions. Do not upgrade.

Three independent blockers:
1. **Open regression (cilium/cilium#44430)**: SSH and external host connectivity
   loss after upgrading to 1.19.x. No fix merged yet.
2. **BPF memory allocation failure (cilium/cilium#44221)**: Reported on the exact
   source version (1.18.6→1.19.0).
3. **CRD migration required**: `CiliumLoadBalancerIPPool` API must change from
   `cilium.io/v2alpha1` to `cilium.io/v2`.

**onedr0p experience**: Merged 1.19.0 but attempted 3am revert. 2-week turbulent
stabilization process.

**Action**: Wait for Cilium 1.19.2+ with host connectivity fix. Monitor
cilium/cilium#44430 for resolution.

**When upgrading — prep checklist**:
1. Switch to official Cilium OCI repository
2. Update `CiliumLoadBalancerIPPool` from `v2alpha1` to `v2`
3. Review ConfigMap values against 1.19 defaults
4. Have out-of-band console access ready (IPMI/Talos console, not SSH)
5. Schedule maintenance window

---

## Talos (#11) + Kubelet (#21) — v1.12.4 + k8s v1.35.2 ✅ COMPLETE

### Steps 1-2: ✅ COMPLETE — deployed 2026-02-27

- Talos upgraded v1.10.4 → v1.11.6 (all 7 nodes)
- Kubernetes upgraded v1.33.2 → v1.34.4 (siderolabs kubelet latest for 1.34)
- Fixed: added `admissionregistration.k8s.io/v1beta1=true` to API server
  runtime-config — `MutatingAdmissionPolicy` graduated from v1alpha1 to v1beta1
  in k8s 1.34, causing apiserver crash loops without this.

### Steps 3-4: ✅ COMPLETE — deployed 2026-02-27

- Talos upgraded v1.11.6 → v1.12.4 (all 7 nodes, `--reboot-mode=powercycle`)
- Kubernetes upgraded v1.34.4 → v1.35.2
- Dropped `admissionregistration.k8s.io/v1alpha1=true` from runtime-config
  (v1alpha1 no longer served in k8s 1.35).
- Migrated VolSync MutatingAdmissionPolicy manifests from v1alpha1 to v1beta1.
- Converted admission-controller patch from JSON6902 to strategic merge
  (`$$patch: delete` for talhelper escaping) — Talos v1.12 dropped JSON6902
  support for multi-document configs.
- OSD.1 went down after upgrade due to PodSecurity `baseline:latest` enforcement
  blocking Rook pods. Resolved by applying updated admission control config to
  CP nodes; OSD purged and rebuilt, Ceph back to HEALTH_OK with 5/5 OSDs.
- PRs #11 and #21 closed (versions applied manually via stepping).

**Key lessons:**
- Use `task talos:upgrade-node` and `task talos:upgrade-k8s` (not raw talosctl)
- Regenerate configs before upgrading k8s (version baked into machine configs)
- Check API server feature gate / runtime-config compatibility at each k8s minor
- Siderolabs kubelet images lag slightly behind upstream k8s releases
- Talos v1.12 requires strategic merge patches — use `$$patch:` to escape for talhelper
- Use `--reboot-mode=powercycle` to avoid kexec hang on v1.12

---

## Recommended order

1. **Rook Ceph** — ✅ COMPLETE (v1.17.7 → v1.18.9 → v1.19.2)
2. **Talos + Kubelet** — ✅ COMPLETE (v1.10.4/v1.33.2 → v1.12.4/v1.35.2)
3. **Cilium** — HOLD until 1.19.2+, do last after Talos/k8s stable

Do NOT upgrade Cilium and Talos in the same maintenance window.
