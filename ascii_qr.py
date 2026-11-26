"""Static ASCII artwork + QR composition, with independent decoding gates."""
from __future__ import annotations

import argparse
import html
import io
import json
import math
from pathlib import Path
import time
from urllib.parse import urlsplit

import numpy as np
from PIL import Image, ImageFilter, ImageOps
import segno
from segno import consts
import zxingcpp

from ascii_pipeline import BOLD_FONT_PATH, convert, image_uri, load_image, save_result

BORDER = 4
CORE_RATIOS = (0.30, 0.40, 0.50, 0.60, 0.80)


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname
            or any(c.isspace() or ord(c) < 32 for c in url)
            or len(url.encode('utf-8')) > 1000):
        raise ValueError('Use an http(s) URL without whitespace, at most 1000 UTF-8 bytes.')
    return url


def qr_layout(url, min_version=5):
    if not 1 <= min_version <= 15:
        raise ValueError('min_version must be between 1 and 15')
    qr = segno.make(validate_url(url), error='h', micro=False, boost_error=False)
    if qr.version < min_version:
        qr = segno.make(url, version=min_version, error='h', micro=False, boost_error=False)
    matrix = np.array(qr.matrix, dtype=bool)
    kinds = np.array(list(qr.matrix_iter(border=0, verbose=True)))
    function = ~np.isin(kinds, [consts.TYPE_DATA_DARK, consts.TYPE_DATA_LIGHT])
    return qr, matrix, function


def prepare_art(image, columns=64, fit='contain', theme='dark', renderer='tonal', crop=None):
    if fit not in ('contain', 'cover') or theme not in ('dark', 'light'):
        raise ValueError('Unknown fit or theme')
    bg = (0, 0, 0) if theme == 'dark' else (255, 255, 255)
    original_size = list(image.size)
    if crop is not None:
        if len(crop) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in crop) or not (crop[0] < crop[2] and crop[1] < crop[3]):
            raise ValueError('crop requires normalized left top right bottom coordinates')
        image = image.crop((round(crop[0]*image.width), round(crop[1]*image.height), round(crop[2]*image.width), round(crop[3]*image.height)))
    # Square framing precedes ASCII conversion: never stretch glyphs/aspect later.
    if fit == 'cover':
        framed = ImageOps.fit(image, (1024, 1024), method=Image.Resampling.LANCZOS)
    else:
        framed = ImageOps.pad(image, (1024, 1024), method=Image.Resampling.LANCZOS, color=bg)
    data, mono, color = convert(framed, columns=columns, mode='shape', theme=theme, font_path=BOLD_FONT_PATH, renderer=renderer)
    data['framing'] = {'fit': fit, 'original_size': original_size, 'working_size': [1024, 1024], 'crop': crop}
    return framed, data, mono, color


def compose(art, matrix, function, module_pixels=24, core_ratio=0.5, core_style='solid'):
    if core_style not in ('solid', 'adaptive'):
        raise ValueError('Unknown core_style')
    if not 12 <= module_pixels <= 48:
        raise ValueError('module_pixels must be between 12 and 48')
    if not math.isfinite(core_ratio) or not 0.3 <= core_ratio <= 0.9:
        raise ValueError('core_ratio must be between 0.3 and 0.9')
    n = len(matrix)
    art = art.convert('RGB').resize((n * module_pixels, n * module_pixels), Image.Resampling.LANCZOS)
    pixels = np.array(art)
    # Preserve the ASCII layer outside small central QR samples. All function
    # modules (finders, separators, timing, alignment, format/version) stay exact.
    core = max(1, round(module_pixels * core_ratio))
    lo = (module_pixels - core) // 2
    for y in range(n):
        for x in range(n):
            y0, x0 = y * module_pixels, x * module_pixels
            value = 0 if matrix[y, x] else 255
            if function[y, x]:
                pixels[y0:y0 + module_pixels, x0:x0 + module_pixels] = value
            else:
                region = pixels[y0 + lo:y0 + lo + core, x0 + lo:x0 + lo + core]
                if core_style == 'solid':
                    region[:] = value
                else:
                    # Retain existing local tones whenever they already lie
                    # on the required side of a wide luminance guard band.
                    region[:] = np.minimum(region, 80) if matrix[y, x] else np.maximum(region, 175)
    result = Image.new('RGB', ((n + BORDER * 2) * module_pixels,) * 2, 'white')
    result.paste(Image.fromarray(pixels), (BORDER * module_pixels,) * 2)
    return result


