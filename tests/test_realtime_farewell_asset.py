from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from src.realtime_farewell_asset import (
    CANONICAL_FAREWELL_ASSET,
    CANONICAL_FAREWELL_MANIFEST,
    FAREWELL_PHRASE,
    load_selected_asset,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RealtimeFarewellAssetTests(unittest.TestCase):
    def test_selected_mandarin_farewell_is_valid_and_owner_approved(self):
        data, manifest = load_selected_asset(
            PROJECT_ROOT / CANONICAL_FAREWELL_ASSET,
            PROJECT_ROOT / CANONICAL_FAREWELL_MANIFEST,
        )
        self.assertEqual(manifest["phrase"], FAREWELL_PHRASE)
        self.assertEqual(manifest["candidate"], "candidate-03")
        self.assertEqual(manifest["voice"], "alloy")
        self.assertEqual(manifest["playback_gain"], 0.5)
        self.assertEqual(manifest["duration_ms"], 580)
        self.assertEqual(manifest["leading_trim_ms"], 20)
        self.assertTrue(manifest["selected_by_owner"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["sha256"])


if __name__ == "__main__":
    unittest.main()
