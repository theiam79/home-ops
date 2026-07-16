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
