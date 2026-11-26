# Technology

The Docker image pins Pillow 13.0.0, NumPy 2.5.5, Segno 1.6.6 and ZXing-cpp 3.1.1.

## Pipeline

1. **Prepare the image.** Apply EXIF orientation, flatten transparency, crop to the selected area and fit it to a square.
2. **Match characters.** Render the real mask of every monospace glyph and compare each cell's tone and shape against them.
3. **Preserve tone.** In `tonal` mode, compute a glyph color and a background color per cell so that the cell keeps its average color. A test rebuilds the exact pixels from the cell JSON alone.
4. **Compose the QR.** Keep all QR function modules and adjust only the centers of data modules. `adaptive` limits dark channels to 80 or below and light channels to 175 or above.
5. **Verify.** Read the saved PNG back with an independent decoder and compare the result with the URL byte for byte.

Error-correction level H does not mean that any 30% of the code can be covered. The studio tests the actual files. A digital pass is never treated as proof of visual quality or of real-world scanning.

## Web studio

The local UI is plain HTML, CSS and JavaScript served by `server.py`, with no build step and no external requests. `web/fx.js` contains visual effects only: the decorative pixel field, the bead-text banner, the result assembly animation and the screen grain. Conversion never depends on it. These effects are disabled when the system asks for reduced motion.

## References and alternatives

- [Pillow ImageOps](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html): orientation and fitting.
- [Segno](https://segno.readthedocs.io/en/latest/api.html): the verbose matrix distinguishes function modules. It is an experimental API, so the version is pinned and tested across several QR versions.
- [ZXing-cpp Python](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md): independent decoding.
- DENSO WAVE on [error correction](https://www.qrcode.com/en/about/error_correction.html) and the [quiet zone](https://www.qrcode.com/en/howto/code.html/index.html).
- [ASCII Magic](https://github.com/LeandroBarone/python-ascii_magic): general-purpose Python converter.
- [ascii-image-converter](https://github.com/TheZoraiz/ascii-image-converter): Go CLI alternative.
- [dwooods/asciify](https://github.com/dwooods/asciify): reference for glyph-shape matching.
- [Asciify Engine](https://github.com/ayangabryl/asciify-engine): real-time GPU renderer. Not a dependency of this project.

No generative image API or external plugin is used, and conversion and decoding work without any remote service.

## Licenses

Dependencies keep their own licenses:

- Pillow: HPND
- NumPy: BSD
- Segno: BSD
- ZXing-cpp: Apache-2.0
- DejaVu fonts: DejaVu license
- [Galmuri](https://github.com/quiple/galmuri) pixel font: SIL Open Font License 1.1 (`web/fonts/OFL.txt`)

The full texts ship with the installed packages, the Debian font package and the `web/fonts/` folder.
