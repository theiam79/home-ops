# Joining Tired Old Vikings

The server runs a few mods, so the plain Steam launcher will be refused. The
whole setup is one import in a mod manager and takes about five minutes.

## 1. Install r2modman

Download r2modman from <https://thunderstore.io/c/valheim/> ("Get Mod Manager")
or <https://r2modman.com>. Windows, Linux and Steam Deck (desktop mode, the
Linux build) all work. Gale (<https://github.com/Kesomannen/gale>) is a fine
alternative and imports the same code.

Steam Deck: install it in desktop mode, then use the manager's own "Launch
modded" every time; adding the game to Game Mode launches vanilla.

## 2. Import the profile

Open r2modman, pick **Valheim**, then **Profiles** → **Import / Update** →
**From code** and paste this:

<!-- profile-code -->
```
01a0a8d4-7eae-e0c6-c41b-651ea3169abd
```
<!-- /profile-code -->

Keep the name it suggests (`Tired Old Vikings`) and select that profile.

If the code is refused, ask for a fresh one, or create an empty profile and
install these five from the **Online** tab, exact versions, in this order:

```
denikson-BepInExPack_Valheim   5.4.2350
ValheimModding-Jotunn          2.30.0
RandyKnapp-AdvancedPortals     1.2.0
Advize-PlantEverything         1.21.2
Advize-PlantEasily             2.2.0
```

Do **not** click "update all" later. The server checks versions on connect; a
newer mod on your side is a refused connection. When the server updates, a new
code goes out.

## 3. Launch and join

1. In r2modman, with the profile selected, press **Start modded**. The Valheim
   window shows a BepInEx console briefly; that is expected.
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

## If something goes wrong

| You see | Fix |
|---|---|
| A "mod mismatch" or "missing mod" dialog on connect | Your profile does not match the server. Re-import the code, or check the five versions above. |
| "Incompatible version" from Valheim itself | Your game updated ahead of the server. Wait for the all-clear, no downgrade needed. |
| No BepInEx console, mods obviously not loaded | You launched vanilla. Use **Start modded** in r2modman, not the Steam play button. |
| The join link does nothing | Steam is not running, or the address is wrong. Use Join IP from the menu. |
