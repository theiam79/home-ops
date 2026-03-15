# Batch 1 — Immediate (no prep)

Patches and low-risk minors. Merge in any order.

---

## #178 — authelia 4.39.15 → 4.39.16

- **Risk:** Negligible
- **Rating rationale:** Patch bump, bugfix only.
- **Reference repo:** onedr0p does not use Authelia.
- **Extra steps:** None.

---

## #167 — reflector 10.0.16 → 10.0.20

- **Risk:** Negligible
- **Rating rationale:** Patch bump within same minor.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #127 — reloader 2.2.8 → 2.2.9

- **Risk:** Negligible
- **Rating rationale:** Patch bump.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #176 — recyclarr 8.4.0 → 8.5.0

- **Risk:** Negligible
- **Rating rationale:** Minor bump, application-level only. No cluster impact.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #175 — opentelemetry-collector 0.146.1 → 0.147.0

- **Risk:** Low
- **Rating rationale:** Minor bump. OTel collector releases frequently with incremental changes.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #174 — loki 6.53.0 → 6.55.0

- **Risk:** Low
- **Rating rationale:** Minor bump within same major. Grafana Loki helm chart.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #171 — cloudflared 2026.2.0 → 2026.3.0

- **Risk:** Low
- **Rating rationale:** Monthly release. CVE fixes (GO-2026-4394), management token improvements. `proxy-dns` deprecation messaging enhanced but not breaking for tunnel usage.
- **Reference repo:** No comparison available.
- **Extra steps:** None.

---

## #170 — flux-operator 0.43.0 → 0.44.0

- **Risk:** Low
- **Rating rationale:** No breaking changes. Adds cosign verification, updated go-sdk.
- **Reference repo:** onedr0p takes these frequently without issues. Note: they added anonymous auth config (#10561) around this time — verify if relevant to your setup.
- **Extra steps:** None.

---

## #137 — external-secrets 2.0.1 → 2.1.0

- **Risk:** Low
- **Rating rationale:** No breaking changes documented. Adds cross-namespace push support, new Nebius provider.
- **Reference repo:** onedr0p upgraded 1.3.2 → 2.0.0 cleanly (#10463). The 2.0 breaking changes only removed Alibaba and Device42 providers (irrelevant). 2.0.1 → 2.1.0 is a safe minor.
- **Extra steps:** None.

---

## #169 — envoy-gateway v1.7.0 → v1.7.1

- **Risk:** Low
- **Rating rationale:** Patch with meaningful bugfixes: envoy proxy updated to 1.37.1, cross-namespace route validation fix, BackendTrafficPolicy reference fix, active health check hostname fix.
- **Reference repo:** onedr0p merged 1.7.0 → 1.7.1 (#10628) cleanly on Mar 12.
- **Extra steps:** None.
