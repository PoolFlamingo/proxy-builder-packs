#!/usr/bin/env python3
"""La entrada del pack en el manifiesto de la app
(`src-tauri/assets/packs-descargables.json` de Proxy Builder): cada fichero
con su SHA-256 y el commit del repositorio de packs donde están.

    python -I manifiesto.py <carpeta del pack> <commit> > entrada.json
"""

import hashlib
import json
import sys
from pathlib import Path

pack = Path(sys.argv[1]).resolve()
commit = sys.argv[2]


def sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


FUERA = {"fuente", "extras", "letras", "dorados"}
ficheros = {}
for f in sorted(pack.rglob("*")):
    rel = f.relative_to(pack)
    if f.is_dir() or rel.parts[0] in FUERA or rel.name in ("extras.json", "README.md", "CREDITOS.md"):
        continue
    ficheros[str(rel).replace("\\", "/")] = sha(f)

extras = []
for e in json.loads((pack / "extras.json").read_text()):
    extras.append({**e, "ruta": "extras/" + e["ruta"], "sha256": sha(pack / "extras" / e["ruta"])})

letras = []
for t in sorted((pack / "letras").glob("*.ttf")):
    lic = t.with_name(t.stem + "-LICENCIA.txt")
    letras.append({
        "ruta": f"letras/{t.name}", "sha256": sha(t),
        "licencia": f"letras/{lic.name}", "licencia_sha256": sha(lic),
    })

pj = json.loads((pack / "pack.json").read_text())
print(json.dumps({
    "id": pj["id"], "nombre": pj["nombre"], "commit": commit, "carpeta": f"{pack.name}/",
    "ficheros": ficheros, "letras": letras, "extras": extras,
}, ensure_ascii=False, indent=1))
