#!/usr/bin/env python3
"""Mint the mod-manager profile code for the Valheim server from the pinned mod list.

Reads MODS from ../app/helmrelease.yaml, drops server-only mods, adds the
client-only ones and the BepInEx pack, builds a byte-identical profile zip
(the r2modman format, which Gale reads too), uploads it through the same open
endpoint the managers use (no account) and prints the code. Same mod list =>
same code, because the profile is stored by content hash. --write puts the
code into README.md and PLAYERS.md between the profile-code markers.

Repositories: an entry is Thunderstore unless it carries Odin's `hex:` prefix
(Hexium). A profile with any Hexium mod is uploaded to Hexium's endpoint and
imports only in Gale; a Thunderstore-only profile imports in Gale, r2modman
and Thunderstore Mod Manager alike.

Usage:  python3 export.py [--write] [--dry-run]
"""
import base64
import hashlib
import io
import json
import pathlib
import re
import sys
import urllib.request
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
APP_DIR = HERE.parent
HELMRELEASE = APP_DIR / "app" / "helmrelease.yaml"
DOCS = [APP_DIR / "README.md", APP_DIR / "PLAYERS.md"]

PROFILE_NAME = "Tired Old Vikings"
BEPINEX = "denikson-BepInExPack_Valheim-5.4.2350"
# Installed on clients only (their README says not on a dedicated server).
# Same `hex:` prefix convention as MODS if one ever comes from Hexium.
CLIENT_ONLY = ["Advize-PlantEasily-2.2.0"]
# In MODS but nothing for clients to install.
SERVER_ONLY = {"Blockheim-LetMeSleep"}

# Same endpoints Gale uses (src-tauri/src/thunderstore/backend.rs).
ENDPOINTS = {
    "thunderstore": "https://thunderstore.io/api/experimental/legacyprofile/",
    "hexium": "https://hexium.gg/api/experimental/legacyprofile/",
}
PREFIXES = {"ts": "thunderstore", "thunderstore": "thunderstore", "hex": "hexium", "hexium": "hexium"}
# The CDNs answer 403 to the default urllib agent.
HEADERS = {"User-Agent": "home-ops-valheim-profile-export/1.0"}
MARK_OPEN, MARK_CLOSE = "<!-- profile-code -->", "<!-- /profile-code -->"


def server_mods() -> list[str]:
    text = HELMRELEASE.read_text()
    m = re.search(r"^(\s*)MODS: \|\n((?:\1\s+\S.*\n)+)", text, re.M)
    if not m:
        sys.exit(f"no MODS block in {HELMRELEASE}")
    return [line.strip() for line in m.group(2).splitlines() if line.strip()]


def parse(entry: str) -> tuple[str, str, tuple[int, int, int]]:
    """'hex:Author-Name-1.2.3' -> ('hexium', 'Author-Name', (1, 2, 3))."""
    source = "thunderstore"
    if ":" in entry:
        prefix, entry = entry.split(":", 1)
        source = PREFIXES.get(prefix.lower())
        if source is None:
            sys.exit(f"unknown repository prefix in {entry!r}")
    ns, name, ver = entry.rsplit("-", 2)
    major, minor, patch = (int(x) for x in ver.split("."))
    return source, f"{ns}-{name}", (major, minor, patch)


def export_r2x(entries: list[str]) -> str:
    out = [f"profileName: {PROFILE_NAME}", "mods:"]
    for entry in entries:
        source, name, (major, minor, patch) = parse(entry)
        out += [
            f"  - name: {name}",
            "    version:",
            f"      major: {major}",
            f"      minor: {minor}",
            f"      patch: {patch}",
            "    enabled: true",
        ]
        if source != "thunderstore":
            # Gale's extension of the r2modman format; absent means Thunderstore.
            out.append(f"    source: {source}")
    return "\n".join(out) + "\n"


def profile_bytes(entries: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo("export.r2x", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, export_r2x(entries))
    return b"#r2modman\n" + base64.b64encode(buf.getvalue())


def backend_for(entries: list[str]) -> str:
    return "hexium" if any(parse(e)[0] == "hexium" for e in entries) else "thunderstore"


def upload(backend: str, body: bytes) -> str:
    req = urllib.request.Request(
        ENDPOINTS[backend] + "create/", data=body, method="POST",
        headers={"Content-Type": "application/octet-stream", **HEADERS},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["key"]


def verify(backend: str, code: str, body: bytes) -> None:
    req = urllib.request.Request(ENDPOINTS[backend] + f"get/{code}/", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        got = resp.read()
    if got != body:
        sys.exit("uploaded profile does not read back identically")


def write_docs(code: str) -> None:
    pat = re.compile(re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE), re.S)
    for doc in DOCS:
        text = doc.read_text()
        new = pat.sub(f"{MARK_OPEN}\n```\n{code}\n```\n{MARK_CLOSE}", text)
        if new == text and code not in text:
            sys.exit(f"no profile-code markers in {doc}")
        doc.write_text(new)


def main() -> None:
    args = set(sys.argv[1:])
    entries = [BEPINEX] + [e for e in server_mods() if parse(e)[1] not in SERVER_ONLY] + CLIENT_ONLY
    backend = backend_for(entries)
    body = profile_bytes(entries)
    print("profile:", ", ".join(entries))
    print("backend:", backend, "(Gale only)" if backend == "hexium" else "(Gale, r2modman, TMM)")
    print("sha256:", hashlib.sha256(body).hexdigest()[:16])
    if "--dry-run" in args:
        print(export_r2x(entries))
        return
    code = upload(backend, body)
    print("code:", code)
    verify(backend, code, body)
    print("verified: reads back identically")
    if "--write" in args:
        write_docs(code)
        print("wrote", ", ".join(d.name for d in DOCS))


if __name__ == "__main__":
    main()
