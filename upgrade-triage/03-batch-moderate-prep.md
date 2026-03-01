# Batch 3 — Moderate Prep (config changes and testing)

These require configuration changes, backups, or pre-merge testing.

---

## #117 — MariaDB 11.7.2 -> 12.2.2 (MAJOR)

- **Risk:** Medium-High
- **Rationale:** Major version bump with a new rolling release model. MariaDB 12.x removes the query cache entirely and several deprecated system variables. The Docker container will refuse to start without `MARIADB_AUTO_UPGRADE=1`. Currently backs Booklore only, limiting blast radius.
- **Reference repo:** No comparison available (onedr0p does not use MariaDB).
- **Extra steps:**
  1. **Backup the database** before upgrading:
     ```
     kubectl exec -n media deploy/mariadb -- mariadb-dump --all-databases > mariadb-backup-$(date +%Y%m%d).sql
     ```
     Also snapshot the PVC via VolSync or manual PVC snapshot.
  2. **Add `MARIADB_AUTO_UPGRADE: "1"`** to the MariaDB container env in `kubernetes/apps/media/mariadb/app/helmrelease.yaml`. Without this, the container exits immediately on version mismatch.
  3. Verify no custom `my.cnf` references removed variables (`query_cache_size`, `query_cache_type`, `big_tables`, `large_page_size`, `storage_engine`). Current helmrelease does not pass a custom config, so this is likely fine.
  4. After merge, verify MariaDB starts and `mariadb-upgrade` runs successfully:
     ```
     kubectl logs -n media -l app.kubernetes.io/name=mariadb --tail=50
     ```
  5. Verify Booklore can connect and read data:
     ```
     kubectl logs -n media -l app.kubernetes.io/name=booklore --tail=20
     ```
  6. **Note:** MariaDB 12.x uses a rolling release model — expect more frequent minor bumps (12.2 -> 12.3 -> ...) going forward.

### Superseded PR: #116 (mariadb 11.7.2 -> 11.8.6)

Not required as an intermediate step. Close #116 after merging #117. See `00-superseded-close.md`.

---

## #69 — Helm 3.20.0 -> 4.1.1 (MAJOR, local CLI tool)

- **Risk:** Low-Medium
- **Rationale:** Major version bump of the local Helm CLI managed via mise. Flux uses its own embedded Helm SDK, so in-cluster reconciliation is NOT affected. The blast radius is limited to manual `helm` commands and the `helmfile` bootstrap workflow. Key changes: Server-Side Apply by default, CLI flag renames (`--atomic` -> `--rollback-on-failure`), post-renderers require plugins.
- **Reference repo:** **onedr0p has deliberately rejected Helm 4 — they closed 6 consecutive Renovate PRs** for this upgrade between November 2025 and February 2026, staying on Helm 3.19.x. This is a strong signal to wait.
- **Extra steps:**
  1. **Consider deferring this upgrade** given the onedr0p signal.
  2. If proceeding, test bootstrap scripts first:
     ```
     cd bootstrap/helmfile.d && helmfile --environment default template
     ```
  3. Check helmfile compatibility with Helm 4 SDK.
  4. Audit any scripts or Taskfile targets for removed/renamed flags.
  5. Update `.mise.toml` line 19 from `3.20.0` to `4.1.1`.
