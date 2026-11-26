import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from ascii_qr import (BORDER, compose, create_project, decode_text,
                      prepare_art, qr_layout, scan_suite, validate_url)


class AsciiQRTests(unittest.TestCase):
    def test_structure_and_centers_preserved_across_versions(self):
        for version in (1, 5, 7, 10):
            qr, matrix, function = qr_layout('https://example.com/', version)
            art = Image.new('RGB', (240, 180), (43, 130, 180))
            image = compose(art, matrix, function, 12, 0.5)
            pixels = np.array(image)
            border = BORDER * 12
            self.assertTrue(np.all(pixels[:border] == 255))
            self.assertTrue(np.all(pixels[-border:] == 255))
            self.assertTrue(np.all(pixels[:, :border] == 255))
            self.assertTrue(np.all(pixels[:, -border:] == 255))
            inner = pixels[border:-border, border:-border]
            for y, x in np.ndindex(matrix.shape):
                expected = 0 if matrix[y, x] else 255
                cell = inner[y*12:(y+1)*12, x*12:(x+1)*12]
                self.assertTrue(np.all(cell[6, 6] == expected))
                if function[y, x]: self.assertTrue(np.all(cell == expected))
            self.assertEqual(decode_text(image), ['https://example.com/'])

    def test_exact_url_round_trip_and_wrong_url_rejected(self):
        urls = ['https://example.com/', 'https://example.com/album?id=123&name=%ED%95%9C%EA%B8%80',
                'https://example.com/' + 'long-album-path-' * 15]
        for url in urls:
            qr, matrix, function = qr_layout(url)
            image = compose(Image.new('RGB', (100, 100), '#707070'), matrix, function, 16, 0.8)
            self.assertTrue(scan_suite(image, url, len(matrix)+8)['passed'])
            self.assertFalse(scan_suite(image, 'https://example.com/wrong', len(matrix)+8)['passed'])
        self.assertFalse(scan_suite(Image.new('RGB', (400, 400), 'white'), urls[0], 45)['passed'])

    def test_framing_and_ascii_intermediate(self):
        source = Image.new('RGB', (240, 80), 'red')
        for fit in ('cover', 'contain'):
            framed, data, mono, color = prepare_art(source, columns=48, fit=fit)
            self.assertEqual(framed.size, (1024, 1024))
            self.assertEqual(data['framing']['original_size'], [240, 80])
            self.assertIn('Bold', data['font'])
            self.assertTrue(all(32 <= ord(c) <= 126 for line in data['lines'] for c in line))
            self.assertEqual(data['renderer'], 'tonal')
            self.assertIn('cell_styles', data)
        self.assertEqual(prepare_art(source, fit='contain')[0].getpixel((0,0)), (0,0,0))
        self.assertEqual(prepare_art(source, fit='cover')[0].getpixel((0,0)), (255,0,0))

    def test_exports_and_fail_closed(self):
        image = Image.new('RGB', (200, 200), 'white')
        ImageDraw.Draw(image).ellipse((30,30,170,170), fill='navy')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'success'
            report = create_project(image, 'https://example.com/', out, columns=32, module_pixels=12)
            self.assertIsNotNone(report['selected'])
            with Image.open(out/'selected-mono.png') as saved:
                self.assertEqual(decode_text(saved), ['https://example.com/'])
            self.assertFalse(report['physical_scan_tested'])
            self.assertEqual(len(report['candidates']), 5)
            self.assertTrue((out/'ascii/art.txt').exists())
            with self.assertRaises(ValueError): create_project(image, 'https://example.com/', out)
            with patch('ascii_qr.scan_suite', return_value={'passed':False, 'cases':[]}):
                failed = Path(tmp)/'failure'
                report = create_project(image, 'https://example.com/', failed, columns=32, module_pixels=12)
                self.assertIsNone(report['selected'])
                self.assertFalse((failed/'selected-color.png').exists())
                self.assertEqual(json.loads((failed/'validation.json').read_text())['status'], 'no_candidate_passed')

    def test_invalid_inputs(self):
        for url in ['file:///secret', 'javascript:alert(1)', 'https://', 'https://example.com/has space', 'https://example.com/'+'x'*1001]:
            with self.assertRaises(ValueError): validate_url(url)
        with self.assertRaises(ValueError): qr_layout('https://example.com/', 0)
        with self.assertRaises(ValueError): compose(Image.new('RGB',(10,10)), np.zeros((21,21)), np.zeros((21,21)), core_ratio=float('nan'))

    def test_adaptive_guard_band_and_crop_validation(self):
        _, matrix, function = qr_layout('https://www.naver.com/')
        art = Image.new('RGB', (200,200), (120,180,210))
        result = np.asarray(compose(art, matrix, function, 24, 0.4, 'adaptive'))
        for y,x in np.ndindex(matrix.shape):
            core=result[(y+4)*24+12,(x+4)*24+12]
            if function[y,x]: self.assertTrue(np.all(core==(0 if matrix[y,x] else 255)))
            elif matrix[y,x]: self.assertTrue(np.all(core<=80))
            else: self.assertTrue(np.all(core>=175))
        for crop in [(0,0,0,1), (-1,0,1,1), (0,0,float('nan'),1)]:
            with self.assertRaises(ValueError): prepare_art(art,crop=crop)


if __name__ == '__main__':
    unittest.main()
