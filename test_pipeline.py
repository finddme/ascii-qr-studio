import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from ascii_pipeline import convert, glyph_atlas, load_image, save_result, CHARSET


class PipelineTests(unittest.TestCase):
    def test_aspect_ratio_and_real_ascii(self):
        data, mono, color = convert(Image.new('RGB', (400, 200), '#888888'), columns=80)
        self.assertLess(abs(mono.width / mono.height - 2), 0.1)
        self.assertEqual(color.size, mono.size)
        self.assertTrue(all(len(line) == 80 for line in data['lines']))
        self.assertTrue(all(32 <= ord(c) <= 126 for line in data['lines'] for c in line))

    def test_background_and_density_monotonic(self):
        gradient = np.tile(np.arange(256, dtype=np.uint8), (128, 1))
        atlas, _, _ = glyph_atlas()
        density = atlas.mean(axis=(1, 2))
        for theme in ['dark', 'light']:
            data, _, _ = convert(Image.fromarray(gradient).convert('RGB'), columns=64, theme=theme, contrast=1, autocontrast=False)
            values = np.array([density[CHARSET.index(c)] for c in data['lines'][0]])
            self.assertTrue(np.all(np.diff(values) >= -1e-6) if theme == 'dark' else np.all(np.diff(values) <= 1e-6))
            bg = 'black' if theme == 'dark' else 'white'
            data, _, _ = convert(Image.new('RGB', (64, 64), bg), columns=16, theme=theme)
            self.assertTrue(all(not line.strip() for line in data['lines']))

    def test_shape_distinguishes_equal_brightness_lines(self):
        atlas, cw, ch = glyph_atlas()
        chars = '/\\' * 8
        row = np.hstack([atlas[CHARSET.index(c)] for c in chars])
        image = Image.fromarray(np.rint(np.tile(row, (4, 1)) * 255).astype('uint8')).convert('RGB')
        data, _, _ = convert(image, columns=16, mode='shape', contrast=1, autocontrast=False)
        self.assertEqual(data['lines'][0], chars)

    def test_transparency_and_exif(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'alpha.png'
            Image.new('RGBA', (8, 4), (255, 0, 0, 0)).save(p)
            self.assertEqual(load_image(p, (255, 255, 255)).getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(load_image(p, (0, 0, 0)).getpixel((0, 0)), (0, 0, 0))
            p = Path(tmp) / 'rotate.jpg'
            exif = Image.Exif(); exif[274] = 6
            Image.new('RGB', (80, 40), 'red').save(p, exif=exif)
            self.assertEqual(load_image(p, (0, 0, 0)).size, (40, 80))

    def test_exports_agree_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Image.new('RGB', (80, 40), 'red')
            data, mono, color = convert(image, columns=16)
            out = Path(tmp) / 'result'
            save_result(image, data, mono, color, out)
            self.assertEqual(set(p.name for p in out.iterdir()), {'art.txt','cells.json','mono.png','color.png','preview.html'})
            self.assertEqual(json.loads((out / 'cells.json').read_text())['lines'], (out / 'art.txt').read_text().splitlines())
            with Image.open(out / 'color.png') as saved:
                self.assertEqual(saved.size, color.size)
            report = (out / 'preview.html').read_text()
            self.assertIn('data:image/png;base64,', report)
            self.assertNotIn('https://', report)
            with self.assertRaises(FileExistsError):
                save_result(image, data, mono, color, out)

    def test_limits(self):
        image = Image.new('RGB', (10, 10))
        for kwargs in [{'columns':0}, {'gamma':0}, {'gamma':float('nan')}, {'contrast':10}]:
            with self.assertRaises(ValueError): convert(image, **kwargs)
        with self.assertRaises(ValueError): convert(Image.new('RGB', (1, 1000)))

    def test_input_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ext in ['png', 'jpg', 'webp', 'gif', 'bmp', 'tiff']:
                p = Path(tmp) / f'image.{ext}'
                Image.new('RGB', (80, 40), '#cc6644').save(p)
                image = load_image(p, (0, 0, 0))
                for mode in ['tone', 'shape']:
                    for theme in ['light', 'dark']:
                        data, mono, color = convert(image, columns=16, mode=mode, theme=theme)
                        self.assertEqual(data['source_size'], [80, 40])
                        self.assertEqual(mono.size, color.size)


if __name__ == '__main__':
    unittest.main()
