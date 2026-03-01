# Batch 2 — Light Prep (minor config or verification)

These need a small action before or after merge, but are straightforward.

---

## #5 — kube-rbac-proxy v0.14.1 -> v0.16.0 [URGENT]

- **Risk:** Low (version bump itself) / **High urgency** (dead registry)
- **Rationale:** The version bump is minor and safe. The **real urgency** is that `gcr.io/kubebuilder/kube-rbac-proxy` is dead — GCR stopped serving this image after March 2025. Your pods only work because the image is cached on nodes. Any node replacement, drain, or image eviction will cause a pull failure and the bitwarden-sm operator will not start.
- **Reference repo:** No comparison available (not used standalone).
- **Extra steps:**
  1. Change the image registry in `kubernetes/apps/bitwarden-sm/bitwarden-sm/app/helm/values.yaml`:
     ```yaml
     # FROM:
     gcr.io/kubebuilder/kube-rbac-proxy:v0.14.1
     # TO:
     quay.io/brancz/kube-rbac-proxy:v0.16.0
     ```
  2. Verify bitwarden-sm pods restart successfully:
     ```
     kubectl rollout status deployment -n bitwarden-sm -l app.kubernetes.io/name=bitwarden-sm
     ```

---

## #111 — flux-operator 0.42.1 -> 0.43.0

- **Risk:** Low
- **Rationale:** Minor version bump of the flux-operator. Follows semver, no breaking API changes expected. Controls the entire Flux installation, so verify before applying.
- **Reference repo:** onedr0p merged 0.42.1 -> 0.43.0 on 2026-02-27 with no reverts. **However**, the preceding 0.42.1 upgrade required an immediate companion commit to "add anon auth to flux operator." Check if your FluxInstance config needs a similar change.
- **Extra steps:**
  1. Check if your FluxInstance needs an `anonAuth` configuration. Review onedr0p's chore commit for details:
     ```
     gh pr view 10561 --repo onedr0p/home-ops --json body,files
     ```
  2. After merge, verify Flux is healthy:
     ```
     flux check
     kubectl get fluxinstance -A
     ```

---

## #112 — audiobookshelf 2.19.5 -> 2.32.1

- **Risk:** Low-Medium
- **Rationale:** Large minor version jump (13 minors). The major change is a **new JWT authentication system in v2.26.0** — all users must re-login after upgrade. Mobile app clients also need re-authentication. Database migrations run automatically on startup.
- **Reference repo:** No comparison available (removed from their cluster in 2023).
- **Extra steps:**
  1. Snapshot the config PVC before upgrading (trigger a VolSync snapshot or manual backup).
  2. **Notify all users** they will need to re-login (web and mobile apps) after the upgrade.
  3. After merge, verify the pod starts and database migrations complete:
     ```
     kubectl logs -n media -l app.kubernetes.io/name=audiobookshelf --tail=50
     ```
  4. Confirm the web UI loads and login works at `audiobookshelf.${SECRET_DOMAIN}`.
