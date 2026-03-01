# Batch 5 — Critical Infrastructure (maintenance window)

These affect CNI, OS/kernel, or Kubernetes version. Require a maintenance window, careful sequencing, and rollback plans.

---

## #85 — Cilium 1.18.6 -> 1.19.1 (CNI)

- **Risk:** Medium-High
- **Rationale:** Cilium is the CNI — a failed upgrade means cluster-wide networking loss. Cilium 1.19 has a `CiliumLoadBalancerIPPool` API version change (`v2alpha1` -> `v2`) that directly affects your config. Removed flags don't impact your values, and you don't use Cilium's Gateway API (separate Envoy Gateway). However, a user-reported regression ([cilium#44221](https://github.com/cilium/cilium/issues/44221)) describes complete networking failure on 1.18->1.19 upgrade.
- **Reference repo:** onedr0p merged Cilium 1.19.0 on 2026-02-04, **reverted it 2 days later**, then **re-reverted (re-applied) 9 hours after that**. They are now stable on 1.19.1. The revert suggests initial instability but ultimate success. They also migrated the chart source from a mirror to the official Cilium OCI repo beforehand.
- **Extra steps:**
  1. **Update `CiliumLoadBalancerIPPool` apiVersion** before or during the upgrade:
     ```yaml
     # In kubernetes/apps/kube-system/cilium/app/networks.yaml
     # Change: apiVersion: cilium.io/v2alpha1
     # To:     apiVersion: cilium.io/v2
     ```
  2. Update the Cilium chart version in both:
     - `kubernetes/apps/kube-system/cilium/app/ocirepository.yaml`
     - `bootstrap/helmfile.d/01-apps.yaml`
  3. After merge, monitor pod connectivity across all namespaces:
     ```
     cilium status
     cilium connectivity test
     kubectl get pods -A | grep -v Running
     ```
  4. **Have a rollback plan ready.** If networking breaks, revert the chart version and CRD changes immediately.
  5. **Do NOT upgrade simultaneously with Talos 1.12.** The eBPF verifier regression on kernel 6.18.x ([siderolabs/talos#12726](https://github.com/siderolabs/talos/issues/12726)) compounds with Cilium changes. Upgrade Cilium first on the current Talos/kernel, validate, then upgrade Talos separately.

---

## #118 + #119 — Talos v1.10.4 -> v1.12.4 + Kubelet v1.33.2 -> v1.35.2 (OS + Kubernetes)

These are tightly coupled and must be sequenced together.

- **Risk:** High
- **Rationale:** Two minor OS versions and two minor Kubernetes versions across 7 nodes. Sequential upgrade is **mandatory** for both Talos (1.10->1.11->1.12) and Kubernetes (1.33->1.34->1.35). Talos 1.12 ships kernel 6.18.x which has a known eBPF verifier regression affecting Cilium ([siderolabs/talos#12726](https://github.com/siderolabs/talos/issues/12726)). The `.machine.network` config format is deprecated in 1.12 but still functional.
- **Reference repo:** onedr0p upgraded incrementally through every version. Talos updates triggered multiple reverts due to factory image availability timing (merged, reverted same day, re-applied next day). Kubelet upgrades were smooth with zero reverts. They also removed a Talos feature gate (`ResourceHealthStatus`) as a chore commit during the 1.11 cycle.

### Upgrade Sequence

**Step 1: Talos 1.10.4 -> 1.11.x + Kubernetes 1.33 -> 1.34**

1. Update Talos installer image to latest 1.11.x in talconfig.
2. Regenerate machine configs with `talhelper`.
3. Upgrade control plane nodes one at a time:
   ```
   talosctl upgrade --nodes <cp-node> --image factory.talos.dev/installer/...:v1.11.x
   ```
4. Upgrade worker nodes one at a time.
5. After all nodes are on Talos 1.11, upgrade Kubernetes:
   ```
   talosctl upgrade-k8s --to 1.34.x
   ```
6. Validate cluster health. Run workloads for at least 24-48 hours before proceeding.

**Step 2: Talos 1.11.x -> 1.12.4 + Kubernetes 1.34 -> 1.35.2**

1. **CRITICAL:** Verify Cilium stability on the current version first. The kernel 6.18.x eBPF verifier bug may cause node instability and networking loss.
2. Check [siderolabs/talos#12726](https://github.com/siderolabs/talos/issues/12726) for resolution status. **If still open, HOLD this step.**
3. If proceeding, same node-by-node upgrade process as Step 1.
4. After all nodes on 1.12, upgrade Kubernetes:
   ```
   talosctl upgrade-k8s --to 1.35.2
   ```
5. Monitor for eBPF verifier errors:
   ```
   talosctl dmesg --nodes <node> | grep -i "bpf\|verifier\|INVARIANTS"
   ```

### Post-upgrade

- No machine config format migration is required (legacy format continues to work in 1.12).
- Plan eventual migration from `.machine.network` to `NetworkConfig` documents at a later date.

---

## #115 — Gluetun v3.39.1 -> v3.41.1 [HOLD]

- **Risk:** High
- **Rationale:** **Do not upgrade.** Gluetun v3.41 **removed the `HEALTH_VPN_DURATION_INITIAL` env var** which your config relies on (`HEALTH_VPN_DURATION_INITIAL: "15s"`) to give WireGuard time to establish before health checks begin. Without it, the hardcoded 6-second timeout causes the exact startup health check cycling that prompted the v3.39.1 pin. Additionally, v3.40 replaced Unbound with a custom Go DNS resolver that has known issues in Kubernetes environments, and the control server API now requires authentication on all routes.
- **Reference repo:** No comparison available (onedr0p removed VPN networking entirely).
- **HOLD condition:** Do not upgrade until upstream gluetun provides a replacement mechanism for configuring the VPN startup health check timeout. Track:
  - [qdm12/gluetun#2942](https://github.com/qdm12/gluetun/issues/2942) — health check restarting VPN
  - [qdm12/gluetun#3069](https://github.com/qdm12/gluetun/issues/3069) — health check failures
  - [qdm12/gluetun#3134](https://github.com/qdm12/gluetun/issues/3134) — ongoing health check issues
- **Extra steps:** None. Keep pinned at v3.39.1.
