# home-assistant

Standard app-template HelmRelease (HA + code-server sidecar), dual-homed on
the internal/external gateways. The non-obvious bit is the **IoT-VLAN secondary
interface** for Google Cast.

## IoT VLAN secondary interface (Google Cast)

`networkattachment.yaml` + the `k8s.v1.cni.cncf.io/networks` pod annotation
attach a second interface (`net1 = 10.1.30.5/24`) placing the HA pod directly on
the IoT VLAN (VLAN 30, 10.1.30.0/24) where the Nest/Google Home speakers live.

Why a dedicated L2 interface instead of routing:

- **mDNS discovery is link-local multicast** — it doesn't cross VLANs, so a
  pod-networked HA never sees the speakers.
- **Cast pulls media back from HA** — Cilium SNATs pod egress to the node IP, so
  a speaker can't open the return connection to a pod. Sharing the speakers' L2
  fixes both discovery and the media-pull path.

Implementation notes:

- **ipvlan L2, not macvlan** — the cluster's Intel I219-V NICs silently drop
  macvlan TX with synthesized MACs. ipvlan reuses the parent MAC.
- **Parent `mgmt0.30`** is a tagged VLAN sub-interface defined in the Talos
  config on all 8 nodes, so no `nodeSelector` is needed.
- **No gateway in the NAD ipam** — only the connected /24 route lands on `net1`;
  the pod's default route stays on `eth0` (cluster network). HA does not reach
  the internet via VLAN 30.
- **Per-pod IP via the annotation** (`capabilities.ips`) keeps the NAD reusable.
- **`strategy: Recreate`** — the pod holds a fixed IP and an RWO config PVC, so a
  rolling second pod would fail the multus IP claim and multi-attach the volume.

### Runtime follow-up (not in manifests)

After the pod has `net1`, the speakers need HA to advertise an IP they can reach
for TTS/media. Point the Cast media base at `http://10.1.30.5:8123` (HA Cast
integration / `internal_url` as appropriate) so served media is reachable on the
VLAN 30 L2.
