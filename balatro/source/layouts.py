#!/usr/bin/env python3
"""The pack-level layouts of Balatro (saga, class, dungeon, flip, aftermath,
fuse, loose footer, battle, plane, scheme and Vanguard), built from pieces of
the Joker template so that they look like the rest of the pack instead of
falling back to the app's house frames.

    python -I layouts.py <pack folder>

rewrites only the `layouts` key of `pack.json`; `build.py` calls `layouts()`
when it builds the whole pack.

Every piece is a crop of a PNG (`desde`, in mm of the canvas as if the PNG
covered it whole) drawn somewhere else (`en`). The card body is a nine-slice
of the Joker frame (its corners and rim at their size, the slate stretched),
laid around the art window so the art shows through; the art window gets the
rounded corners of the Joker art hole; boxes are nine-slices of the white
rules box and bars three-slices of the type line.
"""

import json
import sys
from pathlib import Path

J = "layers/joker/"
FRAME = J + "frame__frame.png"          # 63 x 88 mm
BOX = (J + "frame__non-legendary.png", 1152 / (1240 / 63), 525 / (1240 / 63))
BAR = (J + "frame__typeline.png", 1190 / (1240 / 63), 117 / (1240 / 63))
PT = (J + "frame__p-t.png", 310 / (1240 / 63), 117 / (1240 / 63))
SCANLINES = [
    {"png": J + "small-scanlines__b.png", "mezcla": "oscurecer", "opacidad": 0.051},
    {"png": J + "small-scanlines__g.png", "mezcla": "oscurecer", "opacidad": 0.051},
    {"png": J + "small-scanlines__r.png", "mezcla": "oscurecer", "opacidad": 0.051},
    {"png": J + "small-scanlines__vertical.png", "mezcla": "oscurecer", "opacidad": 0.09},
]
# The Joker's mana boxes (63 x 88 layouts only: they sit under the title).
MANA = [
    (1, 1, 53.804, 7.519), (2, 2, 49.13, 12.194), (3, 3, 44.456, 16.868),
    (4, 4, 39.781, 12.244), (5, 5, 35.107, 12.244), (6, 20, 30.433, 12.244),
]
TINTA = "#3f4a4d"
BLANCO = "#ffffff"
# The Joker's art hole in the frame (mm) and the size of its rounded corners.
HOLE = (2.54, 14.06, 60.41, 47.71)
HOLE_CORNER = 2.0
CARD_CORNER = 3.0
BOX_CORNER = 2.5
BAR_CAP = 1.0


def r(v):
    return round(v, 3)


