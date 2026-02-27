# Batch 4: Heavy Prep — CRD Updates, Bootstrap Changes, Coordinated Upgrades

These PRs touch core infrastructure and require updating bootstrap
configurations, CRD manifests, or careful sequencing. Each upgrade should be
done individually with monitoring between deploys.

Both upgrades in this batch use a two-step sequence: merge an intermediate PR
first to reduce the version gap, verify stability, then merge the target PR.

## PRs in this batch (4, in 2 sequences)

---

### #79 then #89 — kube-prometheus-stack 73.x → 81.6.9 → 82.4.1 (two-step sequence)

This is the highest-priority sequenced upgrade. onedr0p never skipped a kps
major version. You are 9 majors behind. This sequence splits it into two jumps.

#### Step 1: #79 — kube-prometheus-stack 73.x → 81.6.9
- **Risk**: Medium-High (large jump, but landing on a well-tested version)
- **Rating rationale**: This is still a significant jump (73→81, 8 major chart
  versions), but 81.6.9 is a mature patch release that onedr0p ran for weeks
  with dozens of incremental patches on top. It's a battle-tested landing point.
  The CRDs at 81.x are a generation behind 82.x, meaning this step exercises
  the CRD upgrade path without also taking on the 82.x Operator changes.

  Key breaking changes across 73→81:
  - PrometheusRule resource naming conventions changed.
  - Prometheus Operator CRDs updated (scrape classes, PrometheusAgent, new
    status subresources).
  - Thanos sidecar configuration restructured.
  - Default resource requests/limits changed.
  - `additionalPrometheusRulesMap` key naming may affect your custom rules
    (`dockerhub-rules`, `oom-rules`, `zfs-rules`).

- **onedr0p**: Was on 80.14.4 when he jumped to 81.0.0 (Jan 16). He then rode
  81.x for a full month through dozens of patches before jumping to 82.0.0.

- **Extra steps**:
  1. **Update bootstrap CRDs to 81.6.9 first**:
     ```bash
     # Edit bootstrap/helmfile.d/00-crds.yaml
     # Set kube-prometheus-stack CRD version to 81.6.9
     cd bootstrap && helmfile apply
     ```
  2. **Review your custom HelmRelease values** for deprecated keys between 73
     and 81. Particularly:
     - `additionalPrometheusRulesMap` structure
     - `thanosRuler` section
     - `prometheusOperator.admissionWebhooks`
     - Any hardcoded image tags that may conflict
  3. Merge PR #79.
  4. **Check for orphaned PrometheusRules**:
     ```bash
     kubectl get prometheusrules --all-namespaces
     ```
     Delete any old-named rules no longer managed by the HelmRelease.
  5. Verify:
     - All Prometheus targets are scraping (Prometheus UI → Status → Targets)
     - Alertmanager is receiving alerts
     - Grafana dashboards with Prometheus datasource still render
  6. **Wait at least 24 hours** on 81.6.9 before proceeding to Step 2.

#### Step 2: #89 — kube-prometheus-stack 81.6.9 → 82.4.1
- **Risk**: Medium (single major jump from a stable baseline)
- **Rating rationale**: With 81.6.9 stable, this becomes a single major version
  jump — the same size jump onedr0p made (81.6.9→82.0.0). The 82.x line brings
  Prometheus Operator v0.89.0 CRD changes, but the delta from 81.x is much
  smaller than from 73.x.

- **onedr0p**: Merged 81.6.9→82.0.0 (#10512, Feb 15). The PR touched
  `bootstrap/helmfile.d/00-crds.yaml` and the OCIRepository. He then rode 82.x
  through 82.4.1 with no issues.

- **Extra steps**:
  1. **Update bootstrap CRDs to 82.4.1**:
     ```bash
     # Edit bootstrap/helmfile.d/00-crds.yaml
     # Set kube-prometheus-stack CRD version to 82.4.1
     cd bootstrap && helmfile apply
     ```
  2. Merge PR #89.
  3. Verify same checklist as Step 1 (targets, alerts, dashboards).
  4. Clean up: close PR #10 (73.2.3 patch) if still open — it's now irrelevant.

---

### #24 then #86 — External Secrets 0.x → 0.20.4 → 2.0.1 (two-step sequence)

onedr0p jumped from chart 1.3.2 to 2.0.0. Your starting point is further back,
so this sequence adds a checkpoint on 0.20.4 to validate CRD handling before
the major version jump.

#### Step 1: #24 — External Secrets → 0.20.4
- **Risk**: Medium
- **Rating rationale**: This step crosses two important boundaries:
  1. **v1beta1→v1 API migration** (happened ~0.16-0.17): Your ExternalSecrets
     already use `apiVersion: external-secrets.io/v1` (confirmed), so this
     should be transparent. But the CRDs at 0.16+ start serving the v1 API and
     deprecating v1beta1 — this exercises that path.
  2. **CRD size explosion** (~0.19+): CRDs grew past 256KB due to new
     generators and providers. This is where Flux/Helm may fail if not using
     server-side apply. Better to hit this issue on 0.20 (where you can debug
     it) than on the 2.0 jump.

  Good news: your ExternalSecrets already use `apiVersion: external-secrets.io/v1`
  (confirmed in `cert-manager/cert-manager/app/externalsecret.yaml`), so the
  API migration itself is a non-event.

- **onedr0p**: Was already past 0.x when he started his 1.x→2.0 sequence. No
  direct comparison for this step.

- **Extra steps**:
  1. **Verify your current chart version**:
     ```bash
     grep -A5 "external-secrets" kubernetes/apps/external-secrets/ \
       -r --include="*.yaml" | grep -i "version\|tag"
     ```
  2. **Check CRD size handling**: Ensure your HelmRelease or Kustomization
     supports large CRDs:
     ```yaml
     spec:
       install:
         crds: CreateReplace
       upgrade:
         crds: CreateReplace
     ```
     If CRDs fail to apply, you may need to enable server-side apply in Flux
     or apply CRDs manually with `kubectl apply --server-side`.
  3. Merge PR #24.
  4. **Verify all ExternalSecrets are syncing**:
     ```bash
     kubectl get externalsecrets --all-namespaces \
       -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.conditions[0].reason
     ```
  5. **Verify bitwarden-sdk-server**:
     ```bash
     kubectl get pods -n external-secrets | grep bitwarden
     kubectl logs -n external-secrets <bitwarden-sdk-server-pod>
     ```
  6. **Wait at least 24 hours** to confirm all secrets are refreshing on
     schedule before proceeding to Step 2.

#### Step 2: #86 — External Secrets 0.20.4 → 2.0.1
- **Risk**: Medium (from a stable 0.20 baseline)
- **Rating rationale**: With 0.20.4 stable and CRD handling validated, the jump
  to 2.0.1 is primarily a chart version bump. The actual v2.0.0 breaking
  changes are minimal — only removed Alibaba and Device42 providers (which you
  don't use). The major version number reflects the project's graduation to
  stable, not a rewrite.

- **onedr0p**: Jumped from chart 1.3.2 to 2.0.0 (#10463, Feb 6). Merged
  cleanly, touching only `bootstrap/helmfile.d/01-apps.yaml` and the
  OCIRepository.

- **Extra steps**:
  1. **Update bootstrap if needed**: Check if `bootstrap/helmfile.d/01-apps.yaml`
     references external-secrets and needs a version bump.
  2. Merge PR #86.
  3. Verify same checklist as Step 1 (ExternalSecrets syncing, bitwarden pods).
  4. Clean up: PR #24 is now merged and irrelevant.
