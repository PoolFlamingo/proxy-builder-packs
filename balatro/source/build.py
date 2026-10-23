#!/usr/bin/env python3
"""Step D8 of the plan (phase D, Balatro): builds the pack from what
`convert.py` exported (layers and inventory).

    python -I build.py <pack folder> <Drive folder> <m6x11plus.ttf>

Writes into the pack folder:

- `symbols/`: the mana chips (W U B R G), {C}, {T} and the generic 0 to 20
  and X (the colourless chip with the number in m6x11plus, as in the PSD);
- `labels/`: the rarity, legendary and land-type pills, without the English
  text painted on them (the engine writes it in the design's language);
- `layers/common/`: the colour boxes next to the title, one per colour;
- `fonts/`: the font and its licence note;
- `extras/`: card backs, tokens, basic lands and ready-made cards from the
  Drive, cropped to the card area (without the 3 mm of bleed);
- `pack.json`.
"""

import collections
import re
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PACK = Path(sys.argv[1])
DRIVE = Path(sys.argv[2])
LETRA = Path(sys.argv[3])
INV = json.loads((PACK / "source" / "inventory.json").read_text())
CAPAS = PACK / "layers"

# Folder under `layers/` of the templates whose id is not already English
# (the ids stay as they are: saved designs refer to them).
FOLDERS = {"tierra": "land", "planeta": "planet", "espectral": "spectral", "vale": "voucher"}
IDS = {v: k for k, v in FOLDERS.items()}

# The font: capital height / body (704/1152) and PSD pixels per mm.
MAYUS = 704 / 1152
PX_MM = 1240 / 63


def cap(px):
    """The capital height in mm of a text of `px` in the PSD."""
    return round(px * MAYUS / PX_MM, 3)


def zona(plantilla, ruta):
    """The zone (mm) of layer `ruta` (as in the inventory) of a template."""
    for e in INV[plantilla]["capas"]:
        if e["ruta"] == ruta:
            return dict(e["zona"])
    raise KeyError(f"{plantilla}: {ruta}")


def ztexto(plantilla, ruta):
    """The zone of the **text** layer `ruta` (there are bars and texts with the same name)."""
    for e in INV[plantilla]["capas"]:
        if e["ruta"] == ruta and e.get("tipo") == "texto":
            return dict(e["zona"])
    raise KeyError(f"{plantilla}: texto {ruta}")


def fichero(plantilla, ruta):
    for e in INV[plantilla]["capas"]:
        if e["ruta"] == ruta:
            return e["fichero"]
    raise KeyError(f"{plantilla}: {ruta}")


def capa(plantilla, ruta, **extra):
    """A PNG layer of the pack in its zone."""
    c = {"png": fichero(plantilla, ruta), "en": zona(plantilla, ruta)}
    c.update(extra)
    return c


def toda(plantilla, ruta, **extra):
    """A layer that covers the whole card (no `en`)."""
    c = {"png": fichero(plantilla, ruta)}
    c.update(extra)
    return c


# ── Colours ────────────────────────────────────────────────────────────────

# The word of each palette in the file names (`{color}`).
PALABRA = {
    "W": "white", "U": "blue", "B": "black", "R": "red", "G": "green",
    "gold": "gold", "artifact": "colorless", "land": "colorless", "colorless": "colorless",
}
# The colour of each chip (its fill), for the title boxes.
FICHA = {
    "white": (235, 246, 248), "blue": (0, 156, 253), "black": (79, 99, 103),
    "red": (253, 95, 85), "green": (85, 163, 131), "colorless": (123, 123, 123),
    "gold": (241, 178, 68),
}


def hexa(c):
    return "#%02x%02x%02x" % c


# ── Symbols ───────────────────────────────────────────────────────────────

