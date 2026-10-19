#!/usr/bin/env python3
"""Paso D8 del plan (Fase D, Balatro): monta el pack a partir de lo que exportó
`convertir.py` (capas e inventario).

    python -I construir.py <carpeta del pack> <carpeta del Drive> <m6x11plus.ttf>

Escribe en la carpeta del pack:

- `simbolos/`: las fichas de maná (W U B R G), {C}, {T} y el genérico del 0 al
  20 y X (la ficha incolora con el número en m6x11plus, como en el PSD);
- `etiquetas/`: las pastillas de rareza, legendaria y tipos de tierra, sin el
  texto en inglés que traen pintado (lo pone el motor en el idioma del diseño);
- `capas/comun/`: los cuadros de color junto al título, uno por color;
- `letras/`: la letra y su nota de licencia;
- `extras/`: reversos, fichas, tierras básicas y cartas hechas del Drive,
  recortadas al área de la carta (sin los 3 mm de sangrado);
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
INV = json.loads((PACK / "fuente" / "inventario.json").read_text())
CAPAS = PACK / "capas"

# La letra: altura de mayúscula / cuerpo (704/1152) y píxeles por mm del PSD.
MAYUS = 704 / 1152
PX_MM = 1240 / 63


def cap(px):
    """La altura de mayúscula en mm de un texto de `px` del PSD."""
    return round(px * MAYUS / PX_MM, 3)


def zona(plantilla, ruta):
    """La zona (mm) de la capa `ruta` (como en el inventario) de una plantilla."""
    for e in INV[plantilla]["capas"]:
        if e["ruta"] == ruta:
            return dict(e["zona"])
    raise KeyError(f"{plantilla}: {ruta}")


def ztexto(plantilla, ruta):
    """La zona de la capa de **texto** `ruta` (hay barras y textos con el mismo nombre)."""
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
    """Una capa PNG del pack en su zona."""
    c = {"png": fichero(plantilla, ruta), "en": zona(plantilla, ruta)}
    c.update(extra)
    return c


def toda(plantilla, ruta, **extra):
    """Una capa que cubre la carta entera (sin `en`)."""
    c = {"png": fichero(plantilla, ruta)}
    c.update(extra)
    return c


# ── Colores ────────────────────────────────────────────────────────────────

# La palabra de cada paleta en los nombres de fichero (`{color}`).
PALABRA = {
    "W": "white", "U": "blue", "B": "black", "R": "red", "G": "green",
    "gold": "gold", "artifact": "colorless", "land": "colorless", "colorless": "colorless",
}
# El color de cada ficha (el de su relleno), para los cuadros del título.
FICHA = {
    "white": (235, 246, 248), "blue": (0, 156, 253), "black": (79, 99, 103),
    "red": (253, 95, 85), "green": (85, 163, 131), "colorless": (123, 123, 123),
    "gold": (241, 178, 68),
}


def hexa(c):
    return "#%02x%02x%02x" % c


# ── Símbolos ───────────────────────────────────────────────────────────────

def simbolos():
    d = PACK / "simbolos"
    d.mkdir(exist_ok=True)
    out = {}
    base = CAPAS / "joker"
    for codigo, nombre in [("W", "white"), ("U", "blue"), ("B", "black"), ("R", "red"), ("G", "green")]:
        shutil.copy(base / f"words__mana-10-pixels-apart__{nombre}.png", d / f"{codigo}.png")
        out[codigo] = f"simbolos/{codigo}.png"
    incolora = Image.open(base / "words__mana-10-pixels-apart__colorless__colorless.png").convert("RGBA")
    # {C}: la ficha incolora con el rombo (de la plantilla de tierra), al tamaño de las demás.
    t = CAPAS / "tierra"
    ficha = Image.open(t / "symbols__colorless-copy-4__colorless.png").convert("RGBA")
    rombo = Image.open(t / "symbols__colorless-copy-4__colorless-symbol.png").convert("RGBA")
    c = Image.new("RGBA", ficha.size)
    c.alpha_composite(ficha)
    zf = zona("tierra", "Symbols / Colorless copy 4 / Colorless")
    zr = zona("tierra", "Symbols / Colorless copy 4 / Colorless Symbol")
    c.alpha_composite(rombo, (round((zr["x"] - zf["x"]) * PX_MM), round((zr["y"] - zf["y"]) * PX_MM)))
    c.resize(incolora.size, Image.NEAREST).save(d / "C.png")
    out["C"] = "simbolos/C.png"
    shutil.copy(base / "words__tap-symbol.png", d / "T.png")
    out["T"] = "simbolos/T.png"
    # El genérico: la ficha incolora con el número (66 px en el PSD, blanco).
    letra = ImageFont.truetype(str(LETRA), 66)
    for n in [str(i) for i in range(21)] + ["X", "Y", "Z"]:
        im = incolora.copy()
        dib = ImageDraw.Draw(im)
        dib.fontmode = "1"  # sin suavizar: es una letra de píxeles
        x0, y0, x1, y1 = dib.textbbox((0, 0), n, font=letra)
        dib.text(((im.width - (x1 - x0)) / 2 - x0, (im.height - (y1 - y0)) / 2 - y0), n,
                 font=letra, fill=(255, 255, 255, 255))
        im.save(d / f"{n}.png")
        out[n] = f"simbolos/{n}.png"
    return out


# ── Etiquetas ──────────────────────────────────────────────────────────────

def limpiar_pastilla(origen: Path, destino: Path):
    """Quita el texto de una pastilla: el interior, del color de relleno."""
    im = Image.open(origen).convert("RGBA")
    px = im.load()
    cuenta = collections.Counter(px[x, y] for y in range(im.height) for x in range(im.width) if px[x, y][3] == 255)
    relleno = cuenta.most_common(1)[0][0]
    for y in range(im.height):
        fila = [x for x in range(im.width) if px[x, y] == relleno]
        if len(fila) < im.width * 0.3:
            continue  # bordes de arriba y abajo
        a, b = fila[0], fila[-1]
        for x in range(a, b + 1):
            if px[x, y][3] == 255:
                px[x, y] = relleno
    im.save(destino)


ETIQUETAS = {
    # valor: (fichero de origen, texto es, texto en)
    "common": ("joker/words__legal__set__common.png", "Común", "Common"),
    "uncommon": ("joker/words__legal__set__uncomon.png", "Infrecuente", "Uncommon"),
    "rare": ("joker/words__legal__set__rare.png", "Rara", "Rare"),
    "mythic": ("joker/words__legal__set__mythic-rare.png", "Mítica", "Mythic"),
    "special": ("joker/words__legal__set__mythic-rare.png", "Especial", "Special"),
    "bonus": ("joker/words__legal__set__mythic-rare.png", "Bonus", "Bonus"),
    "legendary": ("joker/words__legal__set__mythic-rare.png", "Legendaria", "Legendary"),
    "plains": ("tierra/frame__basic-land-format__land-type__plains.png", "Llanura", "Plains"),
    "island": ("tierra/frame__basic-land-format__land-type__island.png", "Isla", "Island"),
    "swamp": ("tierra/frame__basic-land-format__land-type__swamp.png", "Pantano", "Swamp"),
    "mountain": ("tierra/frame__basic-land-format__land-type__mountain.png", "Montaña", "Mountain"),
    "forest": ("tierra/frame__basic-land-format__land-type__forest.png", "Bosque", "Forest"),
    "wastes": ("joker/words__legal__set__common.png", "Páramo", "Wastes"),
}


def etiquetas():
    d = PACK / "etiquetas"
    d.mkdir(exist_ok=True)
    out = {}
    for valor, (origen, es, en) in ETIQUETAS.items():
        destino = d / f"{valor}.png"
        limpiar_pastilla(CAPAS / origen, destino)
        out[valor] = {"texto": {"es": es, "en": en}, "fondo": f"etiquetas/{valor}.png", "color": "#ffffff"}
    return out


# ── Cuadros de color del título ────────────────────────────────────────────

def cuadros():
    """Los cuadros a los lados del título (capa «Color» de Espectral): uno a
    la izquierda (primer color) y otro a la derecha (segundo), en cada color."""
    tira = Image.open(CAPAS / "espectral" / "frame__color.png").convert("RGBA")
    d = CAPAS / "comun"
    d.mkdir(exist_ok=True)
    mitad = tira.width // 2
    for palabra, color in FICHA.items():
        for lado, caja in (("izq", (0, 0, mitad, tira.height)), ("der", (mitad, 0, tira.width, tira.height))):
            im = Image.new("RGBA", tira.size)
            trozo = tira.crop(caja)
            r, g, b, a = trozo.split()
            relleno = Image.new("RGBA", trozo.size, color + (255,))
            relleno.putalpha(a)
            im.paste(relleno, (caja[0], 0))
            im.save(d / f"cuadro-{lado}-{palabra}.png")
    z = zona("espectral", "Frame / Color")
    return z


# ── Letras y extras ────────────────────────────────────────────────────────

def letras():
    d = PACK / "letras"
    d.mkdir(exist_ok=True)
    shutil.copy(LETRA, d / "m6x11plus.ttf")
    (d / "m6x11plus-LICENCIA.txt").write_text(
        "m6x11plus — Daniel Linssen (managore).\n"
        "Licencia (de la propia letra): «Free to use with attribution».\n"
        "Se usa en el pack Balatro de Proxy Builder con este crédito.\n"
    )


CARTA = (62, 62, 1302, 1792)


def extras():
    """Las imágenes del Drive, recortadas a la carta, y su lista."""
    lista = []
    d = PACK / "extras"
    for tipo, carpeta in [("reverso", "Cardbacks"), ("ficha", "Tokens"), ("carta", "Extra Cards")]:
        for f in sorted((DRIVE / carpeta).glob("*.png")):
            lista.append((tipo, f, f"{tipo}s/{f.name}"))
    for f in sorted((DRIVE / "Basic Lands").glob("*/*.png")):
        lista.append(("tierra", f, f"tierras/{f.parent.name}/{f.name}"))
    for f in sorted(DRIVE.glob("*.png")):
        lista.append(("carta", f, f"cartas/{f.name}"))
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


TINTA = "#3f4a4d"      # el texto de las reglas
TITULO = "#4f6367"     # títulos y tipo sobre claro
AMARILLO = "#f5b244"   # F/R, lealtad, nombres de habilidad
AZUL = "#0093ff"       # lo resaltado


def coste_variable(plantilla, grupo):
    """Las cajas del coste de 1 a 6 símbolos (las que tenga la plantilla)."""
    capas = []
    for e in INV[plantilla]["capas"]:
        r = e["ruta"]
        if r.startswith(grupo) and e.get("tipo") == "imagen":
            n = r.split("/")[-1].strip().split(" ")[0]
            if n.isdigit():
                # La de N se usa con N símbolos; la de 6, con 6 o más.
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
    """Dónde acaba (mm) la barra clara de la línea de tipo, a la altura de su
    texto: el texto es del mismo color que el borde oscuro de la barra, así que
    lo que pase de ahí no se ve."""
    z = zona(plantilla, ruta_barra)
    img = Image.open(PACK / fichero(plantilla, ruta_barra)).convert("RGBA")
    k = img.width / z["w"]
    y = round((z_tipo["y"] + z_tipo["h"] / 2 - z["y"]) * k)
    x = round((z_tipo["x"] - z["x"]) * k)
    claro = lambda p: p[3] > 200 and (p[0] + p[1] + p[2]) / 3 > 150  # noqa: E731
    if not claro(img.getpixel((x, y))):
        raise ValueError(f"{plantilla}: el texto del tipo no empieza en la barra clara")
    while x < img.width - 1 and claro(img.getpixel((x + 1, y))):
        x += 1
    return z["x"] + (x + 1) / k


def tipo_hasta(z_tipo, z_pastilla, fin_barra=None, **extra):
    """La línea de tipo desde su texto hasta la pastilla (o hasta el final de
    su barra clara, si acaba antes)."""
    fin = z_pastilla["x"] - 0.6
    if fin_barra is not None:
        fin = min(fin, fin_barra - 0.5)
    return hueco({"x": z_tipo["x"], "y": z_tipo["y"], "w": round(fin - z_tipo["x"], 3),
                  "h": z_tipo["h"]}, **extra)


def pie(y, color, alto=3.3):
    """El pie de dos líneas (número, rareza y original; set, idioma y artista)."""
    return hueco({"x": 4.5, "y": y, "w": 50.0, "h": alto}, rol="pie", mayuscula=1.15, color=color,
                 tabs=[8.0, 10.6], interlinea=1.6)


def comunes(z_cuadros):
    return {
        "cuadros": [
            {"png": "capas/comun/cuadro-izq-{color1}.png", "en": z_cuadros},
            {"png": "capas/comun/cuadro-der-{color2}.png", "en": z_cuadros},
        ]
    }


def estilos(z_cuadros):
    c = comunes(z_cuadros)
    e = {}

    # ── Joker (criaturas, artefactos…): marco oscuro, arte arriba.
    j = "joker"
    e["joker"] = {
        "nombre": {"es": "Joker", "en": "Joker"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco(zona(j, "Frame / White Box")),
        "fondo": [
            toda(j, "Background"),
            toda(j, "Layer 37"),
            {"png": "capas/joker/backgrounds__{color}.png", "en": zona(j, "Backgrounds / Blue")},
        ],
        "capas": [
            toda(j, "Frame / Frame"),
            capa(j, "Frame / Non-Legendary"),
            capa(j, "Frame / Typeline"),
            capa(j, "Frame / P/T", si={"fr": True}),
            *coste_variable(j, "Frame / Mana Box"),
            toda(j, "Layer 40"),
            *barrido(j),
        ],
        "huecos": {
            "titulo": hueco(zona(j, "Words / Name"), rol="titulo", mayuscula=cap(145), color="#ffffff", alinear="centro"),
            "coste": hueco({"x": 20.0, "y": 13.48, "w": 39.7, "h": 4.17}),
            "tipo": tipo_hasta(ztexto(j, "Words / Typeline"), zona(j, "Words / Legal / SET / Rare"), rol="tipo", mayuscula=cap(63), color="#ffffff"),
            "etiqueta": hueco(zona(j, "Words / Legal / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 4.5, "y": 57.0, "w": 54.0, "h": 20.0}, rol="reglas", mayuscula=cap(72), color=TINTA),
            "fr": hueco(zona(j, "Frame / P/T"), rol="fr", mayuscula=cap(95), color=AMARILLO, alinear="centro"),
            "pie": pie(82.3, "#ffe5b4"),
        },
        "layouts": {"ficha": {}},
    }
    # Sin F/R, las reglas centradas en la caja (Arcane Signet).
    e["joker"]["huecos"]["reglas"]["alinear"] = "inicio"

    # ── Planeswalker: el Joker con las casillas de lealtad.
    p = "planeswalker"
    e["planeswalker"] = json.loads(json.dumps(e["joker"]))
    e["planeswalker"]["nombre"] = {"es": "Planeswalker", "en": "Planeswalker"}
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

    # ── Espectral: marco claro, arte a toda la carta, título en cartel.
    s = "espectral"
    e["espectral"] = {
        "nombre": {"es": "Espectral", "en": "Spectral"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 2.0, "y": 3.0, "w": 59.0, "h": 82.0}),
        "fondo": [toda(s, "Backgrounds / Background")],
        "capas": [
            toda(s, "Frame / Blue Frame"),
            capa(s, "Frame / Blue Box"),
            capa(s, "Frame / Typeline / Blue Typeline"),
            capa(s, "Frame / Mana Box / Mana Box 1-3"),
            *c["cuadros"],
        ],
        "huecos": {
            "titulo": hueco({**zona(s, "Words / Name"), "x": 9.6, "w": 43.8}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco(zona(s, "Frame / Mana Box / Mana Box 1-3"), alinear="centro"),
            "tipo": tipo_hasta(ztexto(s, "Frame / Typeline / Typeline"), zona(s, "Frame / Typeline / SET / Uncomon"), fin_de_barra(s, "Frame / Typeline / Blue Typeline", ztexto(s, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO),
            "etiqueta": hueco(zona(s, "Frame / Typeline / SET / Uncomon"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 4.5, "y": 65.0, "w": 54.0, "h": 19.0}, rol="reglas", mayuscula=cap(72), color=TITULO, alinear="centro"),
            "pie": pie(84.2, "#bfc7d5", 3.0),
        },
        "layouts": {"ficha": {}},
    }
    # El coste: las fichas dentro de la pestaña bajo el título.
    e["espectral"]["huecos"]["coste"] = hueco({"x": 10.0, "y": 12.05, "w": 43.0, "h": 4.17}, alinear="centro")

    # ── Tarot: marco dorado, arte a toda la carta, reglas sobre oscuro.
    t = "tarot"
    e["tarot"] = {
        "nombre": {"es": "Tarot", "en": "Tarot"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 1.0, "y": 2.7, "w": 61.0, "h": 83.0}),
        "fondo": [toda(t, "Background copy")],
        "capas": [
            toda(t, "Frame / Frame"),
            capa(t, "Frame / Rules Box"),
            capa(t, "Frame / Typeline / Rules Extender"),
            capa(t, "Frame / Typeline / Typeline"),
        ],
        "huecos": {
            "titulo": hueco({**zona(t, "Words / Name"), "x": 4.0, "w": 55.0}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 10.0, "y": 10.94, "w": 43.0, "h": 4.17}, alinear="centro"),
            "tipo": tipo_hasta(ztexto(t, "Frame / Typeline / Typeline"), zona(t, "Frame / Typeline / SET / Rare"), fin_de_barra(t, "Frame / Typeline / Typeline", ztexto(t, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO),
            "etiqueta": hueco(zona(t, "Frame / Typeline / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 6.0, "y": 56.5, "w": 51.0, "h": 26.0}, rol="reglas", mayuscula=cap(70), color="#ffffff", alinear="centro"),
            "pie": pie(84.2, "#dab772", 3.0),
        },
        "layouts": {"ficha": {}},
    }

    # ── Planeta: fondo turquesa, el arte flota entre el cartel y el tipo.
    pl = "planeta"
    e["planeta"] = {
        "nombre": {"es": "Planeta", "en": "Planet"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 6.0, "y": 29.5, "w": 51.0, "h": 31.0}),
        "fondo": [toda(pl, "Background copy")],
        "capas": [
            toda(pl, "Frame / Border"),
            capa(pl, "Frame / Flare"),
            capa(pl, "Frame / Nameplate"),
            capa(pl, "Frame / Mana Box / 1 Mana", si={"simbolos": [1, 2]}),
            capa(pl, "Frame / Mana Box / 3 Mana", si={"simbolos": [3, 20]}),
            capa(pl, "Frame / Typeline / Expand Textbox / Extra Textbox"),
            capa(pl, "Frame / Textbox"),
            capa(pl, "Frame / Typeline / Expand Textbox / Typeline"),
        ],
        "huecos": {
            "titulo": hueco({**zona(pl, "Words / Name"), "x": 9.6, "w": 43.8}, rol="titulo", mayuscula=cap(140), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 10.0, "y": 22.69, "w": 43.0, "h": 4.17}, alinear="centro"),
            "tipo": tipo_hasta(ztexto(pl, "Frame / Typeline / Typeline"), zona(pl, "Frame / Typeline / SET / Rare"), fin_de_barra(pl, "Frame / Typeline / Expand Textbox / Typeline", ztexto(pl, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO),
            "etiqueta": hueco(zona(pl, "Frame / Typeline / SET / Rare"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 6.5, "y": 69.3, "w": 50.0, "h": 14.5}, rol="reglas", mayuscula=cap(70), color=TITULO),
            "pie": pie(84.2, "#dff5fc", 3.0),
        },
        "layouts": {"ficha": {}},
    }

    # ── Vale: carta blanca con muescas, cartel arriba con el coste.
    v = "vale"
    e["vale"] = {
        "nombre": {"es": "Vale", "en": "Voucher"},
        "base": "classic",
        "radio": 3.0,
        "arte": hueco({"x": 3.0, "y": 18.0, "w": 57.0, "h": 43.0}),
        "fondo": [toda(v, "Background copy"), capa(v, "Layer 26"), toda(v, "Layer 41")],
        "capas": [
            capa(v, "Frame / Border"),
            capa(v, "Frame / Nameplate", si={"variante": None} if False else {}),
            capa(v, "Frame / Typeline / Rules Extender"),
            capa(v, "Frame / Rules Box"),
            capa(v, "Frame / Typeline / Typeline"),
            capa(v, "Frame / Color Match"),
        ],
        "huecos": {
            "titulo": hueco({**zona(v, "Words / Name"), "x": 4.5, "w": 54.0}, rol="titulo", mayuscula=cap(150), color=TITULO, alinear="centro", mayusculas=True),
            "coste": hueco({"x": 20.0, "y": 3.61, "w": 39.04, "h": 4.17}),
            "tipo": tipo_hasta(ztexto(v, "Frame / Typeline / Typeline"), zona(v, "Frame / Typeline / SET / Uncomon"), fin_de_barra(v, "Frame / Typeline / Typeline", ztexto(v, "Frame / Typeline / Typeline")), rol="tipo", mayuscula=cap(75), color=TITULO),
            "etiqueta": hueco(zona(v, "Frame / Typeline / SET / Uncomon"), rol="tipo", mayuscula=cap(63), sombra=True),
            "reglas": hueco({"x": 4.5, "y": 68.3, "w": 54.0, "h": 15.8}, rol="reglas", mayuscula=cap(72), color=TITULO, alinearV="inicio"),
            "pie": pie(84.1, "#ffffff", 3.0),
        },
        "layouts": {"ficha": {}},
    }
    # El cartel claro u oscuro según la variante.
    capas_v = e["vale"]["capas"]
    capas_v[1] = capa(v, "Frame / Nameplate")


    # ── Tierra: básica (esquinas de naipe) y no básica (reglas sobre el tipo).
    ti = "tierra"
    e["tierra"] = {
        "nombre": {"es": "Tierra", "en": "Land"},
        "base": "fullArt",
        "radio": 3.0,
        "arte": hueco({"x": 3.0, "y": 13.5, "w": 57.0, "h": 52.0}),
        "fondo": [toda(ti, "Background copy"), toda(ti, "Layer 39")],
        "capas": [
            capa(ti, "Frame / Non-Basic Land Format / Box Extension"),
            capa(ti, "Frame / Non-Basic Land Format / Layer 30"),
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
            "pie": pie(84.2, "#ffffff", 3.0),
        },
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
    """Las paletas del pack (para las variables de los SVG de respaldo y la tinta)."""
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
    """Deja en `capas/` solo los PNG que usa `pack.json` (con `{color}`,
    `{color1}` y `{color2}` en cada color)."""
    texto = json.dumps(pack)
    usados = set()
    for ruta in set(re.findall(r'"(capas/[^"]+\.png)"', texto)):
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
    print("capas sin usar quitadas:", quitados)


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
        "origen": "Plantillas Balatro (arte de fans; Balatro es de LocalThunk/Playstack) · letra m6x11plus de Daniel Linssen",
        "escalado": "pixel",
        "colores": PALABRA,
        "paletas": paletas(),
        "letras": {r: dict(letra) for r in ("titulo", "tipo", "reglas", "fr", "pie", "cinta")},
        "simbolos": sim,
        "separacionCoste": round(10 / 82, 3),
        "etiquetas": eti,
        "coloresTexto": {"resalte": AZUL, "habilidad": AMARILLO},
        "insignias": {"fondo": "#3f4a4d", "borde": "#2b3638", "texto": AMARILLO,
                      "pngLealtad": "capas/planeswalker/frame__tick-1-box.png"},
        "sustituir": {"—": "-", "–": "-", "−": "-", "•": "-", "·": "-", "’": "'", "“": "\"", "”": "\""},
        "estilos": estilos(z_cuadros),
    }
    (PACK / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    podar(pack)
    print("pack.json:", len(pack["estilos"]), "estilos,", len(sim), "símbolos,", len(eti), "etiquetas")


if __name__ == "__main__":
    main()
