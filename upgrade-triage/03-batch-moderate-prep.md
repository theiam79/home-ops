# Batch 3: Moderate Prep — Config Changes and Testing Required

These PRs require meaningful changes to Helm values, resource limits, or
application config before merging. Each should be validated after deploy.

## PRs in this batch (5)

### #61 — Minecraft chart 4.26.3 → 5.1.1
- **Risk**: Medium-Low
- **Rating rationale**: Major chart version with template naming changes
  (`nameOverride`/`fullnameOverride` behavior). Your servers likely don't set
  these overrides, but the StatefulSet/Service names could change, which would
  orphan existing PVCs.
- **onedr0p**: N/A (not in his stack).
- **Extra steps**:
  1. Before merging, verify your minecraft HelmRelease values for
     `nameOverride` and `fullnameOverride`. If unset, the defaults may change
     resource names.
  2. Check current resource names:
     ```bash
     kubectl get statefulset,svc,pvc -n <minecraft-namespace>
     ```
  3. After merge, verify PVCs are still bound and the server comes up with
     world data intact.
  4. If names changed, you may need to manually update PVC references or
     create the new StatefulSet before deleting the old one.

### #65 — k8s-sidecar 1.30.3 → 2.5.0
- **Risk**: Medium-High
- **Rating rationale**: k8s-sidecar v2 rewrote internals with significantly
  higher memory usage (~135% increase, from ~80MB to 189MB+). This is confirmed
  in upstream issues. Your Gatus init container uses a 128Mi memory limit which
  **will OOM** on v2. Additionally, v2 adds a health server on port 8080 and
  changes some environment variable names.
- **onedr0p**: Not in his stack (uses `gatus-sidecar`, a different tool).
- **Extra steps before merge**:
  1. Find all containers using the k8s-sidecar image:
     ```bash
     grep -r "k8s-sidecar" kubernetes/ --include="*.yaml" -l
     ```
  2. Increase memory limits from 128Mi to at least 256Mi (recommend 300Mi for
     headroom) on every container using this image.
  3. Check for `readOnlyRootFilesystem: true` in security contexts — the new
     health server may need write access to `/tmp`.
  4. After merge, monitor pod memory usage for 24h:
     ```bash
     kubectl top pods -l <sidecar-label> --all-namespaces
     ```
  5. If any pods OOM, increase limits further. The v2 memory footprint scales
     with the number of watched resources.

### #36 — Loki chart 6.30.1 → 6.53.0
- **Risk**: Medium-High
- **Rating rationale**: Loki chart 6.38 introduced a breaking change where
  `singleBinary.persistence.accessModes` became null by default, causing
  StatefulSet patch failures. This is a known issue in the community. Without
  the fix, the upgrade will hang as Flux cannot reconcile the StatefulSet.
- **onedr0p**: Uses VictoriaLogs instead — no comparison available.
- **Extra steps before merge**:
  1. Add to your Loki HelmRelease values:
     ```yaml
     singleBinary:
       persistence:
         accessModes:
           - ReadWriteOnce
     ```
     (or whatever access mode you currently use — check your existing
     StatefulSet with `kubectl get sts -n <loki-ns> -o yaml | grep accessModes`)
  2. This is a 23-minor-version jump. Review the Loki Helm chart changelog for
     any config deprecations between 6.30 and 6.53. Key areas:
     - Storage schema version changes
     - `structuredConfig` vs flat values
     - Memberlist/ring configuration
  3. After merge, verify log ingestion and querying still work. Check Grafana
     Explore with a simple LogQL query.

### #9 then #55 — Grafana chart 9.2.2 → 9.4.5 → 10.5.15 (two-step sequence)

This is a sequenced upgrade. Merge #9 first, verify, then merge #55.

#### Step 1: #9 — Grafana chart 9.2.2 → 9.4.5
- **Risk**: Low
- **Rating rationale**: Minor bump within the same chart major. Same Grafana
  application version (12.1.1). No Angular changes, no plugin compatibility
  issues. This is a safe checkpoint that validates your Flux pipeline handles
  Grafana chart upgrades correctly.
- **Extra steps**: None. Merge and verify Grafana comes up and dashboards load.
  If anything breaks here, it's a chart config issue you want to fix before
  attempting the Angular-breaking 10.x jump.
- **Wait**: Verify stability for at least a few hours before proceeding to #55.

#### Step 2: #55 — Grafana chart 9.4.5 → 10.5.15
- **Risk**: Medium-High
- **Rating rationale**: Two major issues:
  1. **Angular plugin removal**: Grafana fully removed Angular support. The
     `natel-discrete-panel` and `vonage-status-panel` plugins are Angular-based
     and **will not load** on Grafana 12.x (which chart 10.x ships). The
     `GF_SECURITY_ANGULAR_SUPPORT_ENABLED` environment variable is also removed.
  2. **Chart deprecation**: The `grafana/helm-charts/grafana` chart repo was
     deprecated in January 2026. The chart moved to
     `grafana-community/helm-charts`. This doesn't block the upgrade but means
     future updates will come from a different source.
- **onedr0p**: Uses grafana-operator (chart 5.22.0) instead — completely
  different deployment model. No comparison available.
- **Extra steps before merge**:
  1. Identify and remove/replace Angular plugins:
     ```bash
     grep -r "natel-discrete-panel\|vonage-status-panel\|angular" \
       kubernetes/ --include="*.yaml"
     ```
     Replace with React-based alternatives:
     - `natel-discrete-panel` → `marcusolsson-dynamictext-panel` or native
       State Timeline panel
     - `vonage-status-panel` → `grafana-polystat-panel` or native Stat panel
  2. Remove `GF_SECURITY_ANGULAR_SUPPORT_ENABLED` from environment variables.
  3. Review all dashboards for Angular panel types. Any dashboard using removed
     panels will show "Panel plugin not found" errors.
  4. Plan the OCI source migration to `grafana-community/helm-charts` for
     future updates.
  5. After merge, walk through each Grafana dashboard to verify panels render.

### #69 — Helm CLI 3.20.0 → 4.1.1 (mise tool)
- **Risk**: Medium (local tooling only)
- **Rating rationale**: Only affects the local `helm` binary in `.mise.toml`.
  Does NOT affect Flux-managed HelmReleases in the cluster (Flux has its own
  Helm library). However, Helm 4 changes defaults: server-side apply (SSA) is
  the new default, `helm install` behavior changed for existing releases, and
  some CLI flags were removed. If you use `helm` or `helmfile` for bootstrap
  operations, this matters.
- **onedr0p**: Not visible in his PRs — likely still on Helm 3. Helm 3 is
  supported until November 2026, so there's no urgency.
- **Extra steps before merge**:
  1. Test your bootstrap helmfile with Helm 4:
     ```bash
     cd bootstrap && helmfile diff
     ```
  2. Check if any bootstrap scripts use removed Helm 3 flags.
  3. If bootstrap breaks, keep Helm 3 for now — there's no urgency.
  4. Consider running Helm 3 and 4 side-by-side during transition by pinning
     the version per-task rather than globally.
