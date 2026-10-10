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
| `/home/steam/valheim/BepInEx/config` | `valheim` (`bepinex-config/` subPath) | VolSync | one `<plugin>.cfg` per mod, edited in place (see "Mod configs") |
| `/home/steam/valheim` | `valheim-server-files` (plain 5Gi) | no | SteamCMD download, `config.json`, `discord.json`, BepInEx loader and plugins (re-downloadable) |
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
the 2026-09-09 decision). Odin installs `MODS` from Thunderstore (or Hexium
with a `hex:` prefix, image 3.8+) on every start; dependencies must be listed
explicitly, BepInEx itself comes from `TYPE`, and every pin is exact so a
restart never picks up an untested build.

| Mod | Server | Client | Why |
|---|---|---|---|
| Jotunn | yes | yes | library for AdvancedPortals, OCDheim, BCT and ReforgedPotential; version-checks clients on connect |
| AdvancedPortals | yes | yes | earned metal transport: Ancient (copper/tin, costs iron + ancient bark), Obsidian (iron, costs silver), Black Marble (everything, costs black metal + refined eitr). Vanilla portal untouched |
| PlantEverything | yes | yes | plant berries, mushrooms, flowers, saplings and more with the cultivator; server-synced config |
| LetMeSleep | yes | no | skip the night when a fraction of online players are in bed |
| AzuExtendedPlayerInventory | yes | yes | equipment slots, quick slots (3) and extra inventory rows; Hexium. Server holds the synced config (rows, slot count, vanity/loadout buttons) and kicks clients without the mod. **One-way:** removing it can lose whatever sits in its extra rows and slots, so everyone empties them into a chest first |
| AzuContainerSizes | yes | yes | bigger chests, carts and ship holds to absorb `resources=muchmore`; Hexium. Defaults are vanilla sizes, so it changes nothing until configured. Shrinking a size later keeps items (the chest grows back to fit overflow, 1.1.4+) |
| AzuAutoStore | yes | yes | `.` dumps inventory into chests within 5 m that already hold that item; favorited items and slots are skipped. Also pulls dropped items off the ground into nearby chests (per-container range, see "Mod configs"); Hexium |
| Better Cartography Table | yes | yes | pins are private by default and shared one at a time to a table (public pins; guild pins only with the Guilds mod, not installed); opening a table syncs exploration both ways, no separate Read/Write. Pins live on **one** table per player: using a different table asks to switch and swaps the public pin set (an empty table offers to take your pins, for relocating). Server copy makes Jotunn refuse clients without it (minor-version strict). All its settings are per-client |
| ReforgedPotential | yes | yes | Forge of Potential failure drops the item one level instead of destroying it (our config, see "Mod configs"). Rolls happen on the crafting client with the server's synced config; it declares no network-compatibility level, so the server does **not** refuse a client without it, and that client would roll vanilla odds. The synced profile is the guard |
| PlantEasily | **no** | yes | bulk planting, grid snap, replant on harvest. Client-only by design; its README says not to install it on a dedicated server |
| OCDheim | **no** | yes | world-grid snapping for building, hoe/cultivator areas and seeds (Alt), finer snap (Z), terrain-tweak removal. Client-only by choice: on the server every client would have to match its version. Its extra build pieces and vertical stacking are **on** in the sync profile (Tyler's call, 2026-10-04); they collapse for anyone who joins without OCDheim, which nothing on the server enforces, so the synced profile is the guard. Does not replace PlantEasily: it snaps one seed at a time, PlantEasily plants whole grids |
| Build Camera CHE | **no** | yes | detached build camera on hammer, hoe and cultivator (Azumatt's Custom Hammers Edition). Hexium-only since 1.3.2. Client-only here on purpose: installed on the server it kicks every client that lacks the exact same version, in exchange for server-locked config. Add `hex:Azumatt-Build_Camera_Custom_Hammers_Edition-<ver>` to `MODS` if that trade is ever wanted |

**Friend setup:** the player-facing walkthrough is [PLAYERS.md](PLAYERS.md)
(fill in the address and password when you send it; neither is in the repo).
Friends import Gale **sync** code `YGNX7M` (owned by Tyler's Discord login;
exported by hand from Gale after each pin bump, then **Push update** so
subscribers pull it automatically). The plain, manager-agnostic profile code
minted from the repo carries the same list and is the fallback:

<!-- profile-code -->
```
52324a846f69db84516f2dd9b16e7b22
```
<!-- /profile-code -->

Equivalent manual profile, exact versions:

```
denikson-BepInExPack_Valheim-5.4.2351
ValheimModding-Jotunn-2.30.2
RandyKnapp-AdvancedPortals-1.2.0
Advize-PlantEverything-1.21.3
Azumatt-AzuExtendedPlayerInventory-2.6.1            (Hexium)
Azumatt-AzuContainerSizes-1.1.8                     (Hexium)
Azumatt-AzuAutoStore-3.1.7                          (Hexium)
nbusseneau-Better_Cartography_Table-1.0.0
Akuichi-ReforgedPotential-2.0.7
Advize-PlantEasily-2.3.0
Azumatt-Build_Camera_Custom_Hammers_Edition-1.3.4   (Hexium)
javadevils-OCDheim-0.3.4
```

**Client keybinds collide on defaults:** AzuAutoStore's favoriting modifier is
Z (both slots), which is also OCDheim's precision-mode toggle, and Alt is
OCDheim's grid-mode toggle. Rebind `Azumatt.AzuAutoStore.cfg`
`[3 - Favoriting] FavoritingModifierKeybind1/2` to `LeftControl` in the Gale
sync profile before pushing it (that key is client-side, not server-synced).
AzuExtendedPlayerInventory has its own favoriting key (`[10 - Favoriting]`)
but ignores it while AzuAutoStore is installed: there is one favorite set,
stored by AzuAutoStore (`AzuAutoStore_player_<id>.dat`), and it protects items
from both the `.` dump and the chest's Place Stacks / Stack All.
PlantEasily (Right Ctrl + arrows, Left Shift, F6/F8/F10) and Build Camera (B)
do not overlap.

Jotunn rejects a client that is missing a server mod or runs a different
version, and the dialog names what is missing (seen 2026-09-21: a friend on
Jotunn 2.30.1 against our 2.30.0 was refused until the server caught up).
LetMeSleep is server-only, so it is not in the client list.

**Manager: Gale, required since Build Camera (2026-09).** The code is the
r2modman profile format plus Gale's per-mod `source` field, and Build Camera
lives only on Hexium (`hexium.gg`), where Azumatt publishes exclusively since
2026 (the Thunderstore listing is deprecated at 1.3.1). r2modman and
Thunderstore Mod Manager cannot read Hexium, so they can neither import this
code nor install the mod by hand. Gale imports r2modman profiles in one click
for anyone switching. Jotunn and BepInExPack are mirrored on Hexium; the
three Azu mods are Hexium-only like Build Camera, the rest Thunderstore-only,
which is fine because Gale reads both.

**Profile codes do not expire.** Thunderstore stores an exported profile by
content hash with no expiry (checked in its source: `LegacyProfile` has only a
global storage cap), so the same mod list always yields the same code and an
old code keeps resolving. Hexium runs the same `legacyprofile` API. After any
pin bump, regenerate the code from the repo instead of exporting by hand:

```sh
python3 kubernetes/apps/game-servers/valheim/profile/export.py --write
```

`profile/export.py` reads `MODS` from the HelmRelease, drops the server-only
mods, adds the BepInEx pack and the client-only mods (both pinned at the top
of the script), builds a byte-identical profile zip, uploads it through the
same open endpoint the managers use, reads it back to verify, and rewrites the
code between the `profile-code` markers here and in PLAYERS.md. Commit it with
the `MODS` change. `--dry-run` prints the profile without uploading.

**Hexium mods** carry Odin's `hex:` prefix in `MODS` or in the script's
`CLIENT_ONLY` list (Build Camera today). The script marks each one with Gale's
`source: hexium` field and uploads the profile to Hexium's `legacyprofile`
endpoint instead of Thunderstore's; that code imports only in Gale. BepInExPack
always comes from Thunderstore regardless.

**Compatibility state (2026-10 table + forge batch: Valheim l-1.0.17, netver
40):** Better Cartography Table 1.0.0 (2026-10-05) is its 1.0 release, built
on Jotunn 2.30.2 (matches) and BepInEx 5.4.2351. It replaces the table's
Read/Write with its own handler and keeps pins in its own ZDO key, so vanilla
shared pins on existing tables are left alone (public pins are also copied
into vanilla data for unmodded readers). ReforgedPotential 2.0.7 (2026-10-02)
depends on Jotunn 2.26.1+ and syncs its config through Jotunn's
`SynchronizationManager` (admin-only entries, file watcher); it patches the
upgrade crafting path only, so nothing overlaps with the Azu mods or BCT.
Neither has a 1.0.17-specific report either way; 1.0.17 did not move netver.

**Compatibility state (2026-10 QoL batch: Valheim l-1.0.16, netver 40):** the
server picked up 1.0.16 (build 25527701) on the 2026-10-01 restart because
`UPDATE_ON_STARTUP` was still `"1"` from the September rollout; all four mods
loaded and netver did not move. 1.0.16 only fixed Deep North terrain reverting,
raid over-spawning and two achievements. AzuExtendedPlayerInventory 2.6.1 and
AzuAutoStore 3.1.7 were built after 1.0.16; AzuContainerSizes 1.1.8 targets
1.0 (1.1.7 added the Wardrobe and Grausten chest). AzuEPI 2.4.14 added
AzuAutoStore favoriting compat; neither touches portals, planting or sleep.
OCDheim 0.3.4 depends on Jotunn 2.30.2 (matches) and says 1.0.15 compat
explicitly, with three releases since 1.0.16 and no break reported.
PlantEasily 2.3.0 is compiled against 1.0.16.

**Compatibility state (2026-09 update: Valheim l-1.0.15, netver 40):** the
server moved from 1.0.12 to 1.0.15 together with the pins below; the network
version did not change between them, so clients were never locked out, but
1.0.14 fixed character saves on hosted servers and a biome cache that could
block joining, and 1.0.15 a terrain-duplication performance bug. Jotunn 2.30.1
brought custom piece categories to the 1.0 build menu (AdvancedPortals' portals
get their own tag instead of landing in a random tab) and 2.30.2 fixed the
legacy menu and Deep North asset mocking; AdvancedPortals 1.2.0 is unchanged
since launch and only depends on Jotunn's deprecated-but-kept category API.
PlantEverything 1.21.3 and PlantEasily 2.2.1+ are compiled against 1.0.15,
Build Camera 1.3.2+ against 1.0.14, LetMeSleep 1.0.5 against 1.0, BepInExPack
5.4.2351 is a logging and doorstop refresh. Jotunn issue #490 (client
disconnects on 1.0.15) is misfiled: the failing class is blaxxun's PieceManager
library bundled by another mod, not Jotunn.

**Image 3.8.x:** `steam` is uid 1000 in the image now (was 111), which is what
our `runAsUser`/`fsGroup` always assumed; the emptyDir mounts under `~` stay
because they still keep SteamCMD scratch off the PVCs. 3.8 also added the
`hex:` repository prefix, per-package BepInEx install routes (patchers, core),
keeps `BepInEx.cfg` edits across framework reinstalls, tails the game log
across truncation, and stops reporting a failed Steam registration as a
successful start.

### Mod configs

Each mod writes `BepInEx/config/<plugin>.cfg` the first time it loads. That
directory is a subPath of the backed-up `valheim` claim (Storage table), so the
files ride the VolSync/kopia schedule with the world, and Odin never overwrites
a config that already exists. They are edited in place, not tracked in git:

- In-game, as admin, through the Configuration Manager mod for anything
  server-synced (AdvancedPortals costs and hammer tab, PlantEverything
  everything outside `[General]`). Takes effect live.
- Or on the pod, for anything else:

  ```sh
  kubectl -n game-servers exec -it valheim-0 -- vi /home/steam/valheim/BepInEx/config/blockchaaain.LetMeSleep.cfg
  kubectl -n game-servers delete pod valheim-0     # server-local settings need a restart
  ```

Settings we run off-default (set by hand after the first modded boot generated
the files):

| File | Key | Value | Why |
|---|---|---|---|
| `blockchaaain.LetMeSleep.cfg` | `[General] ratio` | `0.3` | a third of online players in bed skips the night (mod default 0.5; range 0.01 to 1.0) |

The three Azu mods are ServerSync with `Lock Configuration = On`: the server's
file wins for every `[Synced with Server]` key, and a file watcher pushes an
edit to connected clients on save, no restart needed. Settings to make after
their first boot:

- `Azumatt.AzuExtendedPlayerInventory.cfg`: `[0 - Presets] Apply Preset =
  Minimal` (hides the vanity and loadout buttons, both server-synced; resets
  itself to `None` once applied). The stats panel and layout it also touches
  are per-client, so players apply the preset in their own copy for those.
  `[2 - Inventory] Extra Inventory Rows` defaults to **0** (range 0-5);
  `[3 - Quick Slots] Number of Quick Slots` to 3.
- `Azumatt.AzuAutoStore.cfg` + `Azumatt.AzuAutoStore.yml`: `Player Range`
  (the `.` dump) defaults to 5 m; ground pickup uses each container's `range`
  in the yml (10 m for the example chests) and `Fallback Range` (10 m) for
  containers not listed. `Must Have Existing Item To Pull` is on by default.
- `Azumatt.AzuContainerSizes.cfg`: defaults are the vanilla sizes (rows x
  columns; columns cap at 8, the inventory width; chest rows cap at 20, ship
  and cart rows at 30):

  | Container | Key prefix | Default |
  |---|---|---|
  | Personal chest | `Personal Chest` | 2 x 3 |
  | Wood chest | `Wood Chest` | 2 x 5 |
  | Reinforced chest | `Iron Chest` | 4 x 6 |
  | Black metal chest | `Blackmetal Chest` | 4 x 8 |
  | Wardrobe | `Wardrobe` | 10 x 5 |
  | Grausten chest | `Grausten Chest` | 5 x 8 |
  | Karve | `Karve` | 2 x 2 |
  | Longship | `Longboat` | 3 x 6 |
  | Cart | `Cart` | 3 x 6 |

`akuichi.ReforgedPotential.cfg` (server-synced). Vanilla, per guides: 65 %
success, 35 % the item is destroyed (35 % of materials back, never the idol),
one idol per attempt, idols loot-only. Out of the box the mod is far more
generous: 100 % success, craftable idols at the artisan table, a boss-gated
level cap (5 + 4 per boss), idol cost rising by 1 every level and a 2 s craft.
Target: vanilla rules, except a failure costs one level instead of the item:

| Section | Key | Default | Set |
|---|---|---|---|
| `Upgrade Settings` | `Upgrade Chance` | `1` | `0.65` |
| `Upgrade Settings` | `Break Chance` | `0` | `0` (failure = -1 level) |
| `Upgrade Settings` | `Cost Increase Interval` | `1` | `0` (flat cost) |
| `Upgrade Settings` | `Upgrade Crafting Time Base Duration` | `2` | `8` |
| `Boss Progression` | `Enable Boss Progression` | `true` | `false` |
| `Idol Progression` | `Enable Idol Progression` | `true` | `false` |
| `Recipes` | `Enable Recipes` | `true` | `false` (idols stay loot) |

`Consume Idols Only On Failure = true` is the softer option (a failure costs
only the idol, the item keeps its level).

PlantEverything ships with `[General] LockConfiguration = true` (admin-only
synced changes) and vanilla-balanced defaults; its author suggests lowering the
pickable respawn times (`[Berries]`, `[Mushrooms]`, `[Flowers]`, `[Debris]`,
minutes, defaults 240 to 300) if the group finds foraging too slow.
AdvancedPortals runs on defaults.

Removing a mod from `MODS` leaves its config behind; delete it by hand if the
mod is gone for good.

### Updating with mods

`UPDATE_ON_STARTUP=0` and `AUTO_UPDATE=0` between rollouts: a liveness restart
at 03:00 must not silently move the server to a Valheim build the mods were not
made for. Steam still updates friends' clients automatically, and a patch that
bumps the network version locks them out until the server follows, so an update
is a short deliberate sequence rather than a surprise:

1. Check Thunderstore for a Jotunn release dated after the new Valheim patch
   (AdvancedPortals and PlantEverything usually follow within a day or two),
   and Hexium for the Azu mods and Build Camera.
2. Bump the pins in `MODS`, in `profile/export.py` (`BEPINEX`, `CLIENT_ONLY`)
   and in the friends' list above, same versions, then run the exporter with
   `--write` so both docs carry the new code.
3. Set `UPDATE_ON_STARTUP: "1"` in the same PR. On the restart SteamCMD moves
   the game to the current Steam build before Odin installs the new pins, and
   Odin backs the world up first (`AUTO_BACKUP_ON_UPDATE`). Do not run
   `odin install` by hand against a running server: the game loads asset
   bundles lazily and replacing them underneath it is how it crashes.
4. Follow-up commit: `UPDATE_ON_STARTUP` back to `"0"` (one more short
   restart). Check the log for `Valheim Version:` and the new mod versions,
   then send friends the new code.

Skipping a patch is fine as long as the network version did not change; the
server log prints `Network version check, their:N, mine:N` on every join.

Rolling back is an env change: `TYPE: Vanilla` and no `MODS` drops the loader,
and the world keeps working minus placed modded pieces (advanced portals and
PlantEverything plantables turn into nothing, which is the usual mod-removal
cost). Before dropping AzuExtendedPlayerInventory or AzuContainerSizes, have
everyone empty the extra inventory rows/slots and the beyond-vanilla chest
slots: AzuEPI's own docs warn reverting can lose items, and what vanilla does
with items past a chest's stock size is unverified.

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
- **Never set `CLEAN_INSTALL=1`**: it wipes `/home/steam/valheim`, and
  `BepInEx/config` there is a mountpoint of another claim, so the wipe fails
  halfway. To rebuild the server files, delete the `valheim-server-files` PVC
  instead; the configs and world are on the other claim.
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
