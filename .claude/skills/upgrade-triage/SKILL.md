---
name: upgrade-triage
description: Triage open Renovate/dependency PRs by risk, cross-reference against a reference repo, and produce batched upgrade documents
argument-hint: "[reference-repo]"
---

# Upgrade Triage

Assess all open dependency-update PRs, research upgrade risks, cross-reference
against a reference repository's merge history, and produce a prioritized set
of batch documents for **same-session triage**.

Batch documents are scratch artifacts written to a tmp directory — they are
**not committed to the repo**. Anything that needs to outlive the session
(holds, multi-step upgrade plans, blocked work) gets filed as a GitHub issue.

## Arguments

- **reference-repo** (optional): A GitHub `owner/repo` to cross-reference
  against (e.g., `onedr0p/home-ops`). When provided, search that repo's merged
  and open PRs for the same components to identify real-world issues, reverts,
  and supporting chore commits. If omitted, skip the cross-reference phase.

## Phase 1: Inventory

1. List all open PRs:
   ```
   gh pr list --state open --limit 100 \
     --json number,title,author,headRefName,additions,deletions
   ```
2. For each PR, extract:
   - Component name and current → target version
   - Whether the version bump is patch, minor, or major (use semver and the
     `!` convention in commit titles)
   - Whether another open PR targets the same component at a higher version
     (marks the lower one as **superseded**)
3. Group superseded PRs. For each pair, determine whether the superseded PR is
   a useful **intermediate step** (see criteria below).

### Intermediate step criteria

A superseded PR is a useful intermediate step if ALL of:
- The target PR spans 2+ major versions
- The superseded PR lands on a version that is a documented upgrade boundary
  (e.g., CRD schema changes, API version migrations, deprecation removals)
- Merging incrementally reduces the blast radius of each individual step

If it qualifies, keep it and sequence it before the target PR in the same batch.
If not, mark it for closing.

## Phase 2: Risk Research

For each unique component upgrade (skip superseded-only PRs), research risks
using web search and GitHub API. Prioritize major version bumps and
infrastructure-critical components (CNI, storage, OS, k8s).

Use parallel Task agents (subagent_type: `general-purpose`) to research
batches of 5-8 components simultaneously. Each agent should search for:

1. **Breaking changes**: Official migration guides, upgrade notes, changelogs
2. **Known issues**: GitHub issues filed against the target version
3. **Required manual steps**: CRD updates, bootstrap changes, config migrations
4. **User-reported problems**: Community reports of failed upgrades

Focus research effort proportionally to risk:
- **Patches**: No research needed
- **Minors**: Quick search for release notes
- **Majors**: Thorough search including GitHub issues, migration guides
- **Infrastructure** (CNI, storage, OS): Most thorough — include issue trackers,
  community forums, and check for open regressions

## Phase 3: Cross-Reference (if reference repo provided)

Search the reference repo for matching component upgrades:

```
gh pr list --repo <reference-repo> --state all --limit 300 \
  --json number,title,state,mergedAt,headRefName
```

For each component in your PR list:
1. Find matching merged PRs (same component, similar version range)
2. Find any **reverts** (PRs with "Revert" in title referencing the component)
3. Find **chore/manual commits** around the merge date (prep work, config
   changes, fixups)
4. Note the **upgrade path** taken (incremental vs. direct jump)
5. Note anything they have **not yet done** or have **open/stalled**

Key signals to extract:
- **Reverts** = confirmed problems. Note what broke and whether it was resolved.
- **Chore commits** near the merge = extra manual work was needed. Document what.
- **Incremental path** = they considered the direct jump too risky. Match their
  sequencing.
- **Not yet merged** = they may be waiting for a fix. Check for open issues.

## Phase 4: Classify into Batches

Assign each PR to a batch based on combined risk assessment:

### Batch 1 — Immediate (no prep)
- All patches
- Minors with no breaking changes
- Cosmetic major bumps (major version with no actual code changes)
- CI/CD action updates with no API changes

### Batch 2 — Light prep (minor config or verification)
- PRs needing a small values tweak before or after merge
- PRs needing SHA verification (supply-chain-sensitive actions)
- Community PRs requiring manual code review
- Minors where a new default must be explicitly overridden