def simbolos():
    d = PACK / "symbols"
    d.mkdir(exist_ok=True)
    out = {}
    base = CAPAS / "joker"
    for codigo, nombre in [("W", "white"), ("U", "blue"), ("B", "black"), ("R", "red"), ("G", "green")]:
        shutil.copy(base / f"words__mana-10-pixels-apart__{nombre}.png", d / f"{codigo}.png")
        out[codigo] = f"symbols/{codigo}.png"
    incolora = Image.open(base / "words__mana-10-pixels-apart__colorless__colorless.png").convert("RGBA")
    # {C}: the colourless chip with the diamond (from the land template), at the size of the others.
    t = CAPAS / FOLDERS["tierra"]
    ficha = Image.open(t / "symbols__colorless-copy-4__colorless.png").convert("RGBA")
    rombo = Image.open(t / "symbols__colorless-copy-4__colorless-symbol.png").convert("RGBA")
    c = Image.new("RGBA", ficha.size)
    c.alpha_composite(ficha)
    zf = zona("tierra", "Symbols / Colorless copy 4 / Colorless")
    zr = zona("tierra", "Symbols / Colorless copy 4 / Colorless Symbol")
    c.alpha_composite(rombo, (round((zr["x"] - zf["x"]) * PX_MM), round((zr["y"] - zf["y"]) * PX_MM)))
    c.resize(incolora.size, Image.NEAREST).save(d / "C.png")
    out["C"] = "symbols/C.png"
    shutil.copy(base / "words__tap-symbol.png", d / "T.png")
    out["T"] = "symbols/T.png"
    # The generic: the colourless chip with the number (66 px in the PSD, white).
    letra = ImageFont.truetype(str(LETRA), 66)
    for n in [str(i) for i in range(21)] + ["X", "Y", "Z"]:
        im = incolora.copy()
        dib = ImageDraw.Draw(im)
        dib.fontmode = "1"  # no anti-aliasing: it is a pixel font
        x0, y0, x1, y1 = dib.textbbox((0, 0), n, font=letra)
        dib.text(((im.width - (x1 - x0)) / 2 - x0, (im.height - (y1 - y0)) / 2 - y0), n,
                 font=letra, fill=(255, 255, 255, 255))
        im.save(d / f"{n}.png")
        out[n] = f"symbols/{n}.png"
    return out


# ── Labels ──────────────────────────────────────────────────────────────

def limpiar_pastilla(origen: Path, destino: Path):
    """Removes the text of a pill: the inside, in the fill colour."""
    im = Image.open(origen).convert("RGBA")
    px = im.load()
    cuenta = collections.Counter(px[x, y] for y in range(im.height) for x in range(im.width) if px[x, y][3] == 255)
    relleno = cuenta.most_common(1)[0][0]
    for y in range(im.height):
        fila = [x for x in range(im.width) if px[x, y] == relleno]
        if len(fila) < im.width * 0.3:
            continue  # top and bottom edges
        a, b = fila[0], fila[-1]
        for x in range(a, b + 1):
            if px[x, y][3] == 255:
                px[x, y] = relleno
    im.save(destino)


ETIQUETAS = {
    # value: (source file, Spanish text, English text)
    "common": ("joker/words__legal__set__common.png", "Común", "Common"),
    "uncommon": ("joker/words__legal__set__uncomon.png", "Infrecuente", "Uncommon"),
    "rare": ("joker/words__legal__set__rare.png", "Rara", "Rare"),
    "mythic": ("joker/words__legal__set__mythic-rare.png", "Mítica", "Mythic"),
    "special": ("joker/words__legal__set__mythic-rare.png", "Especial", "Special"),
    "bonus": ("joker/words__legal__set__mythic-rare.png", "Bonus", "Bonus"),
    "legendary": ("joker/words__legal__set__mythic-rare.png", "Legendaria", "Legendary"),
    "plains": ("land/frame__basic-land-format__land-type__plains.png", "Llanura", "Plains"),
    "island": ("land/frame__basic-land-format__land-type__island.png", "Isla", "Island"),
    "swamp": ("land/frame__basic-land-format__land-type__swamp.png", "Pantano", "Swamp"),
    "mountain": ("land/frame__basic-land-format__land-type__mountain.png", "Montaña", "Mountain"),
    "forest": ("land/frame__basic-land-format__land-type__forest.png", "Bosque", "Forest"),
    "wastes": ("joker/words__legal__set__common.png", "Páramo", "Wastes"),
}


def etiquetas():
    d = PACK / "labels"
    d.mkdir(exist_ok=True)
    out = {}
    for valor, (origen, es, en) in ETIQUETAS.items():
        destino = d / f"{valor}.png"
        limpiar_pastilla(CAPAS / origen, destino)
        out[valor] = {"texto": {"es": es, "en": en}, "fondo": f"labels/{valor}.png", "color": "#ffffff"}
    return out


# ── Colour boxes of the title ────────────────────────────────────────────

def cuadros():
    """The boxes at the sides of the title (the «Color» layer of Spectral): one on
    the left (first colour) and one on the right (second), in each colour."""
    tira = Image.open(CAPAS / FOLDERS["espectral"] / "frame__color.png").convert("RGBA")
    d = CAPAS / "common"
    d.mkdir(exist_ok=True)
    mitad = tira.width // 2
    for palabra, color in FICHA.items():
        for lado, caja in (("left", (0, 0, mitad, tira.height)), ("right", (mitad, 0, tira.width, tira.height))):
            im = Image.new("RGBA", tira.size)
            trozo = tira.crop(caja)
            r, g, b, a = trozo.split()
            relleno = Image.new("RGBA", trozo.size, color + (255,))
            relleno.putalpha(a)
            im.paste(relleno, (caja[0], 0))
            im.save(d / f"box-{lado}-{palabra}.png")
    z = zona("espectral", "Frame / Color")
    return z


