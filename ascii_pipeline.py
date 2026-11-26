"""Offline image -> real ASCII characters, PNGs and motion-ready cell data."""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

CHARSET = ''.join(chr(i) for i in range(32, 127))
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
BOLD_FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'


def glyph_atlas(font_path=FONT_PATH, font_size=16):
    font = ImageFont.truetype(str(font_path), font_size)
    widths = [font.getlength(c) for c in CHARSET]
    if max(widths) - min(widths) > 0.1:
        raise ValueError('A monospace font is required.')
    cw = math.ceil(max(widths))
    ascent, descent = font.getmetrics()
    ch = ascent + descent
    masks = []
    for char in CHARSET:
        # All characters share a baseline (including punctuation).
        tile = Image.new('L', (cw, ch))
        ImageDraw.Draw(tile).text((0, ascent), char, font=font, fill=255, anchor='ls')
        masks.append(np.asarray(tile, dtype=np.float32) / 255)
    return np.stack(masks), cw, ch


def load_image(path, background):
    with Image.open(path) as source:
        source.seek(0)
        oriented = ImageOps.exif_transpose(source)
        rgba = oriented.convert('RGBA')
        base = Image.new('RGBA', rgba.size, background + (255,))
        return Image.alpha_composite(base, rgba).convert('RGB')


def convert(image, *, columns=120, mode='tone', theme='dark', gamma=1.0,
            contrast=1.15, autocontrast=True, font_path=FONT_PATH, renderer='classic'):
    if renderer not in ('classic', 'tonal'):
        raise ValueError('Unknown renderer')
    if not 16 <= columns <= 300:
        raise ValueError('columns must be between 16 and 300')
    if mode not in ('tone', 'shape') or theme not in ('dark', 'light'):
        raise ValueError('Unknown mode or theme')
    if not math.isfinite(gamma) or not 0.2 <= gamma <= 3:
        raise ValueError('gamma must be between 0.2 and 3')
    if not math.isfinite(contrast) or not 0.2 <= contrast <= 3:
        raise ValueError('contrast must be between 0.2 and 3')
    masks, cw, ch = glyph_atlas(font_path)
    rows = max(1, round(image.height / image.width * columns * cw / ch))
    if rows > 600 or rows * columns > 60000:
        raise ValueError('Image is too tall at this column count; reduce --columns or crop it.')
    rgb = np.asarray(image.resize((columns * cw, rows * ch), Image.Resampling.LANCZOS), dtype=np.float32) / 255
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    if autocontrast:
        low, high = np.percentile(lum, [1, 99])
        if high - low > 1 / 255:
            lum = np.clip((lum - low) / (high - low), 0, 1)
    lum = np.clip((lum - 0.5) * contrast + 0.5, 0, 1) ** (1 / gamma)
    ink = lum if theme == 'dark' else 1 - lum
    patches = ink.reshape(rows, ch, columns, cw).transpose(0, 2, 1, 3).reshape(-1, cw * ch)
    mean = patches.mean(axis=1)
    glyphs = masks.reshape(len(CHARSET), -1)
    density = glyphs.mean(axis=1)
    density /= density.max()
    tone_cost = (mean[:, None] - density[None, :]) ** 2
    if mode == 'tone':
        indices = tone_cost.argmin(axis=1)
    else:
        # Match local geometry as well as tone. Standardization separates shape
        # from brightness; low-detail cells retain the tone-only result.
        centered = glyphs - glyphs.mean(axis=1, keepdims=True)
        templates = centered / np.maximum(np.linalg.norm(centered, axis=1, keepdims=True), 1e-6)
        indices = np.empty(len(patches), dtype=np.int64)
        for start in range(0, len(patches), 512):
            block = patches[start:start + 512]
            centered = block - block.mean(axis=1, keepdims=True)
            normalized = centered / np.maximum(np.linalg.norm(centered, axis=1, keepdims=True), 1e-6)
            correlation = normalized @ templates.T
            weight = np.minimum(block.std(axis=1) * 1.5, 0.25)
            scores = tone_cost[start:start + len(block)] - weight[:, None] * correlation
            indices[start:start + len(block)] = scores.argmin(axis=1)
    indices = indices.reshape(rows, columns)
    colors = np.rint(rgb.reshape(rows, ch, columns, cw, 3).mean(axis=(1, 3)) * 255).astype(np.uint8)
    lines = [''.join(CHARSET[i] for i in row) for row in indices]
    background = 0 if theme == 'dark' else 255
    foreground = 255 - background
    mask = masks[indices].transpose(0, 2, 1, 3).reshape(rows * ch, columns * cw)
    mono = np.rint(background + mask * (foreground - background)).astype(np.uint8)
    expanded = colors.repeat(ch, axis=0).repeat(cw, axis=1)
    color = np.rint(background + mask[:, :, None] * (expanded.astype(np.float32) - background)).astype(np.uint8)
    data = {
        'schema_version': 1, 'columns': columns, 'rows': rows,
        'cell_width': cw, 'cell_height': ch, 'font': Path(font_path).name,
        'font_size': 16, 'baseline': ImageFont.truetype(str(font_path), 16).getmetrics()[0],
        'theme': theme, 'mode': mode, 'gamma': gamma, 'contrast': contrast,
        'autocontrast': autocontrast, 'charset': CHARSET,
        'source_size': list(image.size), 'lines': lines, 'colors': colors.tolist(),
        'coordinate_system': 'top-left origin; cell center = ((column+0.5)*cell_width, (row+0.5)*cell_height)',
    }
    data['renderer'] = renderer
    if renderer == 'tonal':
        # Each cell is ONLY a glyph mask plus two constant colors. Reconstruct
        # its average luminance instead of losing it to the empty glyph area.
        # Bright cells use reverse-video text. No photograph is underneath.
        coverage = masks[indices].mean(axis=(2, 3))[:, :, None]
        targets = {
            'color': colors.astype(np.float32),
            'mono': (lum.reshape(rows, ch, columns, cw).mean(axis=(1, 3)) * 255)[:, :, None],
        }
        renders = {}
        data['cell_styles'] = {}
        for kind, target in targets.items():
            sign = np.where(target.mean(axis=2, keepdims=True) > 127.5, -1., 1.)
            limit_positive = np.minimum(target / np.maximum(coverage, 1e-6),
                                        (255 - target) / np.maximum(1 - coverage, 1e-6))
            limit_negative = np.minimum((255 - target) / np.maximum(coverage, 1e-6),
                                        target / np.maximum(1 - coverage, 1e-6))
            amplitude = np.minimum(64, np.where(sign > 0, limit_positive, limit_negative).min(axis=2, keepdims=True))
            bg = target - sign * amplitude * coverage
            fg = bg + sign * amplitude
            rendered = bg.repeat(ch, axis=0).repeat(cw, axis=1) + mask[:, :, None] * (fg-bg).repeat(ch, axis=0).repeat(cw, axis=1)
            renders[kind] = np.rint(np.clip(rendered, 0, 255)).astype(np.uint8)
            data['cell_styles'][kind] = {'foreground': fg.tolist(), 'background': bg.tolist()}
        mono = renders['mono'][:, :, 0]
        color = renders['color']
    return data, Image.fromarray(mono), Image.fromarray(color)


