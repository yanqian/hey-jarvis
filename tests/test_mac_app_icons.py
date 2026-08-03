from __future__ import annotations

import json
import re
import struct
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "app" / "src-tauri" / "icons"


def read_rgba_png(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    cursor = 8
    payload = bytearray()
    width = height = color_type = bit_depth = None
    while cursor < len(raw):
        length = struct.unpack(">I", raw[cursor : cursor + 4])[0]
        kind = raw[cursor + 4 : cursor + 8]
        data = raw[cursor + 8 : cursor + 8 + length]
        cursor += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                ">IIBBBBB", data
            )
        elif kind == b"IDAT":
            payload.extend(data)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type != 6:
        raise AssertionError(f"expected 8-bit RGBA PNG: {path}")
    stride = width * 4
    decoded = zlib.decompress(payload)
    rows: list[bytearray] = []
    offset = 0
    for _ in range(height):
        filter_type = decoded[offset]
        source = decoded[offset + 1 : offset + 1 + stride]
        offset += stride + 1
        previous = rows[-1] if rows else bytearray(stride)
        row = bytearray(stride)
        for index, value in enumerate(source):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                prediction = 0
            elif filter_type == 1:
                prediction = left
            elif filter_type == 2:
                prediction = above
            elif filter_type == 3:
                prediction = (left + above) // 2
            elif filter_type == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                prediction = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
            else:
                raise AssertionError(f"unsupported PNG filter {filter_type}")
            row[index] = (value + prediction) & 0xFF
        rows.append(row)
    return width, height, b"".join(rows)


