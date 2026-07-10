---
name: upgrade-triage
description: Triage open Renovate/dependency PRs by risk, cross-reference against a reference repo, and work through them in-session — merging, closing, or filing hold issues
argument-hint: "[reference-repo]"
---

# Upgrade Triage

Assess all open dependency-update PRs, research upgrade risks, optionally
cross-reference against a reference repository's merge history, then **work
through every PR in this session** — merging the safe ones, closing the
superseded ones, and filing a GitHub issue for anything postponed or held.

There are **no batch documents and no scratch files**. The risk analysis lives
in the conversation; the durable record is the set of merged PRs, closed PRs,
and `upgrade-hold` GitHub issues this run produces. Nothing is left dangling in
a tmp directory or committed to the repo.

## Arguments

- **reference-repo** (optional): A GitHub `owner/repo` to cross-reference
  against (e.g., `onedr0p/home-ops`). When provided, search that repo's merged
  and open PRs for the same components to identify real-world issues, reverts,
  and supporting chore commits. If omitted, skip the cross-reference phase.

## Phase 0: Check existing holds

Before triaging anything new, list the holds from prior runs so you can update,
close, or unblock them instead of re-deriving the same context:

```
gh issue list --label upgrade-hold --state open \
  --json number,title,body --limit 100
```

For each existing hold, check whether its unblock criteria are now met (the
upstream fix shipped, the maintenance window arrived, the blocking PR merged).
If so, fold it back into this run's worklist and close the issue when done.

## Phase 1: Inventory

1. List all open PRs:
   ```
   gh pr list --state open --limit 100 \
     --json number,title,author,headRefName,additions,deletions,labels
   ```
2. For each PR, extract:
   - Component name and current → target version
   - Whether the bump is patch, minor, or major (use semver, the `type/*`
     labels, and the `!` convention in commit titles)
   - Whether another open PR targets the same component at a higher version
     (marks the lower one as **superseded**)
3. Group superseded PRs. For each pair, decide whether the superseded PR is a
   useful **intermediate step** (see criteria below) or should just be closed.

### Intermediate step criteria

A superseded PR is a useful intermediate step if ALL of:
- The target PR spans 2+ major versions
- The superseded PR lands on a version that is a documented upgrade boundary
  (e.g., CRD schema changes, API version migrations, deprecation removals)
- Merging incrementally reduces the blast radius of each individual step

If it qualifies, keep it and sequence it before the target PR. If not, close it.

## Phase 2: Risk Research

For each unique component upgrade (skip superseded-only PRs), research risks
using web search and GitHub. Prioritize major bumps and infrastructure-critical
components (CNI, storage, OS, k8s).

Use parallel Task agents (subagent_type: `general-purpose`) to research batches
of 5-8 components simultaneously. Each agent should search for:

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
3. Find **chore/manual commits** around the merge date (prep work, fixups)
4. Note the **upgrade path** taken (incremental vs. direct jump)
5. Note anything they have **not yet done** or have **open/stalled**

Key signals:
- **Reverts** = confirmed problems. Note what broke and whether it was resolved.
- **Chore commits** near the merge = extra manual work was needed.
- **Incremental path** = they considered the direct jump too risky; match it.
- **Not yet merged** = they may be waiting for a fix. Check for open issues.

## Phase 4: Risk-order the worklist

Sort the PRs into risk tiers — this is an **in-memory ordering** to drive the
work-through, not a set of documents. Work the tiers from safest to riskiest so
the easy wins land first and the risky ones get full attention.

For each PR, hold in mind:
- **Risk rating** (Negligible / Low / Low-Medium / Medium / Medium-High / High / Critical)
- **Rationale**: the specific breaking change, CRD concern, or behavioral change
- **Reference-repo signal** (if cross-referenced): what they did, reverts, chores
- **Extra steps**: exact commands / config edits needed before or after merge

Tiers, safest first:

1. **Immediate** — patches, clean minors, cosmetic majors, CI actions with no
   API change. Merge directly.
2. **Light prep** — small values tweak, SHA verification, community PR needing
   manual review, a new default to override.
3. **Moderate prep** — major bumps with known config migration, plugin
   replacement, sequenced upgrade where Step 2 needs prep.
4. **Heavy prep** — multi-step sequences spanning 2+ majors, bootstrap CRD
   updates before a chart upgrade, paths the reference repo took incrementally.