# ── Fonts and extras ────────────────────────────────────────────────────────

def letras():
    d = PACK / "fonts"
    d.mkdir(exist_ok=True)
    shutil.copy(LETRA, d / "m6x11plus.ttf")
    (d / "m6x11plus-LICENSE.txt").write_text(
        "m6x11plus — Daniel Linssen (managore).\n"
        "Licence (of the font itself): «Free to use with attribution».\n"
        "Used in Proxy Builder's Balatro pack with this credit.\n"
    )


CARTA = (62, 62, 1302, 1792)

# Folder under `extras/` of each extra type (the type values are the app's).
EXTRA_FOLDERS = {"reverso": "backs", "ficha": "tokens", "tierra": "lands", "carta": "cards"}


def extras():
    """The Drive images, cropped to the card, and their list."""
    lista = []
    d = PACK / "extras"
    for tipo, carpeta in [("reverso", "Cardbacks"), ("ficha", "Tokens"), ("carta", "Extra Cards")]:
        for f in sorted((DRIVE / carpeta).glob("*.png")):
            lista.append((tipo, f, f"{EXTRA_FOLDERS[tipo]}/{f.name}"))
    for f in sorted((DRIVE / "Basic Lands").glob("*/*.png")):
        lista.append(("tierra", f, f"{EXTRA_FOLDERS['tierra']}/{f.parent.name}/{f.name}"))
    for f in sorted(DRIVE.glob("*.png")):
        lista.append(("carta", f, f"{EXTRA_FOLDERS['carta']}/{f.name}"))
    out = []
    for tipo, origen, rel in lista:
        destino = d / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(origen).convert("RGBA")
        if im.size == (1365, 1855):
            im = im.crop(CARTA)
        im.save(destino, optimize=True)
        nombre = origen.stem.replace("_s ", "'s ").replace("_", " ")
        out.append({"ruta": rel, "tipo": tipo, "nombre": nombre})
    (PACK / "extras.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ── pack.json ──────────────────────────────────────────────────────────────

def hueco(z, **extra):
    h = {"x": z["x"], "y": z["y"], "w": z["w"], "h": z["h"]}
    h.update(extra)
    return h


def ampliar(z, dx=0.0, dy=0.0, dw=0.0, dh=0.0):
    return {"x": round(z["x"] + dx, 3), "y": round(z["y"] + dy, 3),
            "w": round(z["w"] + dw, 3), "h": round(z["h"] + dh, 3)}


TINTA = "#3f4a4d"      # the rules text
TITULO = "#4f6367"     # titles and type on light
AMARILLO = "#f5b244"   # P/T, loyalty, ability names
AZUL = "#0093ff"       # highlighted text


def coste_variable(plantilla, grupo):
    """The cost boxes for 1 to 6 symbols (those the template has)."""
    capas = []
    for e in INV[plantilla]["capas"]:
        r = e["ruta"]
        if r.startswith(grupo) and e.get("tipo") == "imagen":
            n = r.split("/")[-1].strip().split(" ")[0]
            if n.isdigit():
                # The one for N is used with N symbols; the one for 6, with 6 or more.
                rango = [int(n), int(n)] if n != "6" else [6, 20]
                capas.append(capa(plantilla, r, si={"simbolos": rango}))
    return capas


def opacidad(plantilla, ruta):
    for e in INV[plantilla]["capas"]:
        if e["ruta"] == ruta:
            return e.get("opacidad", 1.0)
    return 1.0


def barrido(plantilla):
    return [
        toda(plantilla, f"Small Scanlines / {c}", mezcla="oscurecer",
             opacidad=opacidad(plantilla, f"Small Scanlines / {c}"))
        for c in ("B", "G", "R", "Vertical")
    ]


def fin_de_barra(plantilla, ruta_barra, z_tipo):
    """Where (mm) the light bar of the type line ends, at the height of its
    text: the text is the same colour as the bar's dark edge, so whatever goes
    past that is not seen."""
    z = zona(plantilla, ruta_barra)
    img = Image.open(PACK / fichero(plantilla, ruta_barra)).convert("RGBA")
    k = img.width / z["w"]
    y = round((z_tipo["y"] + z_tipo["h"] / 2 - z["y"]) * k)
    x = round((z_tipo["x"] - z["x"]) * k)
    claro = lambda p: p[3] > 200 and (p[0] + p[1] + p[2]) / 3 > 150  # noqa: E731
    if not claro(img.getpixel((x, y))):
        raise ValueError(f"{plantilla}: the type text does not start on the light bar")
    while x < img.width - 1 and claro(img.getpixel((x + 1, y))):
        x += 1
    return z["x"] + (x + 1) / k


def tipo_hasta(z_tipo, z_pastilla, fin_barra=None, **extra):
    """The type line from its text to the pill (or to the end of its light
    bar, if that comes first)."""
    fin = z_pastilla["x"] - 0.6
    if fin_barra is not None:
        fin = min(fin, fin_barra - 0.5)
    return hueco({"x": z_tipo["x"], "y": z_tipo["y"], "w": round(fin - z_tipo["x"], 3),
                  "h": z_tipo["h"]}, **extra)


# The pack's footer: one line, like the templates' legal text
# («JOK • Balatro 001/001»), in two columns that follow each other (or the
# second at the tab stop, where there is one).
PLANTILLA_PIE = "{set} • {lang} {num} {rarity}\t{original} {brush} {artist}"


def pie(plantilla, ancho, color, x=None, y=None, tabs=None, px=40.91):
    """The footer on the line of the template's legal text (or at `x`, `y`)."""
    try:
        z = ztexto(plantilla, "Words / Legal / Set Identifier")
    except KeyError:
        z = {"x": x, "y": y}
    alto = 1.6
    return hueco({"x": z["x"] if x is None else x, "y": z["y"] if y is None else y, "w": ancho, "h": alto},
                 rol="pie", mayuscula=cap(px), color=color, tabs=tabs or [], interlinea=alto)


# ── The rules box that grows (as the author does card by card: with little
# text the type line goes down and the art gains room; with a lot, it goes up).
# The engine computes `yTipo` (top of the type bar) and whatever moves with it
# is given as expressions.

def en_y(y, ref):
    """`y` (mm, in the template) relative to the type bar at `ref`."""
    return f"yTipo{y - ref:+.3f}"


def con_tipo(h, ref):
    """A slot that moves with the type bar."""
    h = dict(h)
    h["y"] = en_y(h["y"], ref)
    return h


def movil(c, ref, hasta=None, tramos=None):
    """A layer that moves with the type bar; with `hasta`, its bottom edge
    stays at that mm (and it stretches in the middle)."""
    c = dict(c)
    z = dict(c["en"])
    off = z["y"] - ref
    z["y"] = en_y(z["y"], ref)
    if hasta is not None:
        z["h"] = f"{hasta - off:.3f}-yTipo"
    c["en"] = z
    if tramos:
        c["tramos"] = tramos
    return c


def caja(fondo, alto_min, alto_max, barra, arriba=0.8, abajo=0.8, comodo=None):
    """`comodo`: up to where the box grows before the text shrinks a little
    (to 85 %), so long rules do not eat the art."""
    extra = {"altoComodo": comodo} if comodo else {}
    return {**extra, "fondo": fondo, "altoMin": alto_min, "altoMax": alto_max, "barraTipo": barra,
            "padArriba": arriba, "padAbajo": abajo}


def comunes(z_cuadros):
    return {
        "cuadros": [
            {"png": "layers/common/box-left-{color1}.png", "en": z_cuadros},
            {"png": "layers/common/box-right-{color2}.png", "en": z_cuadros},
        ]
    }


def estilos(z_cuadros):
    c = comunes(z_cuadros)
    e = {}

    # ── Joker (creatures, artifacts…): dark frame, art on top.
    j = "joker"
    YJ = zona(j, "Frame / Typeline")["y"]
    e["joker"] = {
        "nombre": {"es": "Joker", "en": "Joker"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco(zona(j, "Frame / White Box")),
        "fondo": [
            toda(j, "Background"),
            toda(j, "Layer 37"),
            {"png": "layers/joker/backgrounds__{color}.png", "en": zona(j, "Backgrounds / Blue")},
        ],
        "capas": [
            toda(j, "Frame / Frame"),
            movil(capa(j, "Frame / Non-Legendary"), YJ, hasta=82.15, tramos=[1.6, 1.6]),
            movil(capa(j, "Frame / Typeline"), YJ),
            capa(j, "Frame / P/T", si={"fr": True}),
            *coste_variable(j, "Frame / Mana Box"),
            toda(j, "Layer 40"),
            *barrido(j),
        ],
        "huecos": {
            "titulo": hueco(zona(j, "Words / Name"), rol="titulo", mayuscula=cap(145), color="#ffffff", alinear="centro"),
            "coste": hueco({"x": 20.0, "y": 13.48, "w": 39.7, "h": 4.17}),
            "tipo": con_tipo(tipo_hasta(ztexto(j, "Words / Typeline"), zona(j, "Words / Legal / SET / Rare"), rol="tipo", mayuscula=cap(63), color="#ffffff"), YJ),
            "etiqueta": con_tipo(hueco(zona(j, "Words / Legal / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True), YJ),
            "reglas": hueco({"x": 4.5, "y": 57.0, "w": 54.0, "h": 20.0}, rol="reglas", mayuscula=cap(72), color=TINTA),
            "fr": hueco(zona(j, "Frame / P/T"), rol="fr", mayuscula=cap(95), color=AMARILLO, alinear="centro"),
            "pie": pie(j, 42.9, "#ffe5b4", px=50),
        },
        # The art is a fixed window of the frame: the box is never smaller than
        # the template's, it only grows with a lot of text.
        "caja": caja(81.3, 25.8, 40.0, 82.15 - 26.705 - YJ, 1.0, 1.0, comodo=30.0),
        "layouts": {"ficha": {}},
    }
    # Without P/T, the rules centred in the box (Arcane Signet).
    e["joker"]["huecos"]["reglas"]["alinear"] = "inicio"

    # ── Planeswalker: the Joker with the loyalty boxes.
    p = "planeswalker"
    e["planeswalker"] = json.loads(json.dumps(e["joker"]))
    e["planeswalker"]["nombre"] = {"es": "Planeswalker", "en": "Planeswalker"}
    # The loyalty boxes sit in fixed places: here the box does not move.
    del e["planeswalker"]["caja"]
    e["planeswalker"]["capas"] = [
        toda(p, "Frame / Frame"),
        capa(p, "Frame / Tick Seperator"),
        capa(p, "Frame / P/T", si={"fr": True}),
        *coste_variable(p, "Frame / Mana Box"),
        *barrido("joker"),
    ]
    e["planeswalker"]["huecos"]["tipo"] = tipo_hasta(ztexto(p, "Words / Legal / Typeline"), zona(p, "Words / Legal / SET / Mythic Rare"), rol="tipo", mayuscula=cap(69), color="#ffffff")
    e["planeswalker"]["huecos"]["etiqueta"] = hueco(zona(p, "Words / Legal / SET / Mythic Rare"), rol="tipo", mayuscula=cap(63), sombra=True, contenido="supertipo")
    e["planeswalker"]["huecos"]["reglas"] = hueco(
        {"x": 3.0, "y": zona(p, "Frame / Tick 1 Box")["y"], "w": 56.0,
         "h": 77.0 - zona(p, "Frame / Tick 1 Box")["y"]},
        rol="reglas", mayuscula=cap(60), color=TINTA)
    e["planeswalker"]["arte"] = hueco({"x": 2.23, "y": 14.24, "w": 58.53, "h": 26.5})

    # ── Spectral: light frame, full-card art, title on a nameplate.
    s = "espectral"
    YS = zona(s, "Frame / Typeline / Blue Typeline")["y"]
    e["espectral"] = {
        "nombre": {"es": "Espectral", "en": "Spectral"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 2.0, "y": 3.0, "w": 59.0, "h": 82.0}),
        "fondo": [toda(s, "Backgrounds / Background")],
        "capas": [
            toda(s, "Frame / Blue Frame"),
            movil(capa(s, "Frame / Blue Box"), YS, hasta=86.83),
            movil(capa(s, "Frame / Typeline / Blue Typeline"), YS),
            capa(s, "Frame / Mana Box / Mana Box 1-3"),
            *c["cuadros"],
        ],
        "huecos": {
            "titulo": hueco({**zona(s, "Words / Name"), "x": 9.6, "w": 43.8}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco(zona(s, "Frame / Mana Box / Mana Box 1-3"), alinear="centro"),
            "tipo": con_tipo(tipo_hasta(ztexto(s, "Frame / Typeline / Typeline"), zona(s, "Frame / Typeline / SET / Uncomon"), fin_de_barra(s, "Frame / Typeline / Blue Typeline", ztexto(s, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO), YS),
            "etiqueta": con_tipo(hueco(zona(s, "Frame / Typeline / SET / Uncomon"), rol="tipo", mayuscula=cap(63), sombra=True), YS),
            "reglas": hueco({"x": 6.5, "y": 65.0, "w": 50.0, "h": 19.0}, rol="reglas", mayuscula=cap(72), color=TITULO, alinear="centro"),
            "pie": pie(s, 51.0, "#bfc7d5"),
        },
        "caja": caja(82.0, 12.0, 42.0, 5.951, comodo=28.0),
        "layouts": {"ficha": {}},
    }
    # The cost: the chips inside the tab under the title.
    e["espectral"]["huecos"]["coste"] = hueco({"x": 10.0, "y": 12.05, "w": 43.0, "h": 4.17}, alinear="centro")

    # ── Tarot: golden frame, full-card art, rules on dark.
    t = "tarot"
    YT = zona(t, "Frame / Typeline / Typeline")["y"]
    e["tarot"] = {
        "nombre": {"es": "Tarot", "en": "Tarot"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 1.0, "y": 2.7, "w": 61.0, "h": 83.0}),
        "fondo": [toda(t, "Background copy")],
        "capas": [
            toda(t, "Frame / Frame"),
            movil({"png": fichero(t, "Frame / Rules Box"), "en": {**zona(t, "Frame / Rules Box"), "y": YT + 5.0}}, YT, hasta=88.0),
            movil({"png": fichero(t, "Frame / Typeline / Rules Extender"), "en": {**zona(t, "Frame / Typeline / Rules Extender"), "y": YT + 5.0}}, YT, hasta=83.0),
            movil(capa(t, "Frame / Typeline / Typeline"), YT),
        ],
        "huecos": {
            "titulo": hueco({**zona(t, "Words / Name"), "x": 4.0, "w": 55.0}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 10.0, "y": 10.94, "w": 43.0, "h": 4.17}, alinear="centro"),
            "tipo": con_tipo(tipo_hasta(ztexto(t, "Frame / Typeline / Typeline"), zona(t, "Frame / Typeline / SET / Rare"), fin_de_barra(t, "Frame / Typeline / Typeline", ztexto(t, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO), YT),
            "etiqueta": con_tipo(hueco(zona(t, "Frame / Typeline / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True), YT),
            "reglas": hueco({"x": 6.0, "y": 56.5, "w": 51.0, "h": 26.0}, rol="reglas", mayuscula=cap(70), color="#ffffff", alinear="centro"),
            "pie": pie(t, 53.0, "#a58547"),
        },
        "caja": caja(82.0, 12.0, 42.0, 5.951, comodo=28.0),
        "layouts": {"ficha": {}},
    }

    # ── Planet: turquoise background, the art floats between the nameplate and the type.
    pl = "planeta"
    YP = zona(pl, "Frame / Typeline / Expand Textbox / Typeline")["y"]
    e["planeta"] = {
        "nombre": {"es": "Planeta", "en": "Planet"},
        "base": "classic",
        "radio": 3.0,
        # The art reaches the type bar, wherever it is.
        "arte": hueco({"x": 6.0, "y": 29.5, "w": 51.0, "h": "yTipo-29.0"}),
        "fondo": [toda(pl, "Background copy")],
        "capas": [
            toda(pl, "Frame / Border"),
            capa(pl, "Frame / Flare"),
            capa(pl, "Frame / Nameplate"),
            capa(pl, "Frame / Mana Box / 1 Mana", si={"simbolos": [1, 2]}),
            capa(pl, "Frame / Mana Box / 3 Mana", si={"simbolos": [3, 20]}),
            movil(capa(pl, "Frame / Typeline / Expand Textbox / Extra Textbox"), YP, hasta=81.0),
            capa(pl, "Frame / Textbox"),
            movil(capa(pl, "Frame / Typeline / Expand Textbox / Typeline"), YP),
        ],
        "huecos": {
            "titulo": hueco({**zona(pl, "Words / Name"), "x": 9.6, "w": 43.8}, rol="titulo", mayuscula=cap(140), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 10.0, "y": 22.69, "w": 43.0, "h": 4.17}, alinear="centro"),
            "tipo": con_tipo(tipo_hasta(ztexto(pl, "Frame / Typeline / Typeline"), zona(pl, "Frame / Typeline / SET / Rare"), fin_de_barra(pl, "Frame / Typeline / Expand Textbox / Typeline", ztexto(pl, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO), YP),
            "etiqueta": con_tipo(hueco(zona(pl, "Frame / Typeline / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True), YP),
            "reglas": hueco({"x": 6.5, "y": 69.3, "w": 50.0, "h": 14.5}, rol="reglas", mayuscula=cap(70), color=TITULO),
            "pie": pie(pl, 51.0, "#dff5fc"),
        },
        # The bar never goes lower than where it covers the top edge of the fixed box.
        "caja": caja(83.6, 10.5, 37.5, 5.951, comodo=22.0),
        "layouts": {"ficha": {}},
    }

    # ── Voucher: white card with notches, nameplate on top with the cost.
    v = "vale"
    YV = zona(v, "Frame / Typeline / Typeline")["y"]
    e["vale"] = {
        "nombre": {"es": "Vale", "en": "Voucher"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 3.0, "y": 18.0, "w": 57.0, "h": "yTipo-17.0"}),
        "fondo": [toda(v, "Background copy"), capa(v, "Layer 26"), toda(v, "Layer 41")],
        "capas": [
            capa(v, "Frame / Border"),
            capa(v, "Frame / Nameplate", si={"variante": None} if False else {}),
            movil(capa(v, "Frame / Typeline / Rules Extender"), YV, hasta=79.404, tramos=[0.5, 3.0]),
            capa(v, "Frame / Rules Box"),
            movil(capa(v, "Frame / Typeline / Typeline"), YV),
            capa(v, "Frame / Color Match"),
        ],
        "huecos": {
            "titulo": hueco({**zona(v, "Words / Name"), "x": 4.5, "w": 54.0}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 20.0, "y": 3.61, "w": 39.04, "h": 4.17}),
            "tipo": con_tipo(tipo_hasta(ztexto(v, "Frame / Typeline / Typeline"), zona(v, "Frame / Typeline / SET / Uncomon"), fin_de_barra(v, "Frame / Typeline / Typeline", ztexto(v, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO), YV),
            "etiqueta": con_tipo(hueco(zona(v, "Frame / Typeline / SET / Uncomon"), rol="tipo", mayuscula=cap(63), sombra=True), YV),
            "reglas": hueco({"x": 4.5, "y": 68.3, "w": 54.0, "h": 15.8}, rol="reglas", mayuscula=cap(72), color=TITULO, alinearV="inicio"),
            "pie": pie(v, 58.5, "#ffffff", tabs=[36.3]),
        },
        # Above the bottom notch.
        "caja": caja(80.6, 11.0, 40.0, 6.918, comodo=22.0),
        "layouts": {"ficha": {}},
    }
    # The light or dark nameplate depending on the variant.
    capas_v = e["vale"]["capas"]
    capas_v[1] = capa(v, "Frame / Nameplate")


    # ── Land: basic (playing-card corners) and non-basic (rules above the type).
    ti = "tierra"
    YTI = zona(ti, "Frame / Non-Basic Land Format / Box Extension")["y"]
    e["tierra"] = {
        "nombre": {"es": "Tierra", "en": "Land"},
        "base": "fullArt",
        "radio": 3.0,
        "arte": hueco({"x": 3.0, "y": 13.5, "w": 57.0, "h": "yTipo-11.5"}),
        "fondo": [toda(ti, "Background copy"), toda(ti, "Layer 39")],
        "capas": [
            # The rules box sits above the type bar and grows upwards: here
            # `yTipo` is its top edge (bar 0).
            movil(capa(ti, "Frame / Non-Basic Land Format / Box Extension"), YTI, hasta=75.5, tramos=[1.6, 0.0]),
            capa(ti, "Frame / Non-Basic Land Format / Rules Box"),
            capa(ti, "Frame / Basic Land Format / Typeline"),
            capa(ti, "Frame / Non-Basic Land Format / Name Plate"),
            *c["cuadros"],
        ],
        "huecos": {
            "titulo": hueco({**zona(ti, "Frame / Non-Basic Land Format / Name"), "x": 9.6, "w": 43.8}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "tipo": tipo_hasta(ztexto(ti, "Frame / Basic Land Format / Typeline"), zona(ti, "Frame / Non-Basic Land Format / SET / Rare"), fin_de_barra(ti, "Frame / Basic Land Format / Typeline", ztexto(ti, "Frame / Basic Land Format / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO),
            "etiqueta": hueco(zona(ti, "Frame / Non-Basic Land Format / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 6.5, "y": 60.5, "w": 50.0, "h": 18.5}, rol="reglas", mayuscula=cap(72), color=TINTA, alinear="centro"),
            "pie": pie(ti, 51.0, TITULO, x=5.8, y=86.0),
            # Lands have no cost; if it is another card, under the nameplate.
            "coste": hueco({"x": 30.0, "y": 14.8, "w": 30.0, "h": 4.17}, alinear="fin"),
        },
        "caja": caja(79.3, 12.0, 46.0, 0.0, 1.4, 0.6, comodo=28.0),
        "layoutSi": [{"si": {"basica": True}, "layout": "basica"}],
        "layouts": {
            "basica": {
                "arte": hueco({"x": 3.0, "y": 3.0, "w": 57.0, "h": 76.0}),
                "fondo": [toda(ti, "Background copy"), toda(ti, "Backgrounds / Basic")],
                "capas": [
                    capa(ti, "Frame / Basic Land Format / Typeline"),
                ],
                "huecos": {
                    "titulo": hueco({"x": 0, "y": 0, "w": 0, "h": 0}, rol="titulo"),
                    "simbolo": hueco(zona(ti, "Frame / Basic Land Format / Parts / Chips / Red Chip")),
                    "etiqueta": hueco(zona(ti, "Frame / Basic Land Format / Land Type / Mountain"), rol="tipo", mayuscula=cap(63), sombra=True, contenido="subtipoTierra"),
                },
            },
            "ficha": {},
        },
    }
    return e


def paletas():
    """The pack's palettes (for the fallback SVG variables and the ink)."""
    def p(claro, medio, oscuro):
        return {"claro": claro, "medio": medio, "oscuro": oscuro, "tinte": claro,
                "caja": "#e6edf2", "tinta": TINTA}
    return {
        "W": p("#f6f2e4", "#ebf6f8", "#9aa7aa"),
        "U": p("#bfe4ff", "#009cfd", "#16557f"),
        "B": p("#9aa9ad", "#4f6367", "#2b3638"),
        "R": p("#ffd0cc", "#fd5f55", "#8a2f2a"),
        "G": p("#cdeee0", "#55a383", "#2d5c49"),
        "gold": p("#ffe5b4", "#f1b244", "#8a6420"),
        "artifact": p("#e3e3e3", "#7b7b7b", "#444444"),
        "land": p("#e3e3e3", "#7b7b7b", "#444444"),
        "colorless": p("#e3e3e3", "#7b7b7b", "#444444"),
    }


def podar(pack):
    """Leaves in `layers/` only the PNGs that `pack.json` uses (with `{color}`,
    `{color1}` and `{color2}` in every colour)."""
    texto = json.dumps(pack)
    usados = set()
    for ruta in set(re.findall(r'"(layers/[^"]+\.png)"', texto)):
        variantes = [ruta]
        for marca in ("{color}", "{color1}", "{color2}"):
            variantes = [v.replace(marca, p) for v in variantes for p in set(PALABRA.values())] \
                if any(marca in v for v in variantes) else variantes
        usados.update(variantes)
    quitados = 0
    for f in CAPAS.rglob("*.png"):
        if str(f.relative_to(PACK)) not in usados:
            f.unlink()
            quitados += 1
    print("unused layers removed:", quitados)


def en_orden_del_psd(pack):
    """The layers of each style (and of its layouts) in the order of the PSD
    they come from, bottom to top: otherwise a box that is under the frame in
    the PSD would cover it. Those that do not come from a PSD (the colour
    boxes) go on top."""
    def orden(c):
        ruta = c.get("png") or c.get("svg") or ""
        partes = ruta.split("/")
        if len(partes) >= 3 and partes[0] == "layers" and IDS.get(partes[1], partes[1]) in INV:
            # `{color}` in the path: the one of any colour will do.
            patron = re.compile(re.escape(ruta).replace(r"\{color\}", "[^/]+"))
            for i, e in enumerate(INV[IDS.get(partes[1], partes[1])]["capas"]):
                if patron.fullmatch(e.get("fichero") or ""):
                    return i
        return 10_000
    for e in pack["estilos"].values():
        for lista in [e.get("fondo", []), e["capas"]] + [l.get("capas") or [] for l in e.get("layouts", {}).values()]:
            lista.sort(key=orden)


def main():
    sim = simbolos()
    eti = etiquetas()
    z_cuadros = cuadros()
    letras()
    extras()
    letra = {"familia": "m6x11plus", "peso": 400, "mayuscula": round(MAYUS, 4)}
    pack = {
        "id": "balatro",
        "nombre": "Balatro",
        "version": 2,
        "origen": "Balatro templates (fan art; Balatro belongs to LocalThunk/Playstack) · m6x11plus font by Daniel Linssen",
        "escalado": "pixel",
        "colores": PALABRA,
        "paletas": paletas(),
        "letras": {r: dict(letra) for r in ("titulo", "tipo", "reglas", "fr", "pie", "cinta")},
        "simbolos": sim,
        "separacionCoste": round(10 / 82, 3),
        "plantillaPie": {"es": PLANTILLA_PIE, "en": PLANTILLA_PIE},
        "etiquetas": eti,
        "coloresTexto": {"resalte": AZUL, "habilidad": AMARILLO},
        "insignias": {"fondo": "#3f4a4d", "borde": "#2b3638", "texto": AMARILLO,
                      "pngLealtad": "layers/planeswalker/frame__tick-1-box.png"},
        "sustituir": {"—": "-", "–": "-", "−": "-", "•": "-", "·": "-", "’": "'", "“": "\"", "”": "\""},
        "estilos": estilos(z_cuadros),
    }
    en_orden_del_psd(pack)
    # The pack-level layouts (saga, class, dungeon, flip…): see `layouts.py`.
    sys.path.insert(0, str(Path(__file__).parent))
    from layouts import layouts
    pack["layouts"] = layouts()
    (PACK / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    podar(pack)
    print("pack.json:", len(pack["estilos"]), "styles,", len(sim), "symbols,", len(eti), "labels")


if __name__ == "__main__":
    main()
