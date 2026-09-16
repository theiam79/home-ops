#!/usr/bin/env python3
"""Mint the r2modman profile code for the Valheim server from the pinned mod list.

Reads MODS from ../app/helmrelease.yaml, drops server-only mods, adds the
client-only ones and the BepInEx pack, builds a byte-identical r2modman
profile zip, uploads it to Thunderstore (the same open endpoint r2modman
uses; no account) and prints the code. Same mod list => same code, because
Thunderstore stores profiles by content hash. --write puts the code into
README.md and PLAYERS.md between the profile-code markers.

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
CLIENT_ONLY = ["Advize-PlantEasily-2.2.0"]
# In MODS but nothing for clients to install.
SERVER_ONLY = {"Blockheim-LetMeSleep"}

CREATE_URL = "https://thunderstore.io/api/experimental/legacyprofile/create/"
GET_URL = "https://thunderstore.io/api/experimental/legacyprofile/get/{}/"
# Thunderstore's CDN answers 403 to the default urllib agent.
HEADERS = {"User-Agent": "home-ops-valheim-profile-export/1.0"}
MARK_OPEN, MARK_CLOSE = "<!-- profile-code -->", "<!-- /profile-code -->"


def server_mods() -> list[str]:
    text = HELMRELEASE.read_text()
    m = re.search(r"^(\s*)MODS: \|\n((?:\1\s+\S.*\n)+)", text, re.M)
    if not m:
        sys.exit(f"no MODS block in {HELMRELEASE}")
    return [line.strip() for line in m.group(2).splitlines() if line.strip()]


def split_dep(dep: str) -> tuple[str, tuple[int, int, int]]:
    ns, name, ver = dep.rsplit("-", 2)
    major, minor, patch = (int(x) for x in ver.split("."))
    return f"{ns}-{name}", (major, minor, patch)


def export_r2x(deps: list[str]) -> str:
    out = [f"profileName: {PROFILE_NAME}", "mods:"]
    for dep in deps:
        name, (major, minor, patch) = split_dep(dep)
        out += [
            f"  - name: {name}",
            "    version:",
            f"      major: {major}",
            f"      minor: {minor}",
            f"      patch: {patch}",
            "    enabled: true",
        ]
    return "\n".join(out) + "\n"


def profile_bytes(deps: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo("export.r2x", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, export_r2x(deps))
    return b"#r2modman\n" + base64.b64encode(buf.getvalue())


def upload(body: bytes) -> str:
    req = urllib.request.Request(
        CREATE_URL, data=body, method="POST",
        headers={"Content-Type": "application/octet-stream", **HEADERS},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["key"]


def verify(code: str, body: bytes) -> None:
    req = urllib.request.Request(GET_URL.format(code), headers=HEADERS)
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
    deps = [BEPINEX] + [d for d in server_mods() if split_dep(d)[0] not in SERVER_ONLY] + CLIENT_ONLY
    body = profile_bytes(deps)
    print("profile:", ", ".join(deps))
    print("sha256:", hashlib.sha256(body).hexdigest()[:16])
    if "--dry-run" in args:
        print(export_r2x(deps))
        return
    code = upload(body)
    print("code:", code)
    verify(code, body)
    print("verified: reads back identically")
    if "--write" in args:
        write_docs(code)
        print("wrote", ", ".join(d.name for d in DOCS))


if __name__ == "__main__":
    main()
