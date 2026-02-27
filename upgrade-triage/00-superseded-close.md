# Batch 0: Superseded PRs — Close Without Merging

These PRs target older versions of the same component where a newer PR exists.
They are NOT useful as intermediate stepping stones (those have been moved into
their respective upgrade sequences in Batches 3 and 4).

| PR | Title | Superseded By | Batch |
|----|-------|---------------|-------|
| #2 | Reflector 9.1.7 → 9.1.45 | #81 (→ 10.0.12) | Batch 1 |
| #10 | kube-prometheus-stack 73.2.2 → 73.2.3 | #79 → #89 sequence | Batch 4 |
| #28 | k8s-sidecar 1.30.3 → 1.30.11 | #65 (→ 2.5.0) | Batch 3 |
| #33 | Minecraft chart 4.26.3 → 4.26.4 | #61 (→ 5.1.1) | Batch 2 |
| #38 | Snapshot Controller 4.0.2 → 4.2.0 | #78 (→ 5.0.3) | Batch 2 |

## Rescued as intermediate steps (moved to upgrade sequences)

These were originally in this list but have been moved into their target batch
as a required first step in a multi-major-version upgrade:

| PR | Role | Sequence | Batch |
|----|------|----------|-------|
| #9 | Grafana 9.4.5 — checkpoint before Angular-breaking 10.x | #9 → #55 | Batch 3 |
| #79 | kube-prometheus-stack 81.6.9 — bridge 73→81 before 81→82 | #79 → #89 | Batch 4 |
| #24 | External Secrets 0.20.4 — stabilize on latest 0.x before 2.0 jump | #24 → #86 | Batch 4 |

## Why close the remaining five?

- **#2 (Reflector 9.1.45)**: v10.0.0 is a cosmetic major bump with zero code
  changes. No gap to bridge — skip straight to #81.
- **#10 (kps 73.2.3)**: Patch on current major. Doesn't bridge any version gap.
  The meaningful intermediate is #79 (81.6.9), not a patch on 73.x.
- **#28 (k8s-sidecar 1.30.11)**: Patch on current major. The v1→v2 breaking
  changes (memory, health server) aren't mitigated by being on a newer 1.x patch.
- **#33 (Minecraft 4.26.4)**: Patch on current major. The v4→v5 template naming
  changes aren't mitigated by a 4.x patch.
- **#38 (Snapshot Controller 4.2.0)**: Minor within 4.x. onedr0p merged 4.2→5.0
  cleanly, and this intermediate adds no safety.
