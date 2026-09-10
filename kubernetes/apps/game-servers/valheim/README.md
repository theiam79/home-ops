# valheim

Friends-only Valheim 1.0 dedicated server. Image is
[mbround18/valheim](https://github.com/mbround18/valheim-docker) (Odin): rootless,
updates itself from Steam, and turns mods on with an env change. Research and
option comparison (hosting, exposure, mods) lives in the 2026-09-09 decision
brief; this README is the operating doc.

## Exposure

| What | Where |
|---|---|
| LoadBalancer | `192.168.100.38` (claimed in `kube-system/cilium/README.md`), UDP 2456 game, 2457 Steam query, 2458 RPC |
| Public name | `valheim.<domain>` CNAME → `ipv4.<domain>` (unproxied; Cloudflare tunnel cannot carry UDP) |
| LAN name | same hostname, A record → `.38` via opnsense-dns (hairpin NAT does not work on this WAN, so LAN clients need this) |
| **OPNsense (manual)** | DNAT **UDP 2456-2458 → 192.168.100.38**. Re-enable the old Valheim forward and retarget it to `.38`. Consider a GeoIP block above it and `max-src-states` on the rule; pf's connection-rate limits are TCP-only. |
| Status API | `valheim-status.game-servers.svc:3000` (Huginn: `/status`, `/players`, `/metrics`, `/connect/remote`). In-cluster only. |

The server runs `-public 0`: hidden from the community browser, reachable by
direct connect only. Friends need no software beyond Steam.

**Join instructions for friends:** in Valheim → Join Game → Join IP →
`valheim.<domain>:2456`, or open this link with Steam running:

```
steam://run/892970//+connect%20valheim.<domain>:2456
```

`PUBLIC=0` has a cost worth knowing: Valheim only answers Steam A2S queries on
2457 when public, and Odin uses A2S for player counts. So with `PUBLIC=0`,
Huginn `/players` and `/readiness` report offline, `PLAYER_EVENT_NOTIFICATIONS`
never fire, and `AUTO_UPDATE_PAUSE_WITH_PLAYERS` cannot see anyone. Flipping to
`PUBLIC=1` (password still required) restores all of that at the price of being
listed in the in-game browser.

## Storage

| Mount | Claim | Backed up | Holds |
|---|---|---|---|
| `/home/steam/.config/unity3d/IronGate/Valheim` | `valheim` (VolSync, `saves/` subPath) | VolSync every 12 h | `worlds_local/<World>/` (1.0 chunked save dir), `adminlist.txt`, `bannedlist.txt`, `permittedlist.txt` |
| `/home/steam/backups` | `valheim` (`backups/` subPath) | VolSync | Odin zip taken before every Steam update (`AUTO_BACKUP_ON_UPDATE`), pruned after 7 days |
| `/home/steam/valheim` | `valheim-server-files` (plain 5Gi) | no | SteamCMD download, `config.json`, `discord.json`, BepInEx if enabled |
| `/tmp`, `~/.steam`, `~/.local` | emptyDir | no | SteamCMD scratch |

A world save is a **directory** in 1.0. Copying a world in or out means the whole
`worlds_local/<World>/` tree, not a `.db`/`.fwl` pair. Pre-1.0 saves convert
one-way on first load.

Shutdown is graceful: the start script traps SIGTERM and runs `odin stop`, which
saves the world. `terminationGracePeriodSeconds` is 120 to give it room.

## Secrets

`valheim-secret` comes from Bitwarden Secrets Manager with two keys. Create
both items and paste their ids into `app/externalsecret.yaml`:

```sh
bws secret create VALHEIM_PASSWORD '<password>' <project-id>
bws secret create VALHEIM_DISCORD_WEBHOOK 'https://discord.com/api/webhooks/...' <project-id>
```

Password rules: at least 5 characters and it must not be contained in the server
or world name, or the server refuses to start.

The webhook feeds Odin's own notifications: **Start**, **Stop** and **Update**
events, each posted as Running / Successful / Failed, straight from the
container. These do not depend on `PUBLIC`. Optional extras:
`PLAYER_EVENT_NOTIFICATIONS=1` adds join/leave (needs `PUBLIC=1`, see above);
`WEBHOOK_SUPPRESS_NOTIFICATIONS=1` posts silently; `WEBHOOK_JOIN_URL` adds a
Join button but must be an HTTPS redirect (Huginn `/connect/remote` behind envoy
would do). To go without Discord, drop the `WEBHOOK_URL` key from the
ExternalSecret; Odin skips notifications when it is unset.

## First boot

1. Create the bws secrets and set their ids (above). Check `NAME` and `WORLD`
   in `app/helmrelease.yaml` first: the world name is baked into the save
   directory and the seed is generated on first start.
2. Merge. Flux creates the PVCs, the pod downloads the server (~1 GB) on
   first start, then generates the world. Expect a few minutes.
3. Re-enable the OPNsense forward and point it at `.38`.
4. Add yourself as admin: `V_<SteamID64>` on its own line in `adminlist.txt`
   (1.0 changed the format; bare SteamID64 entries are silently ignored).
   Restart the pod. Do **not** populate `permittedlist.txt` unless you want a
   whitelist, because a non-empty list blocks everyone not on it.
5. Test the join link from a friend's network, not just LAN.

## World tuning (presets and modifiers)

All of these are launch arguments applied every time the server starts, so they
can be changed later by editing env and letting the pod restart. Odin reads
`PRESET`, `MODIFIERS` and `SET_KEY`. A preset resets every modifier, so set the
preset first and then override individual modifiers.

```yaml
PRESET: normal                      # casual | easy | normal | hard | hardcore | immersive | hammer
MODIFIERS: deathpenalty=casual,portals=casual,raids=less
SET_KEY: playerevents               # one of nobuildcost | playerevents | passivemobs | nomap
```

Presets, roughly:

| Preset | Feel |
|---|---|
| normal | stock game |
| casual | very easy combat, no death penalty, 1.5x resources, no raids, all items through portals, passive enemies |
| easy | easier combat, gentle death penalty, more resources, fewer raids |
| hard | harder combat, harsher death, restricted portals, more raids |
| hardcore | very hard combat, death deletes items and skills, no map, no portals |
| immersive | normal combat/resources, no map, no portals |
| hammer | building sandbox: free build, passive enemies, lots of resources |

Individual modifiers:

| Modifier | Values (default in the middle) | What it changes |
|---|---|---|
| combat | veryeasy, easy, **normal**, hard, veryhard | enemy and player damage, enemy speed/size, enemy level-up rate |
| deathpenalty | casual, veryeasy, easy, **normal**, hard, hardcore | casual keeps gear and loses ~1% skills; normal drops gear at a gravestone with 5% skill loss; hardcore destroys all items and resets skills |
| resources | muchless (0.5x), less (0.75x), **normal**, more (1.5x), muchmore (2x), most (3x) | drop rates for most resources (not fish) |
| raids | none, muchless, less, **normal**, more, muchmore | base raid frequency |
| portals | casual, **normal**, hard, veryhard | casual lets metal through; normal blocks metal; hard blocks all items; veryhard removes portals |
| setkey | nobuildcost, playerevents, passivemobs, nomap | free building; raids scale to players present rather than global progress; enemies ignore you until attacked; no minimap |

For a first friends run, `deathpenalty=casual` or `easy` and `portals=casual`
are the two most-requested QoL changes and both are vanilla, no mods needed.

## Mods later

Vanilla today. To add mods (all Steam players must install the same set with
r2modman or Gale; share a profile export):

```yaml
TYPE: BepInEx
MODS: |
  ValheimModding-Jotunn-2.30.0
  Advize-PlantEverything-1.20.0
```

Odin downloads them from Thunderstore on start (`MODS_CONTINUE_ON_FAILURE=true`
keeps the server up if one is missing). Setting `TYPE` back to `Vanilla` removes
the loader; the world keeps working minus anything a removed mod placed.
Thunderstore marks server-only mods, which need nothing on clients. Mods that
use the RPC port need 2458 forwarded, which the forward above already covers.
Crossplay (`ENABLE_CROSSPLAY=1`) is off by design: it is only needed for console
or Game Pass players and pairs badly with mods.

## Gotchas

- **Stuck on "state is 0x6 after update job"**: stale SteamCMD manifest. Odin
  retries once automatically (`STEAMCMD_RESET_ON_FAILURE`); if it loops, delete
  `steamapps/` on the `valheim-server-files` PVC and restart.
- **Admin commands say "not admin"**: adminlist entry lacks the `V_` prefix.
- **`externalTrafficPolicy` must stay `Cluster`**: Cilium L2 announcements
  blackhole with `Local` (see the unifi README). Client source IPs are SNATed,
  which is fine because Valheim bans by platform id, not IP.
- No liveness/readiness probes: the only in-container health signal is A2S,
  which `PUBLIC=0` disables. The statefulset restarts on crash regardless.
