---
name: upgrade-triage
description: Triage open Renovate/dependency PRs by risk, cross-reference against a reference repo, then either work through them in-session (merge/close/hold) or, with --report, publish a read-only risk dashboard for review
argument-hint: "[--report] [reference-repo|none]"
---

# Upgrade Triage

Assess all open dependency-update PRs, research upgrade risks, cross-reference
against a reference repository's merge history, then finish in one of two modes:

- **Interactive mode** (default): **work through every PR in this session** —
  merging the safe ones, closing the superseded ones, and filing a GitHub issue
  for anything postponed or held.
- **Report mode** (`--report`): stop after the assessment and **publish it as a
  dashboard** for human review. Strictly read-only against GitHub.

There are **no batch documents and no scratch files**. The risk analysis lives
in the conversation; the durable record is GitHub state (merged/closed PRs and
`upgrade-hold` issues) in interactive mode, or the published dashboard artifact
in report mode. Nothing is left dangling in a tmp directory or committed to the
repo.

## Arguments

- **`--report`** (optional flag): run in report mode.
- **reference-repo** (optional): A GitHub `owner/repo` to cross-reference
  against. **Defaults to `onedr0p/home-ops`.** Pass `none` to skip the
  cross-reference phase. When provided, search that repo's merged and open PRs
  for the same components to identify real-world issues, reverts, and
  supporting chore commits.

## Report mode ground rules

Report mode performs **no writes to GitHub**: no merging, no closing, no
comments, no labels, no issue creation or edits. Allowed actions are `gh`
reads, web research, and publishing the dashboard artifact. Every PR still
receives exactly one terminal **recommendation** — the difference from
interactive mode is that recommendations are published for review, not
executed. Phases 0–4 run with the report-mode notes inline below; Phases 5–6
are replaced by Phase 5R.

## Phase 0: Check existing holds

Before triaging anything new, list the holds from prior runs so you can update,
close, or unblock them instead of re-deriving the same context:

```
gh issue list --label upgrade-hold --state open \
  --json number,title,body --limit 100
```

For each existing hold, check whether its unblock criteria are now met (the
upstream fix shipped, the maintenance window arrived, the blocking PR merged).

- **Interactive mode:** if criteria are met, fold the hold back into this run's
  worklist and close the issue when done.
- **Report mode:** do **not** close or edit any issue. Record a status for each
  hold instead — `ready` (criteria appear met; cite the evidence, e.g. the
  released version or closed upstream issue) or `blocked` (name which
  criterion still fails). Ready holds are surfaced prominently on the
  dashboard so the reviewer sees what can be actioned.

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
   In report mode, nothing is closed here — a non-intermediate superseded PR
   gets the recommendation `close-superseded`.

### Intermediate step criteria

A superseded PR is a useful intermediate step if ALL of:
- The target PR spans 2+ major versions
- The superseded PR lands on a version that is a documented upgrade boundary
  (e.g., CRD schema changes, API version migrations, deprecation removals)
- Merging incrementally reduces the blast radius of each individual step

If it qualifies, keep it and sequence it before the target PR. If not, close it
(interactive) or recommend closing it (report).

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

## Phase 3: Cross-Reference (unless reference repo is `none`)

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
work-through (interactive) or the dashboard sections (report), not a set of
documents. Work the tiers from safest to riskiest so the easy wins land first
and the risky ones get full attention.

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

## Phase 5 (interactive mode): Work through every PR in session

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
with a summary rather than one-by-one prompts.

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

## Phase 6 (interactive mode): Wrap up

End with a short summary of what happened this session:
- Merged (count + notable ones)
- Closed (with reason)
- Held (PR → issue number → change criteria, one line each)

That summary plus the GitHub state is the entire record — no files to clean up.

## Phase 5R (report mode): Publish the dashboard

1. **Assemble the report** as a single JSON object matching the schema below.
   This is the rendering contract, not a deliverable — build it in memory (or
   a job tmp dir), never in the repo.
2. **Render the dashboard** by filling the marked data regions of
   `dashboard-template.html` in this skill's directory. Replace **only** the
   content between `data:*` marker comment pairs; the tokens, CSS, structure,
   `<title>`, and chip/tier mappings (documented in the template's contract
   comment) stay identical run-to-run so the dashboard reads the same every
   week.
3. **Publish as an artifact.** First call `Artifact` with `action: "list"` and
   look for an existing artifact titled **"Upgrade Triage — home-ops"**; if
   found, republish with `url` set to it so the URL stays stable. Otherwise
   publish new with favicon `🧭` and a one-line description. Keep title and
   favicon identical across runs.
4. **Fallback:** if artifact publishing is unavailable or fails, emit the full
   report as markdown tables in the final message instead — never end a report
   run without its output somewhere reviewable.
5. **Summarize:** end with PR counts per tier, the list of `ready` holds, the
   top three recommended actions, and the dashboard link.

### Report schema

```json
{
  "generated": "<ISO 8601 UTC>",
  "repo": "<owner/repo>",
  "reference_repo": "<owner/repo, or null if skipped>",
  "prs": [
    {
      "number": 519,
      "component": "musicseerr",
      "current": "1.8.2",
      "target": "2.0.0",
      "bump": "major",
      "tier": 4,
      "risk": "Medium-High",
      "recommendation": "hold",
      "rationale": "One or two sentences: the concrete breaking change or concern.",
      "reference_signal": "What the reference repo did, or null.",
      "prep_steps": ["exact command or config edit, if any"],
      "superseded_by": null,
      "coupled_with": [],
      "hold_issue": 519
    }
  ],
  "holds": [
    {
      "issue": 368,
      "title": "Hold: talos 1.13.6",
      "components": ["talos"],
      "prs": [368],
      "blocker": "Why it is held, one line.",
      "criteria": "The mechanical unblock condition from the issue body.",
      "status": "ready",
      "evidence": "Why it is ready (or which criterion still fails)."
    }
  ]
}
```

Field constraints:
- `bump`: `patch` | `minor` | `major` | `digest` | `other`
- `tier`: 1–5 per Phase 4
- `risk`: Negligible | Low | Low-Medium | Medium | Medium-High | High | Critical
- `recommendation`: `merge` | `merge-after-prep` | `close-superseded` | `hold`
  (file/keep an upgrade-hold issue) | `needs-window` (safe but maintenance
  window only)
- Every open dependency PR appears exactly once in `prs`. `holds` includes
  every open `upgrade-hold` issue, whether or not a PR is currently open for
  it.

## Notes

- When components are tightly coupled (Talos + kubelet, Rook operator +
  cluster), handle them together and, if held, file **one** issue for the group
  (interactive) or mark them `coupled_with` each other (report).
- If the reference repo uses a different tool for the same purpose (e.g.,
  grafana-operator vs grafana chart), note "no comparison available" rather than
  forcing a comparison.
- The repo is never the persistence layer for triage state — merged/closed PRs
  and `upgrade-hold` issues are. Do not create triage branches, docs, or
  scratch files.
- The weekly scheduled routine invokes `/upgrade-triage --report`. An
  interactive run may use the latest dashboard as its starting worklist, but
  must re-verify live PR/issue state before acting on it.