class MacAppIconTests(unittest.TestCase):
    def test_bundle_declares_existing_native_icon_family(self):
        config = json.loads((ROOT / "app/src-tauri/tauri.conf.json").read_text())
        declared = config["bundle"]["icon"]
        self.assertEqual(
            declared,
            [
                "icons/32x32.png",
                "icons/128x128.png",
                "icons/128x128@2x.png",
                "icons/icon.icns",
                "icons/icon.png",
            ],
        )
        for relative in declared:
            self.assertTrue((ROOT / "app/src-tauri" / relative).is_file(), relative)

    def test_app_icon_sizes_are_exact_rgba_outputs(self):
        expected = {
            "32x32.png": (32, 32),
            "128x128.png": (128, 128),
            "128x128@2x.png": (256, 256),
            "icon.png": (512, 512),
        }
        for name, dimensions in expected.items():
            width, height, rgba = read_rgba_png(ICON_DIR / name)
            self.assertEqual((width, height), dimensions, name)
            corners = (0, width - 1, width * (height - 1), width * height - 1)
            pixels = [rgba[index : index + 4] for index in range(0, len(rgba), 4)]
            self.assertTrue(all(pixels[index][3] == 0 for index in corners), name)

        iconset_sizes = {
            "icon_16x16.png": (16, 16),
            "icon_16x16@2x.png": (32, 32),
            "icon_32x32.png": (32, 32),
            "icon_32x32@2x.png": (64, 64),
            "icon_128x128.png": (128, 128),
            "icon_128x128@2x.png": (256, 256),
            "icon_256x256.png": (256, 256),
            "icon_256x256@2x.png": (512, 512),
            "icon_512x512.png": (512, 512),
            "icon_512x512@2x.png": (1024, 1024),
        }
        for name, dimensions in iconset_sizes.items():
            width, height, _ = read_rgba_png(ICON_DIR / "AppIcon.iconset" / name)
            self.assertEqual((width, height), dimensions, name)

        self.assertEqual((ICON_DIR / "icon.icns").read_bytes()[:4], b"icns")

    def test_menu_bar_template_has_clean_transparent_edges(self):
        for name, (dimensions, minimum_coverage) in {
            "trayTemplate.png": ((18, 18), 0.27),
            "trayTemplate@2x.png": ((36, 36), 0.23),
        }.items():
            width, height, rgba = read_rgba_png(ICON_DIR / name)
            self.assertEqual((width, height), dimensions)
            pixels = [rgba[index : index + 4] for index in range(0, len(rgba), 4)]
            corners = (0, width - 1, width * (height - 1), width * height - 1)
            self.assertTrue(all(pixels[index][3] == 0 for index in corners), name)
            visible = [pixel for pixel in pixels if pixel[3] > 0]
            coverage = len(visible) / len(pixels)
            self.assertGreater(coverage, minimum_coverage, name)
            self.assertLess(coverage, 0.48, name)
            self.assertTrue(
                all(max(pixel[:3]) <= 8 for pixel in visible),
                f"{name} contains light RGB that can fringe under template rendering",
            )

    def test_native_tray_uses_dedicated_template_asset(self):
        native = (ROOT / "app/src-tauri/src/lib.rs").read_text()
        tray_start = native.index('TrayIconBuilder::with_id("hey-jarvis")')
        tray_end = native.index(".on_menu_event", tray_start)
        tray = native[tray_start:tray_end]
        self.assertIn('include_image!("icons/trayTemplate@2x.png")', tray)
        self.assertIn(".icon_as_template(true)", tray)
        self.assertNotIn("default_window_icon", tray)

    def test_vector_master_preserves_approved_geometry_and_palette(self):
        master = (ICON_DIR / "icon.svg").read_text()
        self.assertIn('d="M 540 414 H 620 V 675', master)
        self.assertIn('stroke-width="76"', master)
        self.assertIn('cx="580" cy="295" r="60"', master)
        self.assertEqual(master.count('fill="#f2f0e8"'), 3)
        self.assertIn("#72deb9", master)
        self.assertIn("#0b1110", master)

    def test_menu_bar_master_uses_dedicated_heavier_optical_weights(self):
        master = (ICON_DIR / "tray-template.svg").read_text()
        self.assertIn('d="M 14 16.2 H 21 V 25', master)
        self.assertIn('stroke-width="4.4"', master)
        self.assertIn('<circle cx="17.5" cy="7" r="4.4" stroke-width="2.4"', master)
        self.assertEqual(master.count('width="1.8"'), 3)
        self.assertNotIn('stroke-width="4.4"', (ICON_DIR / "icon.svg").read_text())

    def test_orb_is_centered_on_rendered_platform_not_the_stem(self):
        for name, expected_stroke in (("icon.svg", 76.0), ("tray-template.svg", 4.4)):
            master = (ICON_DIR / name).read_text()
            path = re.search(
                r'<path\s+d="M ([0-9.]+) [0-9.]+ H ([0-9.]+) V', master
            )
            circle = re.search(r'<circle cx="([0-9.]+)"', master)
            stroke = re.search(
                r'<path[^>]+stroke-width="([0-9.]+)"', master, re.DOTALL
            )
            self.assertIsNotNone(path, name)
            self.assertIsNotNone(circle, name)
            self.assertIsNotNone(stroke, name)
            platform_start, stem = map(float, path.groups())
            stroke_width = float(stroke.group(1))
            rendered_left = platform_start - stroke_width / 2
            rendered_right = stem + stroke_width / 2
            rendered_midpoint = (rendered_left + rendered_right) / 2
            self.assertEqual(stroke_width, expected_stroke, name)
            self.assertAlmostEqual(float(circle.group(1)), rendered_midpoint, places=6)
            self.assertNotEqual(float(circle.group(1)), stem, name)

    def test_menu_bar_orb_keeps_a_visible_gap_above_the_heavier_platform(self):
        master = (ICON_DIR / "tray-template.svg").read_text()
        platform = re.search(r'<path\s+d="M [0-9.]+ ([0-9.]+) H', master)
        circle = re.search(
            r'<circle cx="[0-9.]+" cy="([0-9.]+)" r="([0-9.]+)" stroke-width="([0-9.]+)"',
            master,
        )
        stroke = re.search(r'<path[^>]+stroke-width="([0-9.]+)"', master, re.DOTALL)
        self.assertIsNotNone(platform)
        self.assertIsNotNone(circle)
        self.assertIsNotNone(stroke)
        platform_top = float(platform.group(1)) - float(stroke.group(1)) / 2
        orb_y, orb_radius, orb_stroke = map(float, circle.groups())
        orb_bottom = orb_y + orb_radius + orb_stroke / 2
        self.assertGreaterEqual(platform_top - orb_bottom, 1.3)



if __name__ == "__main__":
    unittest.main()
