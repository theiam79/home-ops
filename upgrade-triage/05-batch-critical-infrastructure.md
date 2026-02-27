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

## Talos (#11) + Kubelet (#21) — v1.12.4 + k8s v1.35.1 🔄 IN PROGRESS

### Steps 1-2: ✅ COMPLETE — deployed 2026-02-27

- Talos upgraded v1.10.4 → v1.11.6 (all 7 nodes)
- Kubernetes upgraded v1.33.2 → v1.34.4 (siderolabs kubelet latest for 1.34)
- Fixed: added `admissionregistration.k8s.io/v1beta1=true` to API server
  runtime-config — `MutatingAdmissionPolicy` graduated from v1alpha1 to v1beta1
  in k8s 1.34, causing apiserver crash loops without this.

### Steps 3-4: ⏸️ ON HOLD

Paused pending investigation of reported Talos v1.12 concerns. Current state
(Talos v1.11.6 / k8s v1.34.4) is stable.

**When resuming:**

#### Step 3: Talos v1.11.6 → v1.12.4

1. Investigate reported v1.12 concerns before proceeding
2. Update `talos/talenv.yaml`: set Talos version to `v1.12.4`
3. Regenerate configs: `task talos:generate-config`
4. Upgrade each node: `task talos:upgrade-node IP=<ip>` one at a time
5. Verify: `talosctl health`, `kubectl get nodes`

#### Step 4: Kubernetes v1.34.4 → v1.35.1

1. Verify cgroup v2: `talosctl read /proc/filesystems --nodes <ip> | grep cgroup`
2. Check siderolabs kubelet image availability for v1.35.1
3. Update `talos/talenv.yaml`: set Kubernetes version
4. Run: `task talos:upgrade-k8s`
5. Verify: `kubectl version`, `kubectl get nodes`
6. May need to update runtime-config if MutatingAdmissionPolicy graduates again

#### Post-upgrade cleanup

1. Close PRs #11 and #21 (versions applied manually via stepping).
2. Commit final `talos/talenv.yaml` and regenerated configs.
3. Verify all workloads healthy, VolSync jobs running, Ceph HEALTH_OK.

**Key lessons from Steps 1-2:**
- Use `task talos:upgrade-node` and `task talos:upgrade-k8s` (not raw talosctl)
- Regenerate configs before upgrading k8s (version baked into machine configs)
- Check API server feature gate / runtime-config compatibility at each k8s minor
- Siderolabs kubelet images lag slightly behind upstream k8s releases

---

## Recommended order

1. **Rook Ceph** — Phase 2 after v1.18 soak ✅ Phase 1 done
2. **Talos + Kubelet** — After Ceph is stable
3. **Cilium** — HOLD until 1.19.2+, do last after Talos/k8s stable

Do NOT upgrade Cilium and Talos in the same maintenance window.