def decode_text(image):
    found = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    return [item.text for item in found if item.valid]


def scan_suite(image, url, total_modules):
    jpeg = io.BytesIO()
    image.save(jpeg, format='JPEG', quality=70)
    jpeg.seek(0)
    with Image.open(jpeg) as opened:
        compressed = opened.copy()
    cases = [
        ('original', image),
        ('grayscale', image.convert('L')),
        ('6px_per_module', image.resize((total_modules * 6,) * 2, Image.Resampling.LANCZOS)),
        ('4px_per_module', image.resize((total_modules * 4,) * 2, Image.Resampling.LANCZOS)),
        ('blur_0.6px', image.filter(ImageFilter.GaussianBlur(0.6))),
        ('rotation_8deg', image.rotate(8, Image.Resampling.BICUBIC, expand=True, fillcolor='white')),
        ('jpeg_quality_70', compressed),
    ]
    results = []
    for name, variant in cases:
        texts = decode_text(variant)
        results.append({'case': name, 'passed': texts == [url], 'decoded': texts, 'size': list(variant.size)})
    return {'passed': all(r['passed'] for r in results), 'cases': results}


def create_project(image, url, output, *, columns=64, fit='contain', theme='dark', module_pixels=24, min_version=5, renderer='tonal', crop=None, core_style='adaptive'):
    output = Path(output)
    if output.exists():
        raise ValueError(f'Output already exists: {output}')
    if not 12 <= module_pixels <= 48:
        raise ValueError('module_pixels must be between 12 and 48')
    qr, matrix, function = qr_layout(url, min_version)
    framed, data, mono, color = prepare_art(image, columns, fit, theme, renderer, crop)
    output.mkdir(parents=True)
    save_result(framed, data, mono, color, output / 'ascii')
    qr.save(output / 'plain-qr.png', scale=module_pixels, border=BORDER)
    # Matrix is useful for inspection; no part of the source photograph is used
    # in the compositing stage, only the two generated ASCII images above.
    (output / 'qr-matrix.json').write_text(json.dumps({
        'version': qr.version, 'error': qr.error, 'mask': qr.mask,
        'matrix': matrix.astype(int).tolist(), 'function_mask': function.astype(int).tolist(),
        'quiet_zone_modules': BORDER,
    }), encoding='utf-8')
    with Image.open(output / 'plain-qr.png') as plain:
        baseline = scan_suite(plain.convert('RGB'), url, len(matrix) + BORDER * 2)
    candidates = []
    selected = None
    figures = []
    for ratio in CORE_RATIOS:
        name = f'core-{round(ratio * 100)}'
        composed = {}
        checks = {}
        for kind, art in [('color', color), ('mono', mono)]:
            candidate = compose(art, matrix, function, module_pixels, ratio, core_style)
            candidate.save(output / f'{name}-{kind}.png')
            # Validate the actual saved artifact, not an earlier render buffer.
            with Image.open(output / f'{name}-{kind}.png') as saved:
                checks[kind] = scan_suite(saved.convert('RGB'), url, len(matrix) + BORDER * 2)
            composed[kind] = candidate
        passed = all(check['passed'] for check in checks.values())
        candidates.append({'name': name, 'core_ratio': ratio,
                           'core_pixels': round(module_pixels * ratio),
                           'actual_core_ratio': round(module_pixels * ratio) / module_pixels,
                           'passed': passed, 'checks': checks})
        if selected is None and passed and baseline['passed']:
            selected = name
            for kind, candidate in composed.items():
                candidate.save(output / f'selected-{kind}.png')
        count = sum(case['passed'] for check in checks.values() for case in check['cases'])
        figures.append(f'<article><h2>QR core width {ratio:.0%}</h2><p>Software checks {count}/14 · '
                       f'{"selected" if selected == name else "passed" if passed else "failed"}</p>'
                       + ''.join(f'<figure><figcaption>{kind}</figcaption><img alt="{name} {kind}" src="{image_uri(img)}"></figure>'
                                 for kind, img in composed.items()) + '</article>')
    report = {
        'schema_version': 2, 'url': url, 'selected': selected,
        'status': 'software_passed' if selected else 'no_candidate_passed',
        'qr_version': qr.version, 'qr_modules': len(matrix), 'error_correction': qr.error,
        'module_pixels': module_pixels, 'quiet_zone_modules': BORDER, 'min_version': min_version,
        'ascii_columns': data['columns'], 'ascii_rows': data['rows'], 'fit': fit, 'theme': theme,
        'renderer': renderer, 'crop': crop, 'core_style': core_style,
        'decoder': 'zxing-cpp 3.1.1', 'baseline': baseline, 'candidates': candidates,
        'physical_scan_tested': False,
        'limitation': 'Digital decoding checks only; real cameras and physical outputs require separate validation.',
    }
    (output / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    intro = f'<h1>ASCII art × QR</h1><p>Link URL: <code>{html.escape(url)}</code></p>'
    if url == 'https://example.com/':
        intro += '<p><strong>This is a test URL.</strong></p>'
    intro += f'<p>QR {len(matrix)}×{len(matrix)} · Error correction H · ASCII {data["columns"]}×{data["rows"]} Bold · '
    intro += f'Selected: {selected or "none — verification failed"}</p><p>Photo → real ASCII characters → QR composite. No motion.</p>'
    intro += f'<p>Character renderer: {renderer} · QR correction: {core_style} · Crop: {html.escape(str(crop))}</p>'
    if renderer == 'tonal':
        intro += '<p>Each character cell keeps the average tone through its glyph and background colors. No photo overlay is used.</p>'
    intro += '<p>These are digital decode checks. Test real cameras and printed output separately.</p>'
    with Image.open(output / 'plain-qr.png') as plain:
        stages = ''.join(f'<figure><figcaption>{label}</figcaption><img alt="{label}" src="{image_uri(img)}"></figure>'
                         for label, img in [('Original framing', framed), ('ASCII intermediate', color), ('Plain QR reference', plain)])
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASCII art and QR composite comparison</title><style>body{margin:28px;background:#17191e;color:#eee;font:16px system-ui}main{max-width:1600px;margin:auto}p{line-height:1.6}code{overflow-wrap:anywhere}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}article{background:#242730;padding:16px;border-radius:12px}h2{font-size:18px}figure{margin:12px 0}figcaption{margin:8px 0;color:#bbb}img{width:100%;height:auto}strong{color:#ffcd83}</style><main>'''
    page += intro + '<section>' + stages + '</section><h2>Composite strength comparison</h2><section>' + ''.join(figures) + '</section></main></html>'
    (output / 'preview.html').write_text(page, encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='Image → bold ASCII → static QR composite → decode verification')
    parser.add_argument('image', type=Path)
    parser.add_argument('--url', required=True, help='Exact http(s) destination; never shortened or fetched')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--columns', type=int, default=64)
    parser.add_argument('--fit', choices=['contain', 'cover'], default='contain')
    parser.add_argument('--theme', choices=['dark', 'light'], default='dark')
    parser.add_argument('--module-pixels', type=int, default=24)
    parser.add_argument('--renderer', choices=['tonal', 'classic'], default='tonal')
    parser.add_argument('--core-style', choices=['adaptive', 'solid'], default='adaptive')
    parser.add_argument('--crop', nargs=4, type=float, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'))
    parser.add_argument('--min-version', type=int, default=5, help='Minimum QR version 1–15; higher = smaller finders relative to art, denser QR')
    args = parser.parse_args()
    output = args.output or Path(__file__).parent / 'dev' / 'output' / f'ascii-qr-{time.time_ns()}'
    try:
        bg = (0, 0, 0) if args.theme == 'dark' else (255, 255, 255)
        report = create_project(load_image(args.image, bg), args.url, output,
                                columns=args.columns, fit=args.fit, theme=args.theme, module_pixels=args.module_pixels,
                                min_version=args.min_version, renderer=args.renderer, crop=args.crop, core_style=args.core_style)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        parser.error(str(exc))
    print(f'{output.resolve() / "preview.html"}\nStatus: {report["status"]}; selected: {report["selected"]}')
    if report['selected'] is None:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
