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
direct connect only. Since the mod flip, friends need the client mod profile
from the "Mods" section before the join link works.

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
| `/home/steam/valheim` | `valheim-server-files` (plain 5Gi) | no | SteamCMD download, `config.json`, `discord.json`, `BepInEx/` (loader, plugins, `config/*.cfg`) |
| `/config-overrides`, `/valheim-post-install.d/10-config-overrides.sh` | `valheim-config` ConfigMap (generated from `app/resources/`) | git | Mod config overrides and the hook that applies them each boot |
| `/tmp`, `~/.steam`, `~/.local`, `~/.cache`, `~/Steam` | emptyDir | no | SteamCMD and Steam SDK scratch |

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
`portals=casual` (everything) or `normal` (haul metal), or a mod
(AdvancedPortals below: craftable portal tiers unlocked by the next biome's
materials).

## Mods

Modded since 2026-09-16 (vanilla from launch until the group reached iron, by
the 2026-09-09 decision). Odin installs `MODS` from Thunderstore on every start;
dependencies must be listed explicitly, BepInEx itself comes from `TYPE`, and
every pin is exact so a restart never picks up an untested build.

| Mod | Server | Client | Why |
|---|---|---|---|
| Jotunn | yes | yes | library for AdvancedPortals; version-checks clients on connect |
| AdvancedPortals | yes | yes | earned metal transport: Ancient (copper/tin, costs iron + ancient bark), Obsidian (iron, costs silver), Black Marble (everything, costs black metal + refined eitr). Vanilla portal untouched |
| PlantEverything | yes | yes | plant berries, mushrooms, flowers, saplings and more with the cultivator; server-synced config |
| LetMeSleep | yes | no | skip the night when a fraction of online players are in bed |
| PlantEasily | **no** | yes | bulk planting, grid snap, replant on harvest. Client-only by design; its README says not to install it on a dedicated server |

**Friend setup (r2modman or Gale, Windows/Linux/Steam Deck):** a Valheim
profile with exactly these, then launch modded:

```
denikson-BepInExPack_Valheim-5.4.2350
ValheimModding-Jotunn-2.30.0
RandyKnapp-AdvancedPortals-1.2.0
Advize-PlantEverything-1.21.2
Advize-PlantEasily-2.2.0
```

Jotunn rejects a client that is missing a server mod or runs a different
version, and the dialog names what is missing. LetMeSleep is server-only, so it
is not in the client list. r2modman profile codes expire in about an hour, so
share the list rather than a code. Bump client and server pins together.

**Compatibility state at the flip (Valheim l-1.0.12, netver 40):** Jotunn
2.30.0 is built for 1.0.7 and works on 1.0.12, but its custom piece categories
are not updated for 1.0, so AdvancedPortals' portals may land in an unexpected
hammer tab (cosmetic). AdvancedPortals 1.2.0 shipped before the first 1.0
Jotunn and carries no 1.0 changelog line; it was verified by hand in a
single-player 1.0.12 world (`devcommands`, `debugmode`, B for no-cost build
shows every piece). PlantEverything 1.21.2 is compiled against 1.0.12 (since 1.21.1),
LetMeSleep 1.0.5 and PlantEasily 2.2.0 against 1.0.

### Mod configs

BepInEx writes one `<plugin>.cfg` per mod into `BepInEx/config/` on the
`valheim-server-files` PVC the first time the mod loads. Odin copies a
package's shipped config only when the file is absent and never overwrites it,
so left alone those files drift on the PVC with no record in git.

The fix here is a small overlay: `app/resources/*.cfg` are minimal files with
only the keys we deliberately set, and `10-config-overrides.sh` runs as an Odin
post-install hook (`/valheim-post-install.d/`, executed on every start after
mods are installed, before the server launches) and copies them over the live
files. BepInEx then fills in every key that is missing with the mod default and
rewrites the file, so a two-line override is a complete config.

Consequences, on purpose:

- **Git wins.** Editing a managed file in `resources/` and merging changes the
  ConfigMap; Reloader restarts the pod; the hook reapplies. Edits made in-game
  through Configuration Manager or by hand on the PVC last until the next
  restart. Unmanaged mods (AdvancedPortals) keep the normal behaviour: the file
  on the PVC is the truth and in-game admin edits persist.
- **A managed file lists only overrides.** Do not paste a full generated config
  in; the mod default for anything not listed is what you get, and the file
  stays readable.
