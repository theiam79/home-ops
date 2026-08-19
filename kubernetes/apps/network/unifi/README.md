# unifi

UniFi Network Application ([linuxserver/unifi-network-application](https://github.com/linuxserver/docker-unifi-network-application)) — replaces the legacy `linuxserver/unifi-controller` container that ran on snotra (deprecated upstream January 2024, frozen at Network ~7.5).

## Design

- **Two containers, one pod**: the Network application plus MongoDB 8.0 (required external DB for this image). Mongo binds `127.0.0.1` only — it is unreachable outside the pod, so the credentials are belt-and-suspenders rather than a real security boundary.
- **`init-mongo.sh`** (ConfigMap) is run by the mongo image entrypoint only when `/data/db` is empty; it creates the `unifi` DB user with `dbOwner` on `unifi`, `unifi_stat`, `unifi_audit`, `unifi_restore` (the set Network 10.x expects). If you ever need to re-run it, scale to 0 and delete the `unifi-mongo-data` PVC contents.
- **Backups**: `/config` is VolSync-backed (`unifi` PVC). The mongo PVC (`unifi-mongo-data`) is deliberately **not** VolSync'd — file-copying a live mongod is inconsistent by construction. Instead, enable UniFi's own scheduled autobackups (Settings → System → Backups, nightly): the `.unf` files land in `/config/data/backup/autobackup/`, which VolSync does protect. DR = fresh install + restore latest `.unf` (mongo rebuilds itself from it).
- **Access**: UI at `https://unifi.${SECRET_DOMAIN}:8443` (opnsense-dns publishes the hostname → LB IP `192.168.100.37`; self-signed cert). Not routed through envoy — the gateway's `Backend` API (needed for backend TLS skip-verify) isn't enabled, and the inform/STUN ports need the raw LB anyway.
- `externalTrafficPolicy` is Cluster (default), not Local: Cilium's L2-announcement leader election doesn't follow backend placement, so Local blackholes the LB IP whenever the lease-holder node isn't running the pod (hit on first deploy: lease on dvergar-02, pod on elli). Device source IPs get SNAT'd to a node IP, which is cosmetic — device identity comes from the inform payload.
- Java heap is capped via `MEM_LIMIT` (env, megabytes) — not a cgroup limit.

Why not UniFi OS Server (Ubiquiti's recommended self-host path since March 2026): it requires a systemd host with Podman — no Docker/Kubernetes support — so it can't run in the cluster and would need a dedicated VM on snotra. The standalone Network app is in maintenance mode but still receives releases; the UniFi-OS-only features (Site Magic, Teleport, Identity) are gateway-centric and irrelevant behind OPNsense. Revisit if Ubiquiti EOLs the standalone app.

## Migration from the legacy controller (one-time)

1. On the old controller (snotra): Settings → System → Backups → **Download backup** (`.unf`, include history). Also note the current version — backups are forward-compatible only, and 7.x → 10.x restore is supported.
2. Create the `unifi-mongo-pass` secret in Bitwarden Secrets Manager, put its UUID in `app/externalsecret.yaml`, merge, let Flux deploy.
3. Open `https://192.168.100.37:8443` → setup wizard → **restore from backup** → upload the `.unf`. Wait for the restart (can take several minutes on restore).
4. In Settings → System → Advanced, set **Inform Host** to `192.168.100.37` and tick *Override inform host*.
5. Re-point each device: `ssh <device>` (creds from the restored controller's device auth, Settings → System → Advanced) and run `set-inform http://192.168.100.37:8080/inform`. Adopted devices reappear as *provisioning* → *connected*. L2 discovery (10001/udp) only helps for devices on the same VLAN as the LB IP.
6. Enable nightly autobackups (see above).
7. Verify all devices reconnect and stats flow, then stop and remove the old `unifi-controller` container on snotra.
