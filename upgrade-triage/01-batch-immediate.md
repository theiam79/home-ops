# Batch 1 — Immediate (no prep needed)

Merge these directly. All are patches or low-risk minors with no breaking changes.

---

## #110 — kube-prometheus-stack 82.4.1 -> 82.4.3

- **Risk:** Negligible
- **Rationale:** Patch bump within the 82.x line. No config changes.
- **Reference repo:** onedr0p merged all 82.x patches without issue, auto-merging aggressively through the entire 82.0.0-82.4.3 range with zero reverts.
- **Extra steps:** None.

---

## #109 — reflector 10.0.13 -> 10.0.14

- **Risk:** Negligible
- **Rationale:** Patch bump. Reflector is a simple secret/configmap mirror.
- **Reference repo:** No comparison available (removed from their cluster years ago).
- **Extra steps:** None.

---

## #108 — booklore v2.0.2 -> v2.0.5

- **Risk:** Negligible
- **Rationale:** Patch bump within the 2.0.x line.
- **Reference repo:** No comparison available (not used).
- **Extra steps:** None.

---

## #114 — prowlarr-develop 1.31.2.4975 -> 1.32.2.4987

- **Risk:** Low
- **Rationale:** Minor bump. Prowlarr develop builds are frequent and generally stable. No breaking changes expected within the 1.x line.
- **Reference repo:** onedr0p uses a different image (`ghcr.io/home-operations/prowlarr`) and is already on 2.x. No direct comparison, but their 1.x-to-2.x jump had zero reverts.
- **Extra steps:** None.

---

## #113 — shelfmark v1.0.2 -> v1.1.2

- **Risk:** Low
- **Rationale:** Minor bump. Shelfmark is a relatively simple app.
- **Reference repo:** No comparison available (not used).
- **Extra steps:** None.
