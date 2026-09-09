# rook-ceph

Three HelmReleases: `app/` (Rook operator), `csi-drivers/` (ceph-csi-operator
chart; driver images come from the operator-generated
`rook-csi-operator-image-set-configmap`), `cluster/` (CephCluster + pools +
StorageClasses + toolbox).

## CephX key types (aes → aes256k)

Ceph 19.2.6+/20.2.4+ ships the `aes256k` key cipher (CVE-2025-30156). Until
every key uses it, Ceph reports three standing warnings:

| Warning | Cleared by |
|---|---|
| `AUTH_INSECURE_CLIENT_KEY_TYPE` | every client key rotated to aes256k (CSI ×4, rbd-mirror-peer) |
| `AUTH_INSECURE_KEYS_ALLOWED` | `auth_allowed_ciphers` restricted to aes256k (Rook `allowedCiphers`) |
| `AUTH_INSECURE_KEYS_CREATABLE` | same as above |

Daemon keys (mon/mgr/osd/admin/...) were rotated in PR #665. CSI keys stayed
`aes` because kernel RBD mounts with aes256k need kernel support — Talos
v1.13.10 backported it into 6.18.48 and Rook 1.20.7 brought the required CSI
3.17.1, so the remaining steps are:

### Step 1 — rotate CSI + rbd-mirror-peer keys to aes256k (DONE 2026-09-09, PR #749)

`cluster/helmrelease.yaml` → `cephClusterSpec.security.cephx.csi`:
`keyRotationPolicy: KeyGeneration`, `keyGeneration: 2`,
`keepPriorKeyCountMax: 1`, `keyType: aes256k` (same for `rbdMirrorPeer`,
minus the prior-key count — the pool has no mirroring peers).

- Rotated keys apply to **new mounts only**; the prior aes key stays active so
  running PVCs are untouched. No daemon restarts, no HEALTH_ERR window.
- Watch: `kubectl -n rook-ceph get cephcluster rook-ceph -o jsonpath='{.status.cephx.csi}'`
  → `keyGeneration: 2`, `keyType: aes256k`, `priorKeyCount: 1`.
- Immediately smoke-test a fresh PVC mount on an OSD node **and** a non-OSD
  node (elli / dvergar-04 / dvergar-06) before the next VolSync wave
  (`0 */12 * * *` UTC) — every mover pod mounts a fresh clone with the new key.
  If a mount fails (`EPERM`/`permission denied` from the kernel client), revert
  with `keyType: aes`, `keyGeneration: 3`, `keepPriorKeyCountMax: 2`.

### Step 2 — rehydrate mounts (DONE 2026-09-09, PR #751)

Existing PVCs keep the old aes key until remounted. Cordon + drain + uncordon
each node (a Talos roll does this for free), then set
`keepPriorKeyCountMax: 0` to drop the old key.

**Trap:** a plain `rollout restart` is NOT enough when the new pod lands on
the same node — the kubelet keeps the RBD device staged and the new pod
inherits the old-key mapping. Force a node change (cordon → restart →
uncordon) or scale to 0 and wait for the VolumeAttachment to disappear.
Verify per node via `/sys/bus/rbd/devices/*/client_id` against
`ceph tell mon.<x> sessions` (`entity_name`), not via pod age. Old-identity
sessions that remain with no matching kernel client id are the hostNetwork
CSI plugins' pooled librados connections — harmless, flushed by restarting
the plugin pods.

Verify nothing still reports `aes`:

```
ceph auth dump-keys --format=json-pretty | grep -c '"aes"'   # want 0
```

### Step 3 — restrict allowed ciphers (mon tighten) (DONE 2026-09-09, PR #752)

Only after Step 2 shows zero `aes` keys anywhere (daemons included):

```yaml
security:
  cephx:
    allowedCiphers: [aes256k]
```

This sets the mon-map `auth_allowed_ciphers` and clears the last two warnings.
Rook's docs flag it as able to take the cluster down if any daemon key is
still aes — the recovery is `allowedCiphers: [aes, aes256k]` +
`daemon.keyType: aes` temporarily (see Rook "Allowed Ciphers").

Reference: Rook `Documentation/Storage-Configuration/Advanced/cephx-key-rotation.md`
(v1.20.7), Ceph `rados/operations/health-checks` AUTH_INSECURE_*.
