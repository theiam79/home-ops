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
| combat | veryeasy, easy, **normal**, hard, veryhard | player dmg / enemy dmg / enemy speed+size / star rate: veryeasy 125/50/90/100 %, easy 110/75/90/100, normal 100/100/100/100, hard 85/150/110/120, veryhard 70/200/120/140 |
| deathpenalty | casual, veryeasy, easy, **normal**, hard, hardcore | casual keeps equipped gear, drops inventory, 1% skill loss; veryeasy drops everything, 1%; easy 2.5%; normal 5%; hard 7.5% and inventory destroyed; hardcore destroys all and resets skills |
| resources | muchless (0.5x), less (0.75x), **normal**, more (1.5x), muchmore (2x), most (3x) | drop rates from mobs and lootable objects (not fish); vanilla does not scale drops with player count |
| raids | none, muchless, less, **normal**, more, muchmore | raid check interval / chance: muchless 92 min / 10 %, less 69 / 13 %, normal 46 / 20 %, more 28 / 33 %, muchmore 14 / 67 % |
| portals | casual, **normal**, hard, veryhard | casual lets everything through (not tames); normal blocks metal; hard disables portals while a boss is active; veryhard removes portals |
| setkey | nobuildcost, playerevents, passivemobs, nomap | free building; raids keyed to each player's own boss progress rather than the world's; enemies ignore you until attacked; no minimap |

Vanilla already scales enemies with the group: roughly +30 % effective health
and +4 % damage per extra player within 100 m, capped at five. Resource drops do
not scale, which is the usual argument for `resources=more` on a group server.

For a first friends run, `deathpenalty=casual` and `resources=more` are the
two most common group picks; `combat=hard` is the usual counterweight to a soft
death penalty. There is no vanilla "earn metal portals" option: it is
`portals=casual` (everything) or `normal` (haul metal), or a mod later
(AdvancedPortals: craftable portal tiers unlocked by the next biome's
materials; TieredPortals: metal unlocks per boss kill).

## Mods later

Vanilla at launch, by decision on 2026-09-09: the first tiered portal needs
iron anyway, so there is nothing to gain from mods before the Swamp, and staying
vanilla keeps friends on the plain Steam launcher while 1.0 hotfixes and mod
updates settle.

**Planned flip, once the group reaches iron:** AdvancedPortals, so metal
transport is earned by crafting portal tiers instead of a flat
`portals=casual`. Ancient carries copper/tin (costs iron + ancient bark),
Obsidian carries iron (costs silver), Black Marble carries everything (costs
black metal + refined eitr). The vanilla portal is untouched; config is
server-synced and live-editable in `randyknapp.mods.advancedportals.cfg`.

```yaml
TYPE: BepInEx
MODS: |
  ValheimModding-Jotunn-<latest>
  RandyKnapp-AdvancedPortals-<latest>
```

Odin installs the list from Thunderstore on start; dependencies must be listed
explicitly (BepInEx itself comes from `TYPE`). Pin exact versions. Before
flipping, check on Thunderstore that both have a release dated after the
current Valheim patch: on launch day AdvancedPortals 1.2.0 shipped 2.5 h before
Jotunn 2.30.0, the first Jotunn built for 1.0.7, and Jotunn's custom piece
categories were not yet updated for 1.0.

**Every player must run the same set once mods are on.** Jotunn version-checks
on connect and rejects clients missing a mod, naming what they lack. Friend
setup: r2modman or Gale, a Valheim profile with `BepInExPack_Valheim`,
`Jotunn` and `AdvancedPortals`, launch modded. r2modman profile codes expire in
about an hour, so share the list rather than a code.

**Updates with mods:** Valheim version-locks clients to the server and Steam
updates clients automatically, so `AUTO_UPDATE` stays on even though Odin's
docs suggest otherwise. A hotfix can break a mod for a day or two; Odin backs
the world up before every update. Setting `TYPE` back to `Vanilla` and removing
`MODS` drops the loader and the world keeps working minus the placed advanced
portals.

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