- Files must be named exactly as the mod names them (`blockchaaain.LetMeSleep.cfg`,
  `advize.PlantEverything.cfg`). A typo just creates an orphan file.
- `${...}` in a config would be eaten by Flux substitution, which is why the
  generator carries `kustomize.toolkit.fluxcd.io/substitute: disabled`.

Managed today: LetMeSleep `ratio` (0.5; a third is 0.34) and PlantEverything
`LockConfiguration` (admin-only changes; respawn-time knobs are listed in the
file, commented out). AdvancedPortals runs on defaults; its costs and hammer
tab are server-synced and live-editable by an admin in
`randyknapp.mods.advancedportals.cfg`. To bring it under git, add a
`resources/randyknapp.mods.advancedportals.cfg` with the overrides and list it
in `kustomization.yaml`.

### Updating with mods

`UPDATE_ON_STARTUP=0` and `AUTO_UPDATE=0` since the flip: a liveness restart at
03:00 must not silently move the server to a Valheim build the mods were not
made for. Steam still updates friends' clients automatically, and a patch that
bumps the network version locks them out until the server follows, so an update
is a short deliberate sequence rather than a surprise:

1. Check Thunderstore for a Jotunn release dated after the new Valheim patch
   (AdvancedPortals and PlantEverything usually follow within a day or two).
2. Bump the pins in `MODS` and in the friends' list above, same versions.
3. Set `UPDATE_ON_STARTUP: "1"` for that rollout, or run the update by hand:
   `kubectl -n game-servers exec valheim-0 -- odin install`, then delete the
   pod. Odin backs the world up first (`AUTO_BACKUP_ON_UPDATE`).
4. Set `UPDATE_ON_STARTUP` back to `"0"` if it was flipped.

Skipping a patch is fine as long as the network version did not change; the
server log prints `Network version check, their:N, mine:N` on every join.

Rolling back is an env change: `TYPE: Vanilla` and no `MODS` drops the loader,
and the world keeps working minus placed modded pieces (advanced portals and
PlantEverything plantables turn into nothing, which is the usual mod-removal
cost).

Thunderstore marks server-only mods, which need nothing on clients. Mods that
use the RPC port need 2458 forwarded, which the forward above already covers.
Crossplay (`ENABLE_CROSSPLAY=1`) is off by design: it is only needed for console
or Game Pass players and pairs badly with mods.

## Gotchas

- **SteamCMD "Failed to install app '896660' (Missing configuration)" then
  "(Missing file permissions)", exit code 8, container restarts**: the image's
  `steam` user is uid 111 and `/home/steam` is mode 750, so our uid 1000 cannot
  create anything directly under the home dir. SteamCMD wants `~/Steam` for its
  config and logs. Every path SteamCMD or the game writes under `~` must be an
  emptyDir or PVC mount (table above). Hit on first boot 2026-09-10.
- **Stuck on "state is 0x6 after update job"**: stale SteamCMD manifest. Odin
  retries once automatically (`STEAMCMD_RESET_ON_FAILURE`); if it loops, delete
  `steamapps/` on the `valheim-server-files` PVC and restart.
- **Admin commands say "not admin"**: adminlist entry lacks the `V_` prefix.
- **`externalTrafficPolicy` must stay `Cluster`**: Cilium L2 announcements
  blackhole with `Local` (see the unifi README). Client source IPs are SNATed,
  which is fine because Valheim bans by platform id, not IP.
- **Game process dies, pod stays `1/1 Running`**: the start script only
  waits on its log tailer, so a crash of `valheim_server.x86_64` leaves Odin
  and Huginn alive and the pod green. Huginn `/liveness` answers 200 with the
  game dead, and `/health` and `/readiness` hang under `PUBLIC=0` (A2S). The
  probes are therefore `pgrep -f valheim_server.x86_64`: startup allows 10 min
  for SteamCMD and the world load, liveness restarts the container after ~90 s
  without the process, readiness pulls the endpoints. Seen 2026-09-13: SIGSEGV
  in Mono GC during the hourly "Unloading unused assets" pass (a known Unity
  bug), players locked out for 3.5 h before anyone noticed.
- **Every restart reinstalls `MODS`**: Odin re-resolves the list on start, so a
  Thunderstore outage delays boot until the startup probe gives up. Pins keep
  the resolved versions stable.
