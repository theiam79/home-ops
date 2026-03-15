# Batch 3 — Moderate Prep (config changes and testing)

---

## #177 — cert-manager v1.19.4 → v1.20.0

- **Risk:** Medium
- **Rating rationale:** Minor bump with notable breaking changes:
  1. **Container UID/GID changed** from 1000/0 to 65532/65532. If PodSecurityPolicies, SecurityContextConstraints, or filesystem permissions reference UID 1000, they will break.
  2. **`DefaultPrivateKeyRotationPolicyAlways`** promoted to GA — can no longer be disabled.
  3. **API defaults reverted**: Issuer reference kind/group defaults introduced in v1.19.0 were reverted. Certificates may renew unexpectedly if you relied on the new defaults.
- **Reference repo:** onedr0p merged v1.20.0 (#10621) cleanly on Mar 11. They went through the full 1.19.x series incrementally first. Only 2 files changed.
- **Extra steps:**
  1. Check for security policies referencing cert-manager UID 1000:
     ```bash
     grep -r "1000" kubernetes/apps/ --include="*.yaml" | grep -i cert-manager
     ```
  2. Review cert-manager HelmRelease for any explicit securityContext overrides.
  3. Back up cert-manager resources:
     ```bash
     kubectl get certificates,issuers,clusterissuers -A -o yaml > cert-manager-backup.yaml
     ```
  4. After merge, verify certificates are still valid:
     ```bash
     kubectl get certificates -A
     cmctl status certificate <name> -n <ns>
     ```

---

## #133 — NATS chart 1.3.16 → 2.12.5, image 2.11.3 → 2.12.5

- **Risk:** Medium
- **Rating rationale:** **Helm chart major version bump** (1.x → 2.x) plus container image minor bump. Your config is simple (no cluster, no JetStream — just pub/sub for hermod), which limits blast radius. Key concerns:
  1. **Helm chart 2.x** may have restructured values. Current values (`config.cluster.enabled`, `config.jetstream.enabled`, `container.image`, `container.merge.resources`, `reloader.merge.resources`) need validation against the new chart schema.
  2. **Strict mode** enabled by default in NATS 2.12 — invalid requests that were previously logged now return errors.
  3. **Insecure cipher suites** disabled by default (irrelevant if using unencrypted in-cluster connections).
  4. **Downgrade caveat**: If rollback needed, must go to v2.11.9+ (not current 2.11.3) due to stream state format changes.
- **Reference repo:** No comparison available (onedr0p does not use NATS).
- **Extra steps:**
  1. Compare current Helm values against the chart 2.x `values.yaml`:
     ```bash
     helm show values oci://ghcr.io/nats-io/helm-charts/nats --version 2.12.5 > /tmp/nats-new-values.yaml
     ```
  2. Validate your values map to the new schema — particularly `container.image` and `container.merge.resources`.
  3. After merge, verify hermod connectivity:
     ```bash
     kubectl logs -n hermod deploy/hermod-api | grep -i nats
     kubectl logs -n hermod deploy/hermod-bot | grep -i nats
     ```
  4. If rollback needed, bump image to 2.11.9-alpine (not 2.11.3) and chart to a compatible 1.x version.

---

## #123 — mariadb 11.8.6 → 12.2.2

- **Risk:** Medium-High
- **Rating rationale:** **Real major version bump.** MariaDB 12.x is the new rolling release model. Breaking changes:
  1. **Query cache fully removed** — any reference to `query_cache_size`, `query_cache_type` will cause startup errors.
  2. **Deprecated system variables removed** — `big_tables`, `large_page_size`, others.
  3. **Requires `MARIADB_AUTO_UPGRADE=1`** env var for the entrypoint to run `mariadb-upgrade` on first start. Without this, internal system tables won't be updated.
  4. On-disk data format is compatible for in-place upgrade from 11.8.
- **Reference repo:** onedr0p does not use MariaDB (no comparison).
- **Extra steps:**
  1. **Backup first** — take a VolSync snapshot or manual dump:
     ```bash
     kubectl exec -n media deploy/mariadb -- mariadb-dump -u root -p<password> --all-databases > mariadb-backup.sql
     ```
  2. Add `MARIADB_AUTO_UPGRADE: "1"` to the mariadb HelmRelease env section before bumping the tag.
  3. Review any custom MariaDB config for deprecated variables:
     ```bash
     grep -r "query_cache\|big_tables\|large_page_size" kubernetes/apps/media/mariadb/
     ```
  4. Merge the PR (with the env var addition).
  5. Verify Booklore connects successfully:
     ```bash
     kubectl logs -n media deploy/booklore | grep -i database
     ```
