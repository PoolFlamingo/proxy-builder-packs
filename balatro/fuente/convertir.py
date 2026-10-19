#!/usr/bin/env python3
"""Paso D1 del plan (Fase D, Balatro): de los PSD de las plantillas a capas
PNG en coordenadas de la carta y un inventario.

    python -I convertir.py <carpeta con los PSD> <carpeta de salida>

Para cada plantilla (Balatro.psd → `joker`, Balatro-Land.psd → `tierra`…):

- cada capa de imagen que no sea la ilustración de ejemplo, el texto ni las
  muestras de color se exporta recortada al área de la carta (62,62)–(1302,1792)
  de un lienzo de 1365×1855 (unos 500 PPP con 3 mm de sangrado), a
  `capas/<plantilla>/<grupo>__<capa>.png`, con su zona en mm;
- de cada capa de texto se apunta caja, tamaño, color por tramos y alineación;
- se recompone con lo visible y se compara con la composición del PSD.

Todo va a `inventario.json` (y un resumen en `inventario.md`).

Necesita psd-tools, pillow, numpy (un venv aparte).
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from psd_tools import PSDImage

PLANTILLAS = {
    "Balatro.psd": "joker",
    "Balatro-Land.psd": "tierra",
    "Balatro-Planes.psd": "planeswalker",
    "Balatro-Planet.psd": "planeta",
    "Balatro-Spectral.psd": "espectral",
    "Balatro-Tarot.psd": "tarot",
    "Balatro-Voucher.psd": "vale",
}

# El área de la carta en el lienzo del PSD y lo que mide (mm).
CARTA = (62, 62, 1302, 1792)
ANCHO_MM, ALTO_MM = 63.0, 88.0
PX_X = (CARTA[2] - CARTA[0]) / ANCHO_MM
PX_Y = (CARTA[3] - CARTA[1]) / ALTO_MM

# Lo que no se exporta: la ilustración de ejemplo y las ayudas.
FUERA = {"ART", "Color Swatches"}


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip()).strip("-").lower()
    return s or "capa"


def mm(x0, y0, x1, y1):
    return {
        "x": round((x0 - CARTA[0]) / PX_X, 3),
        "y": round((y0 - CARTA[1]) / PX_Y, 3),
        "w": round((x1 - x0) / PX_X, 3),
        "h": round((y1 - y0) / PX_Y, 3),
    }


def recortar(img: Image.Image, bbox):
    """La imagen de la capa (en `bbox` del lienzo) recortada al área de la carta."""
    x0, y0, x1, y1 = bbox
    cx0, cy0 = max(x0, CARTA[0]), max(y0, CARTA[1])
    cx1, cy1 = min(x1, CARTA[2]), min(y1, CARTA[3])
    if cx1 <= cx0 or cy1 <= cy0:
        return None, None
    recorte = img.crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
    return recorte, (cx0, cy0, cx1, cy1)


def texto(capa):
    try:
        ed, rd = capa.engine_dict, capa.resource_dict
        fuentes = rd["FontSet"]
        runs = ed["StyleRun"]["RunArray"]
        largos = ed["StyleRun"]["RunLengthArray"]
        t = capa.text
        tramos, i = [], 0
        for r, n in zip(runs, largos):
            ss = r["StyleSheet"]["StyleSheetData"]
            color = [round(float(v), 3) for v in ss.get("FillColor", {}).get("Values", [])]
            tramos.append({
                "texto": t[i:i + int(n)],
                "letra": str(fuentes[ss.get("Font", 0)]["Name"]).strip("'"),
                "tam_px": round(float(ss.get("FontSize", 0)) * float(capa.transform[0]), 2),
                "color": "#%02x%02x%02x" % tuple(round(c * 255) for c in color[1:4]) if len(color) == 4 else None,
            })
            i += int(n)
        just = ed["ParagraphRun"]["RunArray"][0]["ParagraphSheet"]["Properties"].get("Justification", 0)
        return {
            "texto": t,
            "tramos": tramos,
            "alinear": {0: "inicio", 1: "fin", 2: "centro"}.get(int(just), "inicio"),
        }
    except Exception as e:  # noqa: BLE001 - es un inventario: se apunta y se sigue
        return {"error": str(e)}


def recorrer(psd, nombre, salida: Path, inventario):
    capas_dir = salida / "capas" / nombre
    capas_dir.mkdir(parents=True, exist_ok=True)

    def visitar(grupo, ruta, visible_padre):
        for capa in grupo:
            visible = visible_padre and capa.visible
            if capa.name in FUERA:
                continue
            camino = ruta + [capa.name]
            if capa.is_group():
                visitar(capa, camino, visible)
                continue
            if capa.bbox == (0, 0, 0, 0):
                continue
            # Las capas de recorte van compuestas con su base (abajo).
            if getattr(capa, "clipping", False):
                continue
            entrada = {
                "ruta": " / ".join(camino),
                "visible": visible,
                "mezcla": str(getattr(capa, "blend_mode", "")).replace("BlendMode.", "").lower(),
                "opacidad": round(capa.opacity / 255, 3),
                "bbox_px": list(capa.bbox),
            }
            if capa.kind == "type":
                entrada["tipo"] = "texto"
                entrada["zona"] = mm(*capa.bbox)
                entrada.update(texto(capa))
            else:
                compuesta = capa.has_effects() or bool(getattr(capa, "clip_layers", None))
                img = capa.composite() if compuesta else capa.topil()
                if img is None:
                    continue
                img = img.convert("RGBA")
                recorte, caja = recortar(img, capa.bbox)
                if recorte is None:
                    continue
                fichero = capas_dir / ("__".join(slug(p) for p in camino) + ".png")
                recorte.save(fichero, optimize=True)
                entrada["tipo"] = "imagen"
                entrada["fichero"] = str(fichero.relative_to(salida))
                entrada["zona"] = mm(*caja)
                entrada["efectos"] = bool(capa.has_effects())
                entrada["recortes"] = [c.name for c in getattr(capa, "clip_layers", []) or []]
            inventario.append(entrada)

    visitar(psd, [], True)


def recomponer(psd, salida: Path, nombre, inventario):
    """Lo visible del inventario, en orden, contra la composición del PSD."""
    lienzo = Image.new("RGBA", (CARTA[2] - CARTA[0], CARTA[3] - CARTA[1]), (0, 0, 0, 0))
    for e in inventario:
        if e.get("tipo") != "imagen" or not e["visible"] or e["mezcla"] not in ("normal", "pass_through"):
            continue
        img = Image.open(salida / e["fichero"]).convert("RGBA")
        if e["opacidad"] < 1:
            a = np.array(img)
            a[..., 3] = (a[..., 3] * e["opacidad"]).astype(np.uint8)
            img = Image.fromarray(a)
        z = e["zona"]
        x = round(z["x"] * PX_X)
        y = round(z["y"] * PX_Y)
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        capa.paste(img, (x, y))
        lienzo = Image.alpha_composite(lienzo, capa)
    def dentro(capa):
        # Lo mismo que se exporta: sin la ilustración, los textos, las ayudas
        # ni las capas con otra mezcla (el barrido va aparte).
        n = capa
        while n is not None and hasattr(n, "name"):
            if n.name in FUERA:
                return False
            n = n.parent
        if capa.kind == "type":
            return False
        modo = str(getattr(capa, "blend_mode", "")).replace("BlendMode.", "").lower()
        return capa.is_visible() and (capa.is_group() or modo in ("normal", "pass_through"))

    ref = psd.composite(ignore_preview=True, layer_filter=dentro).convert("RGBA").crop(CARTA)
    a = np.asarray(lienzo, dtype=np.int16)[..., :3]
    b = np.asarray(ref, dtype=np.int16)[..., :3]
    diff = float(np.abs(a - b).mean())
    vistas = salida / "fuente" / "vistas"
    vistas.mkdir(parents=True, exist_ok=True)
    ref.save(vistas / f"{nombre}-psd.png")
    lienzo.save(vistas / f"{nombre}-capas.png")
    return diff


def main():
    origen, salida = Path(sys.argv[1]), Path(sys.argv[2])
    todo = {}
    for fichero, nombre in PLANTILLAS.items():
        psd = PSDImage.open(origen / fichero)
        inventario = []
        recorrer(psd, nombre, salida, inventario)
        diff = recomponer(psd, salida, nombre, inventario)
        todo[nombre] = {"psd": fichero, "diferencia_media": round(diff, 2), "capas": inventario}
        print(f"{nombre}: {len(inventario)} capas, diferencia media {diff:.2f}/255")
    (salida / "fuente" / "inventario.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1))
    lineas = ["# Inventario de las plantillas Balatro", ""]
    for nombre, d in todo.items():
        lineas += [f"## {nombre} ({d['psd']}) — diferencia {d['diferencia_media']}/255", "",
                   "| Capa | Tipo | Visible | Mezcla | Zona (mm) | Fichero / texto |", "|---|---|---|---|---|---|"]
        for e in d["capas"]:
            z = e.get("zona", {})
            zona = f"{z.get('x')},{z.get('y')} {z.get('w')}×{z.get('h')}"
            extra = e.get("fichero") or repr(e.get("texto", ""))[:40]
            lineas.append(f"| {e['ruta']} | {e.get('tipo')} | {e['visible']} | {e['mezcla']} | {zona} | {extra} |")
        lineas.append("")
    (salida / "fuente" / "inventario.md").write_text("\n".join(lineas))


if __name__ == "__main__":
    main()
