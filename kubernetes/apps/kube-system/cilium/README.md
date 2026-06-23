# cilium

Primary CNI (kube-proxy replacement, native routing, Multus-compatible via
`cni.exclusive: false`).

## `bpf.vlanBypass` — required for Multus VLAN secondary networks

Cilium's `bpf_host` program drops **all** 802.1Q-tagged frames on the native
NIC by default, logged as `VLAN traffic disallowed by VLAN filter`
(`bpf_host.c`). This silently breaks any Multus secondary network attached to a
tagged VLAN sub-interface (`ipvlan`/`macvlan` on `mgmt0.<id>`): the pod gets its
IP on `net1`, but every frame it sends is dropped at the host before reaching
the wire — no ARP, no ping, nothing. It affects all CNI modes and is independent
of NIC driver.

`vlanBypass` allowlists VLAN IDs past that filter (`[0]` would bypass all).
Current list:

- **30** — IoT VLAN (`10.1.30.0/24`); Home Assistant ↔ Google Cast speakers.
- **70** — VPN-egress VLAN; qbittorrent/slskd multus migration.

Add a VLAN ID here whenever a new Multus tagged-VLAN attachment is introduced.

### Diagnosing

If a Multus VLAN pod can't reach its gateway, confirm before touching the switch
or NICs — the host path usually works while the pod path doesn't:

```sh
# on the node's cilium agent:
cilium-dbg monitor --type drop      # look for "VLAN traffic disallowed by VLAN filter"
```

Note: a host-netns test (adding an IP directly to `mgmt0.<id>` and pinging) will
**succeed** even when this filter is blocking pods — only an actual pod on the
secondary network exercises the dropped path.
