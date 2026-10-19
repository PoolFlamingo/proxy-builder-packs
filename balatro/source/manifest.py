#!/usr/bin/env python3
"""The pack's entry in the app's manifest
(`src-tauri/assets/packs-descargables.json` of Proxy Builder): every file
with its SHA-256 and the commit of the packs repository where they are.

    python -I manifest.py <pack folder> <commit> > entry.json
"""

import hashlib
import json
import sys
from pathlib import Path

pack = Path(sys.argv[1]).resolve()
commit = sys.argv[2]


def sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


OUTSIDE = {"source", "extras", "fonts", "golden"}
ficheros = {}
for f in sorted(pack.rglob("*")):
    rel = f.relative_to(pack)
    if f.is_dir() or rel.parts[0] in OUTSIDE or rel.name in ("extras.json", "README.md", "CREDITS.md"):
        continue
    ficheros[str(rel).replace("\\", "/")] = sha(f)

extras = []
for e in json.loads((pack / "extras.json").read_text()):
    extras.append({**e, "ruta": "extras/" + e["ruta"], "sha256": sha(pack / "extras" / e["ruta"])})

letras = []
for t in sorted((pack / "fonts").glob("*.ttf")):
    lic = t.with_name(t.stem + "-LICENSE.txt")
    letras.append({
        "ruta": f"fonts/{t.name}", "sha256": sha(t),
        "licencia": f"fonts/{lic.name}", "licencia_sha256": sha(lic),
    })

pj = json.loads((pack / "pack.json").read_text())
print(json.dumps({
    "id": pj["id"], "nombre": pj["nombre"], "commit": commit, "carpeta": f"{pack.name}/",
    "ficheros": ficheros, "letras": letras, "extras": extras,
}, ensure_ascii=False, indent=1))
