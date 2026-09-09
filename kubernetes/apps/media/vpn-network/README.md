# vpn-network

`vpn-vlan70` NetworkAttachmentDefinition: a second NIC (`net1`) on VLAN 70,
where OPNsense policy-routes everything through the AirVPN WireGuard tunnel
(`wg0`). Replaces the gluetun-sidecar pattern for qbittorrent/slskd.

## How it works

- **ipvlan L2** on `mgmt0.70` — the Talos `VLANConfig` sub-interface that
  exists (unnumbered, by design) on every node; nodes themselves have no IP
  on VLAN 70 and never should (VLAN 70 egress goes through the VPN).
- **sbr** meta-plugin chained after ipvlan — converts `net1`'s routes into
  per-source-IP rules, so replies to inbound (port-forwarded) connections
  leave via `net1` instead of being dropped by cilium on `eth0`
  ("Invalid source ip").
- **static IPAM** — each pod pins its IP via the multus annotation:

  ```yaml
  k8s.v1.cni.cncf.io/networks: |
    [{ "name": "vpn-vlan70", "namespace": "media", "ips": ["192.168.70.32/24"] }]
  ```

## IP plan (192.168.70.0/24)

| IP | Use |
|---|---|
| .1 | OPNsense gateway |
| .20–.30 | RESERVED — never allocate (mirrors node last-octets on VLAN 100; see the 2026-07-16 LB-IPAM/node-IP collision incident) |
| .32 | qbittorrent |
| .33 | slskd |
| .34–.62 | future VPN workloads |

Kill-switch and inbound port-forwarding live in OPNsense (NO_WAN_EGRESS tag
mechanism; Destination NAT with `reply-to` on the wg interface). Cilium must
keep `bpf.vlanBypass: [30, 70]` for tagged VLAN traffic to pass the host
datapath.

## slskd / qbittorrent routing init container

slskd cannot bind its outbound Soulseek traffic to an address (and qbittorrent uses the same pattern), so the
`routing` init container replaces the pod's default route with `net1` and
pins every node-local network back to `eth0`. Those pinned routes are what
keep kubelet probes alive — a probe reply that leaves via the VPN VLAN never
comes back and the pod gets liveness-killed. The list must cover every
address a node might use as the *source* of host-to-pod traffic:

| Route via `eth0` | Why |
|---|---|
| `10.42.0.0/15` | pod CIDR (cilium_host, pod-to-pod) |
| `192.168.100.0/24` | management VLAN / node InternalIPs |
| `10.10.10.0/24` | Ceph VLAN (`ceph0`) — on OSD nodes the kernel picks this address as the probe source because `enp2s0` enumerates before the management NIC (first seen after the Talos v1.13.10 roll on 2026-09-09; slskd and then qbittorrent liveness-looped on every OSD node until this route was added — PRs #748, #750) |

Add a row here if a node ever gains another addressed interface.
