# Proxy Builder frame packs

Downloadable content for the card editor of
[Proxy Builder](https://github.com/PoolFlamingo/proxy-builder). The app
downloads each pack from a fixed commit of this repository and checks the
SHA-256 of every file (the manifest lives in the app:
`src-tauri/assets/packs-descargables.json`).

## `balatro/`

Pixel-art frames themed after Balatro: seven templates (Joker, Land,
Planeswalker, Planet, Spectral, Tarot and Voucher) with their variants, mana in
poker chips, rarity as a label, coloured words and scanlines. It also includes
two card backs, tokens, the basic lands and the ready-made cards of the sample
deck. Credits and licences in `balatro/CREDITS.md`.

### Rebuilding it from the templates

In `balatro/source/`, with a venv that has `psd-tools`, `pillow` and `numpy`:

1. `python -I convert.py <folder with the PSDs> ..` — layers and inventory.
2. `python -I build.py .. <Drive folder> <m6x11plus.ttf>` — symbols, labels,
   extras and `pack.json` (leaves only the layers it uses).
3. `python -I manifest.py .. <commit>` — the app's manifest entry.

`build.py` deletes the layers it does not use: if you run it again, run
`convert.py` first.