### Batch 3 — Moderate prep (config changes and testing)
- Major version bumps with known config migration
- PRs requiring plugin replacement or feature removal
- Sequenced upgrades where Step 1 is low-risk but Step 2 needs prep
- Local tooling upgrades that affect bootstrap workflows

### Batch 4 — Heavy prep (CRD/bootstrap changes, coordinated upgrades)
- Multi-step sequenced upgrades spanning 2+ major versions
- PRs requiring bootstrap CRD updates before the chart upgrade
- Upgrades where the reference repo took an incremental path

### Batch 5 — Critical infrastructure (maintenance window)
- CNI upgrades (Cilium, Calico, etc.)
- Storage layer upgrades (Rook Ceph, OpenEBS, etc.) requiring version stepping
- OS/kernel upgrades (Talos, Flatcar, etc.)
- Kubernetes version upgrades coupled with OS upgrades
- Anything with open regressions — mark as HOLD with rationale

## Phase 5: Write Scratch Batch Documents

Write batch documents to a session-scoped tmp directory — **never** inside the
repo working tree:

```
/tmp/upgrade-triage-$(date +%Y%m%d-%H%M%S)/
  00-superseded-close.md
  01-batch-immediate.md
  02-batch-light-prep.md
  03-batch-moderate-prep.md
  04-batch-heavy-prep.md
  05-batch-critical-infrastructure.md
```

Tell the user the tmp path so they can open the files alongside the
conversation. These are scratch artifacts for **this session only**.

Each batch document must include for every PR:

- **PR number and title** with version range
- **Risk rating** (Negligible / Low / Low-Medium / Medium / Medium-High / High / Critical)
- **Rating rationale**: Why this rating — reference specific breaking changes,
  CRD concerns, or behavioral changes
- **Reference repo status** (if cross-referenced): What they did, any reverts,
  any manual chore commits, whether their starting version differs from ours
- **Extra steps**: Exact commands or config changes needed before/after merge.
  Include `kubectl`, `grep`, and verification commands. For sequenced upgrades,
  clearly label Step 1 and Step 2 with wait periods between them.

For the superseded file (`00-superseded-close.md`):
- List PRs to close outright (not useful as intermediates)
- List PRs rescued as intermediate steps, noting which batch they moved to

## Phase 6: Triage in Session, File Issues for Holds

The batch documents drive triage **in this session**:

1. Walk the user through batches in order (immediate → critical). For each PR
   in a batch, either merge it now, close it (superseded), or defer it.
2. For anything **deferred** — HOLDs, multi-step sequences waiting on prep
   work, blocked upgrades — open a GitHub issue so the context survives the
   session. Do not leave it only in the scratch docs.

Use `gh issue create` for each held item. Include in the issue body:

- PR number(s) being held and current → target versions
- Risk rating and rationale (lift from the batch doc)
- The specific blocker (upstream issue, required prep work, maintenance
  window, missing CRDs, etc.) with links
- Concrete unblock criteria — what condition lets us proceed
- Any cross-reference repo signals (reverts, chore commits, incremental path)
- Sequenced upgrades: spell out Step 1 / Step 2 with the wait condition

Label issues `upgrade-hold` (create the label if it doesn't exist) so they're
easy to surface on the next triage run.

**Do not** commit the batch documents, create a `docs/upgrade-triage` branch,
or open a PR with the scratch files. The repo is not the persistence layer —
GitHub issues are.

## Notes

- When multiple components are tightly coupled (e.g., Talos + kubelet, Rook
  operator + cluster), group them in the same batch entry and document the
  sequencing. If deferred, file **one** issue covering the whole group.
- If the reference repo uses a different tool for the same purpose (e.g.,
  grafana-operator vs grafana chart), note "no comparison available" rather
  than forcing a comparison.
- On re-runs: before writing fresh batch docs, check existing `upgrade-hold`
  issues (`gh issue list --label upgrade-hold`) so you can cross-reference,
  update, or close them as conditions change. The scratch docs are
  point-in-time — the issues are the durable record.
