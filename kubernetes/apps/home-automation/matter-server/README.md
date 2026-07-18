# matter-server

[matterjs-server](https://github.com/matter-js/matterjs-server) — the Open
Home Foundation Matter controller for Home Assistant, successor to
[python-matter-server](https://github.com/home-assistant-libs/python-matter-server)
(8.1.2 was that project's final release; this is the matter.js rewrite with a
compatible WebSocket API). HA runs as Core in a container (no Supervisor), so
the "official Matter Server add-on" path doesn't exist here; this deployment
is its replacement. HA connects via the Matter integration with the add-on
checkbox **unchecked** and the URL
`ws://matter-server.home-automation.svc.cluster.local:5580/ws`.

The Thread radio side is the SMLIGHT SM Hub Nano (`smhub.internal`) running
OpenThread Border Router on the IoT VLAN; HA talks to it separately via the
OTBR integration (`tcp://smhub.internal:8081`).

## Why the multus `iot` attachment (net1 = 10.1.30.6)

Matter-over-Thread requires the controller to share an L2 domain with the
border router, for two link-local mechanisms that never cross VLANs:

1. **mDNS** — the OTBR advertises itself (`_meshcop._udp`) and proxies Thread
   devices' Matter service records onto the infrastructure link.
2. **IPv6 Router Advertisements** — the OTBR announces the route into the
   Thread mesh (its OMR prefix) as an RA Route Information Option. Without
   that route, commissioning hands off to Thread and then times out.

The pod therefore attaches to the existing `iot`
NetworkAttachmentDefinition (ipvlan L2 on `mgmt0.30`, owned by the
home-assistant app — hence the `dependsOn` in `ks.yaml`) with the static IP
`10.1.30.6/24`, right next to HA's `10.1.30.5`. Both sit outside the dnsmasq
DHCP pool (.10–.254) because CNI static IPAM is not a DHCP client.
`PRIMARY_INTERFACE=net1` points the SDK at the IoT-VLAN interface (the image
is configured entirely through env vars; `STORAGE_PATH=/data` is its default).

## The sysctl initContainer

Linux **ignores RA Route Information Options by default**
(`accept_ra_rt_info_max_plen=0`), so the privileged initContainer sets, on
`net1` only:

- `net.ipv6.conf.net1.accept_ra=2` — accept RAs regardless of forwarding state
- `net.ipv6.conf.net1.accept_ra_rt_info_max_plen=64` — install RIO routes up
  to /64 (the Thread OMR prefix length)

These are netns-scoped (they don't touch the node), but they're not on
kubelet's safe-sysctl list, so a privileged init is simpler than an
allowed-unsafe-sysctls kubelet change on all nodes. Verify after rollout:

```sh
kubectl -n home-automation exec deploy/matter-server -- ip -6 route show dev net1
# expect: fd..::/64 via fe80::... proto ra
```

## Storage

`/data` holds the **Matter fabric credentials** — losing it means
re-commissioning every Matter device. It's a volsync-backed PVC (1Gi,
ceph-block) so it rides the normal kopia backup schedule. The image bakes in
`USER 1000:1000`, matching the pod securityContext/fsGroup.

## No route / no auth

The websocket API and dashboard on 5580 are unauthenticated by design (the
add-on relies on the Supervisor network for isolation). ClusterIP only —
never expose it via HTTPRoute. Reach the dashboard with a port-forward when
needed.

## Version note

matterjs-server is beta (not yet CSA re-certified) but is the only maintained
line — upstream declared python-matter-server end-of-life and its 8.1.1/8.1.2
releases never even shipped container images. Drop-in WS-API replacement,
supports Matter 1.4.2.
