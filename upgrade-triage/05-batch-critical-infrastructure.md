# Batch 5: Critical Infrastructure — Maintenance Windows Required

These PRs affect the cluster's CNI, storage layer, and operating system. Each
requires a maintenance window, sequential multi-step upgrades, or is blocked
pending upstream fixes. Do not batch these together — upgrade one subsystem at
a time with stability verification between each.

## PRs in this batch (4, covering 5 PRs)

---

### #47 + #48 — Rook Ceph v1.17.7 → v1.19.2 (operator + cluster)
- **Risk**: HIGH
- **Rating rationale**: Rook does not support skipping minor versions. You must
  go v1.17 → v1.18 → v1.19. Additionally, Rook v1.19 drops support for Ceph
  Reef (v18.x) — you must be running Ceph Squid (v19.2.0+) before upgrading to
  Rook 1.19. The v1.18 release introduced mandatory CSI operator migration.

- **onedr0p**: Was already on Rook 1.18.8 when he upgraded to 1.19.0 (#10392,
  Jan 20). He also did a major Ceph infrastructure rework (#10530, Feb 18):
  removed Thunderbolt ring networking, switched to pod networking, changed RBD
  compression to passive, modified storage class parameters. This suggests the
  1.18→1.19 path involved more than just a version bump for his environment.

- **Extra steps — Phase 1 (v1.17 → v1.18)**:
  1. Create a new Renovate PR or manual branch targeting Rook v1.18.x (latest
     patch in the 1.18 line).
  2. Read the [Rook v1.18 upgrade guide](https://rook.io/docs/rook/v1.18/Upgrade/rook-upgrade/).
  3. **Upgrade Ceph first** if on Reef v18.x: set the Ceph image to Squid
     v19.2.0+ in the CephCluster CR and wait for the upgrade to complete:
     ```bash
     kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph status
     kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph versions
     ```
  4. CSI operator migration: Rook 1.18 moves CSI to an operator model. Follow
     the migration docs carefully.
  5. Verify cluster health: `ceph status` should show HEALTH_OK.

- **Extra steps — Phase 2 (v1.18 → v1.19)**:
  1. Only proceed after v1.18 has been stable for at least 24-48 hours.
  2. Verify Ceph version is Squid v19.2.0+ (Reef is dropped in Rook 1.19).
  3. Merge PRs #47 and #48 together (operator and cluster must match).
  4. Monitor OSD, MON, and MDS pods during rollout:
     ```bash
     watch kubectl -n rook-ceph get pods
     kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph -w
     ```
  5. StorageClass immutability: if you need to change storage class parameters,
     create new classes rather than modifying existing ones.

- **Timeline**: Plan for 2-3 days total across both phases.

---

### #85 — Cilium 1.18.6 → 1.19.1
- **Risk**: HIGH — RECOMMEND HOLD
- **Rating rationale**: Three independent blockers:
  1. **Open regression (cilium/cilium#44430)**: Users report SSH and external
     host connectivity loss after upgrading to 1.19.x. No fix merged yet.
  2. **BPF memory allocation failure (cilium/cilium#44221)**: Reported on the
     exact source version (1.18.6→1.19.0).
  3. **CRD migration required**: `CiliumLoadBalancerIPPool` API must change from
     `cilium.io/v2alpha1` to `cilium.io/v2`. Your `networks.yaml` likely needs
     updating.

- **onedr0p**: Merged 1.19.0 (#10451, Feb 4) but **tried to revert at 3am**
  (#10459, Feb 6) back to 1.18.5. The revert diff is massive — shows dozens of
  ConfigMap key removals/additions, health port naming changes, RBAC changes,
  and image swaps. He then reverted the revert (#10461, Feb 6 12pm), deciding to
  push forward. He also did prep work switching to the official OCI chart
  repository (#10339) before the upgrade. Eventually stabilized on 1.19.1
  (#10528, Feb 17) — but this was a 2-week turbulent process.

- **Recommendation**: Wait for Cilium 1.19.2+ which should fix the host
  connectivity regression. Monitor the GitHub issue for resolution.

- **When you do upgrade — extra steps**:
  1. Switch to the official Cilium OCI repository (not a mirror) first, as
     onedr0p did.
  2. Update CRDs:
     ```bash
     grep -r "cilium.io/v2alpha1" kubernetes/ --include="*.yaml"
     ```
     Change `CiliumLoadBalancerIPPool` from `v2alpha1` to `v2`.
  3. Review your Cilium ConfigMap values against 1.19 defaults. Key changes:
     - `bpf.tproxy: true` is new
     - `policy-deny-response` removed
     - `enable-tunnel-big-tcp` removed
     - Health probe ports changed from named (`health`) to numeric (`9879`)
  4. **Have out-of-band console access ready** (IPMI/iLO/Talos console). If the
     CNI breaks, you lose SSH access to nodes.
  5. Upgrade during a maintenance window. Monitor connectivity:
     ```bash
     # From outside the cluster
     ping <node-ip>
     ssh <node-ip>
     # From inside the cluster
     kubectl exec -it <test-pod> -- curl -s https://kubernetes.default
     ```

---

### #11 + #21 — Talos v1.12.4 + Kubelet v1.35.1
- **Risk**: CRITICAL — Multi-step, coupled upgrades
- **Rating rationale**: Talos Linux is the node operating system. The installer
  PR (#11) upgrades the Talos image, and the kubelet PR (#21) upgrades
  Kubernetes. These are tightly coupled — Talos v1.12.4 bundles k8s 1.35.0.

  **You cannot skip Talos minor versions.** If you're on v1.10, you must go
  v1.10 → v1.11 → v1.12. Kubernetes also cannot skip minor versions — if you're
  on 1.33, you need 1.33 → 1.34 → 1.35.

  Kubernetes 1.35 removes cgroup v1 support entirely. Talos v1.12 jumps the
  kernel from 6.12 to 6.18 and deprecates the legacy network config format in
  favor of a new multi-document format.

- **onedr0p**: Was already on Talos v1.12.0. Upgraded to v1.12.1 (#10300, Jan 5)
  but **reverted** (#10324, Jan 8), then re-merged (#10325, Jan 9). The revert
  suggests even minor Talos patches can cause issues. Eventually reached v1.12.4
  (#10467, Feb 17) via incremental patches. For kubelet v1.35.1, merged as part
  of the Talos group (#10477, Feb 17).

- **Extra steps**:
  1. **Determine your current Talos version**:
     ```bash
     talosctl version --nodes <node-ip>
     ```
  2. **If on v1.10 or v1.11 — create intermediate upgrade PRs**:
     - v1.10 → v1.11.x (latest patch)
     - v1.11 → v1.12.x (latest patch)
     Each step requires:
     ```bash
     talosctl upgrade --nodes <node-ip> \
       --image ghcr.io/siderolabs/installer:v1.XX.X
     ```
     Upgrade one node at a time. Wait for it to rejoin the cluster.
  3. **Verify cgroup v2**: Kubernetes 1.35 drops cgroup v1. Talos uses cgroup v2
     by default, but verify:
     ```bash
     talosctl read /proc/filesystems --nodes <node-ip> | grep cgroup
     ```
  4. **Review Talos v1.12 network config changes**: If you use the legacy single-
     document machine config, it still works but is deprecated. The new format
     uses multi-document YAML.
  5. **Kubernetes version steps**: If jumping multiple k8s minors:
     - Upgrade Talos first (which bundles the target kubelet)
     - The kubelet version is determined by the Talos image, not a separate PR
     - PR #21 updates the kubelet image reference in Talos machine config
  6. **Maintenance window**: Schedule 2-4 hours. Upgrade nodes one at a time.
     Have Talos console access available (not just SSH, which goes through the
     CNI). Monitor:
     ```bash
     talosctl health --nodes <node-ip>
     kubectl get nodes -w
     ```

---

## Recommended order within this batch

1. **Rook Ceph** (v1.17 → v1.18 → v1.19) — 2-3 day process
2. **Talos + Kubelet** (version stepping as needed) — 2-4 hour maintenance window
3. **Cilium** — HOLD until 1.19.2+. Do this last, after Talos/k8s are stable.

Do NOT upgrade Cilium and Talos in the same maintenance window. If the CNI
breaks during a Talos upgrade, diagnosis becomes extremely difficult.
