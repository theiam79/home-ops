#!/bin/sh
# Odin post-install hook: copy the git-managed BepInEx config overrides over the
# live files every boot. See README "Mod configs" for why overwrite, not seed.
set -eu
src=/config-overrides
dst="${GAME_LOCATION:-/home/steam/valheim}/BepInEx/config"
mkdir -p "$dst"
for f in "$src"/*.cfg; do
  [ -e "$f" ] || continue
  cp -f "$f" "$dst/"
  echo "[config-overrides] applied $(basename "$f")"
done