5. **Critical infrastructure** — CNI (Cilium), storage (Rook Ceph), OS/kernel
   (Talos), k8s version bumps, anything with open regressions. Maintenance
   window only.

## Phase 5: Work through every PR in session

Go tier by tier, safest first. For **each** PR take exactly one terminal action
this session — never leave it in limbo:

- **Merge** — when it's safe (or safe after a documented small step). Do any
  required prep first (values edit, SHA pin), then merge. State what you did.
- **Close** — superseded PRs that aren't useful intermediates; obsolete or
  rejected upgrades. Say why in the close comment.
- **Hold / postpone → file an issue** — anything that can't merge now: needs a
  maintenance window, blocked on an upstream fix, awaiting prep work, or a
  sequenced upgrade waiting on Step 1. File a GitHub issue (below) so the
  reasoning and the unblock condition survive the session, then leave the PR
  open (Renovate will keep it fresh) or close it if the issue fully supersedes
  it — state which and why.

Keep the user in the loop: announce each tier, and for any merge that mutates
cluster state or any close, confirm intent before acting unless the user has
said to proceed autonomously. Patches and clean minors can be merged in a batch
with a summary rather than one-by-one prompts — but pace the batch per the
rollout-safety rules below.

### Merge pacing & rollout safety

Do **not** fire every approved merge at once. Mass-simultaneous merges make
Flux restart many pods in the same window, which storms RWO/RBD volume
detach-attach. On a cluster with any flaky storage, a single slow or crashing
Ceph mon during that storm is enough to blow Helm's 5-minute upgrade timeout —
producing failed upgrades *and* failed rollbacks across the fleet. (Observed:
batch-merging an `app-template` major alongside ~36 other PRs tipped over a
known-recurring ceph-mon crash; data stayed safe but a dozen HelmReleases timed
out.) Pace it:

1. **Isolate fleet-wide / shared-dependency upgrades — merge each ALONE.** Any
   PR that re-renders many apps at once is the single biggest blast radius:
   - a shared library chart (e.g. bjw-s `app-template` / `common`)
   - an `OCIRepository`/`HelmRepository` tag referenced by many HelmReleases
   - CNI (Cilium), CSI / storage drivers, cert-manager, external-secrets
   Merge it by itself, then wait for Flux to fully reconcile and pods to settle
   (and storage to stay healthy) **before** merging anything else. Never stack
   other merges on top of one of these.
2. **Merge the rest in waves, not all at once.** Group safe patches/minors into
   modest batches (~8–12). Spread stateful / persistent-volume apps across
   waves so you don't restart many RBD-backed pods simultaneously.
3. **Health-gate between waves.** Before the next wave confirm: all HelmReleases
   Ready (`flux get hr -A`), no pods stuck `Terminating`/`ContainerCreating`/
   `Pending`, and storage healthy (`ceph status` → `HEALTH_OK`, PGs
   `active+clean`). If not, stop and let it recover (or remediate) first — a
   stalled wave is a pacing problem to settle, **not** a reason to file a hold.

### Filing a hold issue

For every postponed/held PR (or coupled group), `gh issue create` with body:

- PR number(s) being held and current → target versions
- **Risk rating and rationale** — the concrete reason it's held
- **The blocker** — upstream issue, required prep, maintenance window, missing
  CRDs, etc., with links
- **Change criteria** — the explicit condition(s) that let us proceed, written
  so a future run can check them mechanically (e.g. "upstream issue #1234
  closed", "Rook 1.20.2 released", "next maintenance window")
- Any cross-reference signals (reverts, chore commits, incremental path)
- Sequenced upgrades: spell out Step 1 / Step 2 with the wait condition

Label issues `upgrade-hold` (create the label if it doesn't exist) so the next
run's Phase 0 finds them. If a hold issue already exists for the component,
update it instead of opening a duplicate.

## Phase 6: Wrap up

End with a short summary of what happened this session:
- Merged (count + notable ones)
- Closed (with reason)
- Held (PR → issue number → change criteria, one line each)

That summary plus the GitHub state is the entire record — no files to clean up.

## Notes

- When components are tightly coupled (Talos + kubelet, Rook operator +
  cluster), handle them together and, if held, file **one** issue for the group.
- If the reference repo uses a different tool for the same purpose (e.g.,
  grafana-operator vs grafana chart), note "no comparison available" rather than
  forcing a comparison.
- The repo is never the persistence layer for triage state — merged/closed PRs
  and `upgrade-hold` issues are. Do not create triage branches, docs, or
  scratch files.
