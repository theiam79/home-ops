# elli GPU + local LLM (Home Assistant voice) — runbook

Goal: bring elli's RTX 3080 10GB online under Talos/K8s, serve a local LLM via
Ollama, and run an automated, reproducible A/B (**Gemma 4 E4B** vs **Qwen3 8B**)
for Home Assistant Assist tool-calling — *before* wiring real voice or rebuilding
HA. Whisper/Piper (voice) is deferred; the eval below does not need them.

The 3080 is already physically installed and powered in elli, so this is a config
change, not a hardware change.

## What this branch adds

| Change | File |
|---|---|
| elli gets an NVIDIA-enabled install image + loads the nvidia kernel modules + `nvidia.com/gpu.present` label | `talos/nodes/elli.yaml.j2` |
| Documents elli's 4-extension factory schematic | `talos/schematic.yaml.j2` |
| NVIDIA device plugin (RuntimeClass + time-slicing + HelmRelease) | `kubernetes/apps/kube-system/nvidia-device-plugin/` |
| Ollama (GPU, app-template) | `kubernetes/apps/home-automation/ollama/` |
| Wires both into their namespace kustomizations | `.../kube-system/kustomization.yaml`, `.../home-automation/kustomization.yaml` |

---

## Phase 1 — Bring the GPU online (Talos)

Run from a machine with Bitwarden Secrets access (`bws`), since `task talos:*`
needs the templated secret env. **Driver/extension installs require a node
upgrade + reboot.**

1. **Build the schematic.** At <https://factory.talos.dev>, for the current
   `talos/talenv.yaml` Talos version (amd64 / metal), select these FOUR extensions:
   - `siderolabs/i915`
   - `siderolabs/intel-ucode`
   - `siderolabs/nvidia-open-gpu-kernel-modules-production`  ← open modules are correct for Ampere
   - `siderolabs/nvidia-container-toolkit-production`

   Copy the returned **schematic ID**.

2. **Paste the ID** into `talos/nodes/elli.yaml.j2` →
   `machine.install.image` (replace `REPLACE_WITH_ELLI_SCHEMATIC_ID`).

3. **Upgrade elli to the NVIDIA image** (installs the extensions, reboots):
   ```bash
   bws run -- task talos:upgrade-node IP=192.168.100.30
   ```
   The task pulls the install image straight from elli's rendered config, so it
   uses the new schematic automatically.

4. **Apply the machine config** (loads the kernel modules + the GPU node label):
   ```bash
   bws run -- task talos:apply-node IP=192.168.100.30
   ```

5. **Verify the driver loaded:**
   ```bash
   talosctl -n 192.168.100.30 get extensions          # both nvidia extensions listed
   talosctl -n 192.168.100.30 read /proc/driver/nvidia/version
   talosctl -n 192.168.100.30 read /proc/modules | grep nvidia
   ```

> Ordering matters: upgrade (gets the extension image) **then** apply (loads the
> modules). Loading `nvidia` modules before the extension image is present fails.

---

## Phase 2 — Expose the GPU to Kubernetes (Flux)

This is pure GitOps — no Talos secrets. Merge/push this branch, then Flux
reconciles. node-feature-discovery already whitelists PCI class `03`, so it will
label elli `feature.node.kubernetes.io/pci-10de.present=true`, which the device
plugin's default affinity targets.

```bash
flux reconcile kustomization cluster-apps --with-source   # or wait for the interval
kubectl -n kube-system get ds nvidia-device-plugin
```

**Verify the node advertises the GPU** (time-slicing → 4):
```bash
kubectl get node elli -o jsonpath='{.status.allocatable.nvidia\.com/gpu}{"\n"}'   # -> 4
```

**Smoke-test with nvidia-smi:**
```bash
kubectl run nvidia-smi --rm -it --restart=Never \
  --image=nvidia/cuda:12.6.0-base-ubuntu22.04 \
  --overrides='{"spec":{"runtimeClassName":"nvidia","containers":[{"name":"nvidia-smi","image":"nvidia/cuda:12.6.0-base-ubuntu22.04","command":["nvidia-smi"],"resources":{"limits":{"nvidia.com/gpu":1}}}]}}'
```
You should see the RTX 3080 in the table.

> **If the GPU is not visible to pods (Talos v1.13 CDI gotcha):** the most likely
> cause is the CDI hook path. Uncomment the `postRenderers` block in
> `nvidia-device-plugin/helmrelease.yaml` (it points the hook at
> `/usr/local/bin/nvidia-cdi-hook`, where Talos puts extension binaries), confirm
> the container name matches, and `flux reconcile hr nvidia-device-plugin -n kube-system`.

---

## Phase 3 — Pull the models

Ollama lives at `home-automation/ollama` (Service `ollama:11434`).

