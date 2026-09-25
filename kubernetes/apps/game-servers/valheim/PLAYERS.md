# Joining Tired Old Vikings

The server runs a few mods, so the plain Steam launcher will be refused. The
whole setup is one import in a mod manager and takes about five minutes.

## 1. Install Gale

Download Gale from <https://github.com/Kesomannen/gale/releases> (or the
"Mod Manager" link on <https://hexium.gg>). Windows (installer, winget,
Scoop), Linux (Flatpak, AppImage, deb, rpm, AUR) and Steam Deck (desktop
mode, the Flatpak) all work. No macOS build.

Already on r2modman or Thunderstore Mod Manager? Switch: one of our mods
(Build Camera) is only published on Hexium, which those two cannot read, so
the code below imports in Gale only. Gale imports your existing r2modman
profiles in one click, so nothing else is lost.

Steam Deck: install in desktop mode, then use the manager's own **Launch
modded** every time; adding the game to Game Mode launches vanilla.

## 2. Import the profile

Open Gale, pick **Valheim** as the game, open the profile menu in the top bar
and choose **Import profile**. Paste this sync code where it says "Enter
import code", leave **Create new** selected, and press **Import**:

```
AQHGYV
```

That is a Gale *sync* profile owned by Tyler: when the server's mods change,
Gale offers a **Pull update** (and pulls automatically at launch by default),
so no new code goes out. If the sync code is refused, this plain import code
carries the same mods:

<!-- profile-code -->
```
5508cb5183ac79fb772e88e90167b2db
```
<!-- /profile-code -->

Keep the name it suggests (`Tired Old Vikings`) and select that profile.

If the code is refused, ask for a fresh one, or create an empty profile and
install these six from Gale's mod browser, exact versions, in this order
(the last one shows up only when Hexium is enabled as a source):

```
denikson-BepInExPack_Valheim                 5.4.2351
ValheimModding-Jotunn                        2.30.2
RandyKnapp-AdvancedPortals                   1.2.0
Advize-PlantEverything                       1.21.3
Advize-PlantEasily                           2.2.2
Azumatt-Build_Camera_Custom_Hammers_Edition  1.3.3
```

Do **not** click "update all" later. The server checks versions on connect; a
newer mod on your side is a refused connection. When the server updates, pull
the synced profile (or import the new plain code).

## 3. Launch and join

1. In Gale, with the profile selected, press **Launch modded** in the top bar
   (r2modman calls it **Start modded**). The Valheim window shows a BepInEx
   console briefly; that is expected.
2. In Valheim: **Start Game** → pick or create a character → **Join Game** →
   **Join IP** → enter the address and port:

   ```
   <server address>:2456
   ```

3. Enter the password when asked.

Or, with Steam running, open this link and skip the menu:

```
steam://run/892970//+connect%20<server address>:2456
```

Address and password come from Tyler directly; they are not in this file.

## What the mods change

- **Portals carry metal once you build the right tier.** Ancient portal (needs
  iron and ancient bark) carries copper and tin, Obsidian (needs silver)
  carries iron, Black Marble (needs black metal and refined eitr) carries
  everything. The plain portal is unchanged.
- **Sleeping needs about a third of the players online**, not everyone. Get in
  bed and a message shows how many are in.
- **Farming.** The cultivator can plant berries, mushrooms, flowers and
  saplings (PlantEverything), and plants in rows or grids with snapping
  (PlantEasily). With the cultivator out, the keybinds show on screen.
- **Build camera.** With a hammer, hoe or cultivator out, press **B** to
  detach the camera and build from the air: mouse to look, **WASD** to move,
  **Space** / **Ctrl** up and down, **Shift** to move faster, click to build
  as usual, **B** again to return. It reaches about 100 m from your character
  and needs a workbench in range like normal building. Gamepad: triggers for
  up and down, right stick to look.

## If something goes wrong

| You see | Fix |
|---|---|
| A "mod mismatch" or "missing mod" dialog on connect | Your profile does not match the server. Re-import the code, or check the six versions above. |
| Gale says a mod in the code could not be found | Hexium is not enabled as a source in Gale's settings, or you pasted the code into r2modman. |
| "Incompatible version" from Valheim itself | Your game updated ahead of the server. Wait for the all-clear, no downgrade needed. |
| No BepInEx console, mods obviously not loaded | You launched vanilla. Use **Launch modded** in the manager, not the Steam play button. |
| The join link does nothing | Steam is not running, or the address is wrong. Use Join IP from the menu. |
