# Packs de marcos de Proxy Builder

Contenido descargable del editor de cartas de
[Proxy Builder](https://github.com/PoolFlamingo/proxy-builder). La app baja
cada pack de un commit fijo de este repositorio y comprueba el SHA-256 de cada
fichero (el manifiesto va en la app: `src-tauri/assets/packs-descargables.json`).

## `balatro/`

Marcos de pixel art con el tema de Balatro: siete plantillas (Joker, Tierra,
Planeswalker, Planeta, Espectral, Tarot y Vale) con sus variantes, maná en
fichas de póker, rareza como etiqueta, palabras de colores y líneas de
barrido. Trae además dos reversos, fichas, las tierras básicas y las cartas ya
hechas del mazo de ejemplo. Créditos y licencias en `balatro/CREDITOS.md`.

### Rehacerlo desde las plantillas

En `balatro/fuente/`, con un venv con `psd-tools`, `pillow` y `numpy`:

1. `python -I convertir.py <carpeta con los PSD> ..` — capas e inventario.
2. `python -I construir.py .. <carpeta del Drive> <m6x11plus.ttf>` — símbolos,
   etiquetas, extras y `pack.json` (deja solo las capas que usa).
3. `python -I manifiesto.py .. <commit>` — la entrada del manifiesto de la app.

`construir.py` borra las capas que no usa: si se vuelve a ejecutar, antes
`convertir.py`.
