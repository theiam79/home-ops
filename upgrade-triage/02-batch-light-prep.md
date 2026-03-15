# Batch 2 — Light Prep (minor config or verification)

---

## #168 — Talos installer v1.12.4 → v1.12.5

- **Risk:** Low-Medium
- **Rating rationale:** Patch release (Mar 9, 2026). Fixes: nftables set range calculation, DHCP unicast renewal, raw encryption key newline handling, host resolution without hostname. No breaking changes.
- **Reference repo:** onedr0p merged v1.12.5 (#10613) cleanly on Mar 9. **However**, they have a history of Talos patch reverts due to factory image availability lag (#9965 for v1.11.3, #10324 for v1.12.1). Both times they reverted same-day and re-applied the next day.
- **Extra steps:**
  1. Verify Talos factory images for v1.12.5 are available before merging (should be fine since it's been 5 days): `talosctl image default`
  2. Apply one node at a time: `talosctl upgrade --nodes <node> --image <factory-image>`
  3. Verify node health after each: `talosctl health --nodes <node>`

---

## #128 — volsync 0.14.0 → 0.15.0

- **Risk:** Low-Medium
- **Rating rationale:** `kube-rbac-proxy` sidecar removed — metrics auth now handled natively by controller-runtime. If you have ServiceMonitor configs referencing the rbac-proxy port (8443), they need updating.
- **Reference repo:** onedr0p uses the perfectra1n fork (currently v0.17.11), not upstream. They have an open PR (#10636) for moverVolumes NFS config. Not directly comparable, but the rbac-proxy removal is a universal change.
- **Extra steps:**
  1. Check if you have a ServiceMonitor targeting volsync's kube-rbac-proxy port:
     ```bash
     grep -r "volsync" kubernetes/ --include="*servicemonitor*" -l
     grep -r "8443" kubernetes/apps/ --include="*.yaml" | grep -i volsync
     ```
  2. If found, update to the new metrics endpoint.
  3. Verify VolSync ReplicationSources reconcile after upgrade:
     ```bash
     kubectl get replicationsource -A
     ```

---

## #129 — kube-prometheus-stack 82.4.3 → 82.10.3

- **Risk:** Low-Medium
- **Rating rationale:** Patch bumps within same major (82.x). No breaking changes documented. However, Prometheus Operator CRDs may have been updated within this range, and Helm does not auto-upgrade CRDs.
- **Reference repo:** onedr0p takes every kube-prometheus-stack patch without issues. The 81.x → 82.0.0 jump was marked breaking but merged cleanly. They've gone through 82.0.0 → 82.10.3 incrementally without reverts.
- **Extra steps:**
  1. Check if Prometheus Operator version changed between 82.4.3 and 82.10.3.
  2. If CRD version bumped, apply CRDs manually before merging:
     ```bash
     kubectl apply --server-side -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/<version>/example/prometheus-operator-crd/monitoring.coreos.com_alertmanagerconfigs.yaml
     kubectl apply --server-side -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/<version>/example/prometheus-operator-crd/monitoring.coreos.com_prometheusrules.yaml
     # ... etc for all CRDs
     ```
  3. Verify Prometheus and Alertmanager pods restart cleanly.

---

## #179 — add-pr-comment v2.8.2 → v3.9.0 (GitHub Action)

- **Risk:** Low-Medium
- **Rating rationale:** Major version bump for a GitHub Action. Currently pinned by SHA in `.github/workflows/flux-local.yaml`. The v3 API is largely backward-compatible — main additions are automatic message truncation, library exports, and new input options. No inputs were removed.
- **Reference repo:** No comparison available.
- **Extra steps:**
  1. Review the action's v3 migration notes for any renamed/removed inputs.
  2. Update the SHA pin in `.github/workflows/flux-local.yaml` to match the new v3.9.0 tag.
  3. Test by opening a draft PR and verifying the comment posts correctly.