```bash
kubectl -n home-automation exec deploy/ollama -- ollama pull gemma4:e4b
kubectl -n home-automation exec deploy/ollama -- ollama pull qwen3:8b
kubectl -n home-automation exec deploy/ollama -- ollama list
```

> Confirm exact tags against the Ollama registry — QAT variants may be tagged e.g.
> `gemma4:e4b-it-qat`. Prefer the QAT int4 build for the 3080. Both models +
> headroom fit the 10GB; `OLLAMA_KEEP_ALIVE=-1` keeps the active one resident.

---

## Phase 4 — Raw performance gate (~15 min, near-free)

```bash
# generation tok/s + prompt-eval (TTFT proxy)
kubectl -n home-automation exec -it deploy/ollama -- ollama run --verbose qwen3:8b "Say hi in one word."
kubectl -n home-automation exec -it deploy/ollama -- ollama run --verbose gemma4:e4b "Say hi in one word."
# confirm 100% GPU residency (any CPU spill tanks throughput)
kubectl -n home-automation exec deploy/ollama -- ollama ps
```
Want comfortably >20–30 tok/s and `100% GPU`. E4B should be faster (smaller) —
a real tie-breaker if accuracy is close.

---

## Phase 5 — HA-specific eval — THE DECIDER (~1–2 hrs)

`allenporter/home-assistant-datasets` is purpose-built for HA Assist tool-calling
and produces the leaderboard the HA blog cites. It spins up a *synthetic* HA, so
it does **not** need your real (still-being-rebuilt) HA instance.

Published leaderboard for reference (E4B is **not** on it — that's the number this
run fills in): `qwen3-8b` 82.8% assist / 93.4% assist-mini.

```bash
# On your workstation, reach in-cluster Ollama:
kubectl -n home-automation port-forward svc/ollama 11434:11434 &

pip install home-assistant-datasets        # or clone + pip install -e .

# models/qwen3-8b.yaml  (repeat for gemma4-e4b):
#   model_id: qwen3-8b
#   domain: ollama
#   config_entry_data:
#     url: http://localhost:11434
#     model: qwen3:8b
#   config_entry_options:
#     llm_hass_api: assist

for M in qwen3-8b gemma4-e4b; do
  pytest home_assistant_datasets/tool/assist/collect \
    --models=$M --dataset=datasets/assist/ --model_output_dir=reports/assist/local
done
pytest home_assistant_datasets/tool/assist/eval --model_output_dir=reports/assist/local
# repeat both steps with --dataset=datasets/assist-mini/
```

Decision criteria:
- **assist-mini ≥ ~93% and assist ≥ ~80%** keeps you in the leaderboard band.
  Well below the published Qwen3-8B numbers ⇒ suspect a quant or chat-template
  problem, not the model.
- **Read the per-task wins/losses**, not just the %. For HA, *consistent correct
  entity targeting and zero hallucinated tool calls* matter more than a point or
  two — a model that occasionally actuates the wrong device is worse than its score.
- Use the native-Ollama path (above). Do **not** route tool-calling through
  Ollama's `/v1` OpenAI shim — it's the documented-unreliable path and would
  unfairly penalize whichever model goes through it.

Pick the winner; keep the other as a configured fallback (no hardware cost — both
fit alongside Whisper later).

---

## Phase 6 — Live replay on your real home (DEFERRED until HA is rebuilt)

Synthetic homes can't test your real entity aliases/areas. Once HA is back:
configure both models as conversation agents and loop ~20–30 of *your* commands
through `conversation.process` per `agent_id`, diffing responses + resulting
entity state. Threshold: zero wrong-device actions on your top commands.

---

## Next phase (post-decision) — voice stack

Not needed for the eval. When wiring real voice:
- `wyoming-whisper-gpu` (STT, GPU — stock `rhasspy/wyoming-whisper` is CPU-only;
  use a GPU build) + `wyoming-piper` (TTS, CPU). Both co-schedule on the 3080 via
  the time-slicing slots already configured here.
- HA Assist: Ollama conversation agent, expose <25 entities, enable "Prefer
  handling commands locally".
- Meal-planning automation is a *separate*, cloud-LLM workflow (Mealie + weekly
  plan) and does not use this GPU.

## Troubleshooting quick hits

- **Pod stuck `CreateContainerError` / no GPU** → Talos v1.13 CDI hook path; see
  the postRenderer note in `nvidia-device-plugin/helmrelease.yaml`.
- **`nvidia.com/gpu` is 0** → NFD hasn't labeled elli (driver not loaded — recheck
  Phase 1 verify) or the device-plugin DaemonSet isn't scheduled.
- **Ollama CPU-only / slow** → `ollama ps` not `100% GPU`; model too big for free
  VRAM, or `runtimeClassName: nvidia` not applied.
- **Schematic/driver mismatch after a Talos upgrade** → rebuild the schematic at
  factory.talos.dev for the new Talos version and re-run Phase 1.
