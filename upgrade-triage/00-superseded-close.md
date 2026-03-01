# Superseded PRs

## Close

### #116 — mariadb 11.7.2 -> 11.8.6 (superseded by #117: 11.7.2 -> 12.2.2)

**Verdict: Close** — not a useful intermediate step.

MariaDB 11.8 is within the same major version as 11.7 and is not a documented upgrade boundary for the 11-to-12 migration. MariaDB officially supports direct upgrades from any earlier version to the latest, so stepping through 11.8 provides no meaningful risk reduction. The rolling release model in 12.x means 11.8 will itself go EOL quickly.

If you prefer extra caution, you could merge #116 first as a low-risk warm-up, but it is not required and adds unnecessary churn.
