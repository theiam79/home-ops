# Batch 5: Critical Infrastructure — Maintenance Windows Required

These PRs affect the cluster's CNI, storage layer, and operating system. Each
requires a maintenance window, sequential multi-step upgrades, or is blocked
pending upstream fixes. Do not batch these together — upgrade one subsystem at
a time with stability verification between each.

---

## Rook Ceph (#47 + #48) — v1.17.7 → v1.19.2 🔄 IN PROGRESS

**Phase 1 (v1.17.7 → v1.18.9): ✅ COMPLETE** — deployed 2026-02-27.
- Ceph confirmed on Squid v19.2.3 (satisfies v1.19 prerequisite).
- Manual commit `36fa4a8` bumped both OCIRepositories to v1.18.9.
- OSDs rolled successfully, cluster reporting HEALTH_OK.
- Soaking on v1.18.9 before proceeding.

**Phase 2 (v1.18.9 → v1.19.2): ⏳ WAITING**
- PRs #47 and #48 target v1.19.2 but will conflict on the version lines
  changed in Phase 1 (v1.17.7→v1.18.9 vs v1.17.7→v1.19.2).
- Will need to apply manually and close PRs, same as SM-Operator.
- **Proceed after v1.18.9 has been stable for 24-48 hours.**
- Monitor OSD, MON, and MGR pods during rollout.

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

## Talos (#11) + Kubelet (#21) — v1.12.4 + k8s v1.35.1 ⏳ PLANNING

**Status**: Needs version stepping plan. Cannot skip Talos or Kubernetes minors.

**Prerequisites to determine**:
- Current Talos version (`talosctl version`)
- Current Kubernetes version (`kubectl version`)
- Number of intermediate steps needed

**Key risks**:
- Kubernetes 1.35 removes cgroup v1 support entirely
- Talos v1.12 jumps kernel from 6.12 to 6.18
- Talos v1.12 deprecates legacy single-document network config
- onedr0p reverted a Talos v1.12.1 patch before re-merging

**Plan**: 2-4 hour maintenance window. Upgrade nodes one at a time via
`talosctl upgrade`. Have Talos console access available (not SSH).

---

## Recommended order

1. **Rook Ceph** — Phase 2 after v1.18 soak ✅ Phase 1 done
2. **Talos + Kubelet** — After Ceph is stable
3. **Cilium** — HOLD until 1.19.2+, do last after Talos/k8s stable

Do NOT upgrade Cilium and Talos in the same maintenance window.