class Canvas:
    def __init__(self, w=63.0, h=88.0):
        self.w, self.h = w, h
        self.capas = []

    def piece(self, png, size, src, dst, **extra):
        """`src` in mm of the PNG (whose natural size is `size`), drawn at `dst`."""
        sw, sh = size
        x, y, w, h = src
        if dst[2] <= 0.001 or dst[3] <= 0.001:
            return
        c = {
            "png": png,
            "desde": {"x": r(x / sw * self.w), "y": r(y / sh * self.h),
                      "w": r(w / sw * self.w), "h": r(h / sh * self.h)},
            "en": {"x": r(dst[0]), "y": r(dst[1]), "w": r(dst[2]), "h": r(dst[3])},
        }
        c.update(extra)
        self.capas.append(c)

    def frame(self, src, dst):
        self.piece(FRAME, (63.0, 88.0), src, dst)

    def card(self, art=None, bottom=None, round_bottom=True, rim_bottom=True):
        """The slate card with its rim, around the art window `art`.
        `bottom`: down to where it goes (the rest is another piece)."""
        W, H, c = self.w, self.h, CARD_CORNER
        B = self.h if bottom is None else bottom
        # Top corners and edge.
        self.frame((0, 0, c, c), (0, 0, c, c))
        self.frame((63 - c, 0, c, c), (W - c, 0, c, c))
        self.frame((c, 0, 63 - 2 * c, c), (c, 0, W - 2 * c, c))
        low = B - c if (round_bottom and bottom is None) else B
        # Left and right edges.
        self.frame((0, 60, c, 15), (0, c, c, low - c))
        self.frame((63 - c, 60, c, 15), (W - c, c, c, low - c))
        if round_bottom and bottom is None:
            self.frame((0, 88 - c, c, c), (0, H - c, c, c))
            self.frame((63 - c, 88 - c, c, c), (W - c, H - c, c, c))
            self.frame((c, 88 - c, 63 - 2 * c, c), (c, H - c, W - 2 * c, c))
        elif rim_bottom and bottom is None:
            self.frame((c, 88 - c, 63 - 2 * c, c), (0, H - c, W, c))
        # The slate inside, around the art.
        fill = lambda x, y, w, h: self.frame((10, 62, 40, 12), (x, y, w, h))
        x0, y0, x1, y1 = c, c, W - c, low
        if art is None:
            fill(x0, y0, x1 - x0, y1 - y0)
            return
        ax, ay, aw, ah = art
        fill(x0, y0, x1 - x0, ay - y0)
        fill(x0, min(ay + ah, y1), x1 - x0, y1 - min(ay + ah, y1))
        top, bot = max(ay, y0), min(ay + ah, y1)
        fill(x0, top, ax - x0, bot - top)
        fill(ax + aw, top, x1 - (ax + aw), bot - top)
        # The rounded corners of the art window.
        k = HOLE_CORNER
        hx0, hy0, hx1, hy1 = HOLE
        for sx, sy, dx, dy in [(hx0, hy0, ax, ay), (hx1 - k, hy0, ax + aw - k, ay),
                               (hx0, hy1 - k, ax, ay + ah - k), (hx1 - k, hy1 - k, ax + aw - k, ay + ah - k)]:
            if dy + k <= B + 0.001:
                self.frame((sx, sy, k, k), (dx, dy, k, k))

    def box(self, x, y, w, h):
        """A white rules box (nine-slice of the Joker's)."""
        png, sw, sh = BOX
        k = BOX_CORNER
        cols = [(0, k, x, k), (k, sw - 2 * k, x + k, w - 2 * k), (sw - k, k, x + w - k, k)]
        rows = [(0, k, y, k), (k, sh - 2 * k, y + k, h - 2 * k), (sh - k, k, y + h - k, k)]
        for sy, shh, dy, dh in rows:
            for sx, sww, dx, dw in cols:
                self.piece(png, (sw, sh), (sx, sy, sww, shh), (dx, dy, dw, dh))

    def bar(self, x, y, w, png=BAR):
        """A dark bar (three-slice of the type line, or of the P/T box)."""
        p, sw, sh = png
        k = BAR_CAP
        self.piece(p, (sw, sh), (0, 0, k, sh), (x, y, k, sh))
        self.piece(p, (sw, sh), (k, 0, sw - 2 * k, sh), (x + k, y, w - 2 * k, sh))
        self.piece(p, (sw, sh), (sw - k, 0, k, sh), (x + w - k, y, k, sh))

    def mana(self):
        for a, b, x, w in MANA:
            self.capas.append({"png": J + f"frame__mana-box__{a}-mana.png" if a < 6 else J + "frame__mana-box__6-mana.png",
                               "en": {"x": x, "y": 12.106, "w": w, "h": 7.223},
                               "si": {"simbolos": [a, b]}})

    def scanlines(self):
        self.capas.extend(dict(c) for c in SCANLINES)


def hueco(x, y, w, h, **extra):
    d = {"x": r(x), "y": r(y), "w": r(w), "h": r(h)}
    d.update(extra)
    return d


def titulo(w=63.0, esc=1.0):
    return {"titulo": hueco(5.284 * esc, 4.782 * esc, w - 2 * 5.284 * esc, 5.799 * esc,
                            rol="titulo", mayuscula=r(4.502 * esc), color=BLANCO, alinear="centro")}


def tipo(y, x=1.27, w=60.46, etiqueta=True):
    h = {"tipo": hueco(x + 1.474, y + 1.882, w - (16.2 if etiqueta else 2.9), 2.543,
                       rol="tipo", mayuscula=1.956, color=BLANCO)}
    if etiqueta:
        h["etiqueta"] = hueco(x + w - 13.87, y + 1.271, 12.549, 3.306, rol="tipo", mayuscula=1.956, sombra=True)
    return h