def image_uri(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def save_result(image, data, mono, color, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'art.txt').write_text('\n'.join(data['lines']) + '\n', encoding='utf-8')
    (destination / 'cells.json').write_text(json.dumps(data, ensure_ascii=True), encoding='utf-8')
    mono.save(destination / 'mono.png')
    color.save(destination / 'color.png')
    thumb = image.copy()
    thumb.thumbnail((1200, 1200))
    figures = ''.join(f'<figure><figcaption>{label}</figcaption><img alt="{label}" src="{image_uri(pic)}"></figure>'
                      for label, pic in [('Original', thumb), ('Color ASCII', color), ('Monochrome ASCII', mono)])
    text = html.escape('\n'.join(data['lines']))
    report = f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ASCII 변환 결과</title>
<style>body{{background:#17191e;color:#eee;font:16px system-ui;margin:32px}}main{{max-width:1400px;margin:auto}}
figure{{margin:24px 0}}figcaption{{margin:8px 0;color:#bbb}}img{{max-width:100%;height:auto}}pre{{overflow:auto;font:12px/1.19 monospace}}</style>
<main><h1>이미지 → ASCII</h1><p>{data['columns']} × {data['rows']} characters · {data['mode']} · {data['theme']} · {html.escape(data['font'])}</p>
{figures}<details><summary>텍스트 보기</summary><pre>{text}</pre></details></main></html>'''
    (destination / 'preview.html').write_text(report, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='로컬 이미지 → ASCII TXT / PNG / JSON / HTML (외부 전송 없음)')
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path, help='New directory; existing directories are never overwritten')
    parser.add_argument('--preset', choices=['classic', 'bold'], default='classic',
                        help='classic: 120 columns / regular; bold: 64 columns / bold. Explicit options override.')
    parser.add_argument('--columns', type=int)
    parser.add_argument('--mode', choices=['tone', 'shape'], default='tone')
    parser.add_argument('--renderer', choices=['tonal', 'classic'], default='tonal',
                        help='tonal preserves cell brightness with foreground/background colors; classic uses a flat background')
    parser.add_argument('--theme', choices=['dark', 'light'], default='dark')
    parser.add_argument('--gamma', type=float, default=1.0)
    parser.add_argument('--contrast', type=float, default=1.15)
    parser.add_argument('--no-autocontrast', action='store_true')
    parser.add_argument('--font', type=Path)
    args = parser.parse_args()
    columns = args.columns if args.columns is not None else (64 if args.preset == 'bold' else 120)
    font_path = args.font or Path(BOLD_FONT_PATH if args.preset == 'bold' else FONT_PATH)
    target = args.output or Path(__file__).parent / 'dev' / 'output' / f'{args.image.stem}-{time.time_ns()}'
    if target.exists():
        parser.error(f'Output already exists: {target}; choose a new --output directory')
    started = time.perf_counter()
    try:
        bg = (0, 0, 0) if args.theme == 'dark' else (255, 255, 255)
        image = load_image(args.image, bg)
        data, mono, color = convert(image, columns=columns, mode=args.mode,
                                    theme=args.theme, gamma=args.gamma, contrast=args.contrast,
                                    autocontrast=not args.no_autocontrast, font_path=font_path, renderer=args.renderer)
        save_result(image, data, mono, color, target)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        parser.error(str(exc))
    print(f'{data["columns"]} × {data["rows"]} · {time.perf_counter()-started:.2f}s\n{target.resolve() / "preview.html"}')


if __name__ == '__main__':
    main()