def reglas(x, y, w, h, top=1.2, **extra):
    d = dict(rol="reglas", mayuscula=2.235, color=TINTA, alinear="inicio")
    d.update(extra)
    return {"reglas": hueco(x + 1.5, y + top, w - 3.0, h - top - 1.0, **d)}


def pie(x=4.471, y=82.913, w=42.9):
    return {"pie": hueco(x, y, w, 1.6, rol="pie", mayuscula=1.552, color="#ffe5b4", tabs=[], interlinea=1.6)}


def fr(x, y, w=15.75, h=5.951):
    return {"fr": hueco(x, y, w, h, rol="fr", mayuscula=2.95, color="#f5b244", alinear="centro")}


def layout(cv, arte, huecos, tamano=None, ventana=None):
    d = {}
    if tamano:
        d["tamano"] = tamano
    d["arte"] = hueco(*arte)
    if ventana:
        d["ventanaArte"] = ventana
    d["cajaPorDefecto"] = "clara"
    d["capas"] = cv.capas
    d["huecos"] = huecos
    return d


def layouts():
    L = {}

    # Saga: chapters on the left, art on the right.
    cv = Canvas()
    art, box = (33.2, 14.06, 26.9, 54.4), (3.0, 14.06, 29.4, 54.4)
    cv.card(art)
    cv.box(*box)
    cv.bar(1.27, 70.2, 60.46)
    cv.mana()
    cv.scanlines()
    L["saga"] = layout(cv, art, {**titulo(), "coste": hueco(20.0, 13.48, 39.7, 4.17),
                                 **tipo(70.2), **reglas(*box), **pie()})

    # Class: art on the left, levels on the right (under the mana box).
    cv = Canvas()
    art, box = (3.0, 14.06, 26.9, 54.4), (30.6, 14.06, 29.4, 54.4)
    cv.card(art)
    cv.box(*box)
    cv.bar(1.27, 70.2, 60.46)
    cv.mana()
    cv.scanlines()
    L["clase"] = layout(cv, art, {**titulo(), "coste": hueco(20.0, 13.48, 39.7, 4.17),
                                  **tipo(70.2), **reglas(*box, top=6.4), **pie()})

    # Dungeon: a band of art and the rooms in a big box.
    cv = Canvas()
    art, box = (3.0, 14.06, 57.0, 10.0), (3.0, 32.4, 57.0, 47.2)
    cv.card(art)
    cv.bar(1.27, 25.6, 60.46)
    cv.box(*box)
    cv.scanlines()
    L["mazmorra"] = layout(cv, art, {**titulo(), **tipo(25.6, etiqueta=False),
                                     **reglas(*box, mayuscula=1.1), **pie()})

    # Flip: only the top half (the other half is the same piece, turned).
    cv = Canvas()
    art, box = (3.0, 31.0, 57.0, 26.0), (3.0, 12.4, 57.0, 11.8)
    cv.card(art, bottom=44.0)
    cv.box(*box)
    cv.bar(1.27, 24.6, 42.5)
    cv.bar(44.4, 24.6, 15.75, png=PT)
    cv.scanlines()
    L["flip"] = layout(cv, art, {**titulo(), "coste": hueco(30.0, 5.5, 28.0, 3.6),
                                 **tipo(24.6, w=42.5, etiqueta=False),
                                 **reglas(*box, mayuscula=2.0), **fr(44.4, 24.6)})
    L["flip"]["huecos"]["titulo"].update(w=30.0, alinear="inicio", mayuscula=3.4)

    # Aftermath, top half (63 x 51) and bottom half (33 x 63, turned left).
    cv = Canvas(63, 51)
    art, box = (3.0, 14.06, 57.0, 17.4), (3.0, 39.0, 57.0, 12.0)
    cv.card(art, bottom=51.0)
    cv.bar(1.27, 32.4, 60.46)
    cv.box(*box)
    L["secuelaArriba"] = layout(cv, art, {**titulo(), "coste": hueco(30.0, 10.0, 28.0, 3.4),
                                          **tipo(32.4), **reglas(*box, mayuscula=2.0)}, tamano=[63, 51])
    cv = Canvas(33, 63)
    box = (1.6, 13.0, 29.8, 48.4)
    cv.card()
    cv.bar(0.9, 1.0, 31.2)
    cv.bar(0.9, 6.7, 31.2)
    cv.box(*box)
    L["secuelaAbajo"] = layout(cv, (0, 0, 0, 0), {
        "titulo": hueco(2.4, 2.7, 18.0, 2.6, rol="titulo", mayuscula=2.0, color=BLANCO),
        "coste": hueco(20.0, 2.2, 10.5, 3.2),
        "tipo": hueco(2.4, 8.4, 28.0, 2.5, rol="tipo", mayuscula=1.956, color=BLANCO),
        **reglas(*box, mayuscula=1.9)}, tamano=[33, 63])

    # Fuse: the shared strip (88 x 6).
    cv = Canvas(88, 6)
    cv.box(0.3, 0.2, 87.4, 5.6)
    L["fusionar"] = layout(cv, (0, 0, 0, 0), {"reglas": hueco(4.0, 1.0, 80.0, 4.0, rol="reglas", mayuscula=1.6,
                                                              color=TINTA, alinear="centro")}, tamano=[88, 6])

    # The footer of the composed cards.
    L["pie"] = {"arte": hueco(0, 0, 0, 0), "capas": [], "huecos": pie(y=84.9)}

    # Battle (88 x 63, landscape).
    cv = Canvas(88, 63)
    art, box = (3.0, 14.06, 82.0, 18.4), (3.0, 40.4, 68.0, 18.0)
    cv.card(art)
    cv.bar(1.27, 33.6, 70.0)
    cv.box(*box)
    cv.bar(72.4, 50.4, 13.6, png=PT)
    cv.scanlines()
    L["batalla"] = layout(cv, art, {**titulo(w=88.0), "coste": hueco(48.0, 6.0, 36.0, 3.6),
                                    **tipo(33.6, w=70.0), **reglas(*box, mayuscula=2.0),
                                    **fr(72.4, 50.4, 13.6), **pie(y=59.4, w=60.0)}, tamano=[88, 63])

    # Plane (127 x 88.9, landscape).
    cv = Canvas(127, 88.9)
    art, box = (3.0, 14.06, 121.0, 37.0), (3.0, 58.6, 121.0, 23.6)
    cv.card(art)
    cv.bar(1.27, 51.8, 124.46)
    cv.box(*box)
    cv.scanlines()
    L["plano"] = layout(cv, art, {**titulo(w=127.0), **tipo(51.8, w=124.46),
                                  **reglas(*box, mayuscula=2.4), **pie(y=84.0, w=110.0)}, tamano=[127, 88.9])

    # Scheme and Vanguard (88.9 x 127).
    for nombre, alto in (("plan", 38.0), ("vanguard", 28.0)):
        cv = Canvas(88.9, 127)
        art, box = (3.0, 14.06, 82.9, 54.0), (3.0, 76.6, 82.9, alto)
        cv.card(art)
        cv.bar(1.27, 69.6, 86.36)
        cv.box(*box)
        hs = {**titulo(w=88.9), **tipo(69.6, w=86.36), **reglas(*box, mayuscula=2.4), **pie(y=121.8, w=80.0)}
        if nombre == "vanguard":
            cv.bar(3.0, 108.0, 26.0, png=PT)
            cv.bar(59.9, 108.0, 26.0, png=PT)
            hs["mano"] = hueco(3.0, 108.0, 26.0, 5.951, rol="fr", mayuscula=2.4, color="#f5b244", alinear="centro")
            hs["vida"] = hueco(59.9, 108.0, 26.0, 5.951, rol="fr", mayuscula=2.4, color="#f5b244", alinear="centro")
        cv.scanlines()
        L[nombre] = layout(cv, art, hs, tamano=[88.9, 127])
    return L


if __name__ == "__main__":
    pack = Path(sys.argv[1]) / "pack.json"
    datos = json.loads(pack.read_text())
    datos["layouts"] = layouts()
    pack.write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    print("layouts:", ", ".join(datos["layouts"]))
