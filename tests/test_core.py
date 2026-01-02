import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mc_mod_compat.core.version_range import McVersion, VersionRange
from mc_mod_compat.checker.evaluator import Evaluator
from mc_mod_compat.common import Evidence, SupportLevel

class TestVersionRange(unittest.TestCase):
    def test_mc_version_parsing(self):
        v = McVersion("1.20.1")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 20)
        self.assertEqual(v.patch, 1)
        
        v2 = McVersion("1.19")
        self.assertEqual(v2.major, 1)
        self.assertEqual(v2.minor, 19)
        self.assertEqual(v2.patch, 0) # Default patch 0

    def test_mc_version_comparison(self):
        self.assertTrue(McVersion("1.20.1") > McVersion("1.20"))
        self.assertTrue(McVersion("1.20.1") == McVersion("1.20.1"))
        self.assertTrue(McVersion("1.19.4") < McVersion("1.20"))
        
    def test_range_exact(self):
        vr = VersionRange("1.20.1")
        self.assertTrue(vr.contains("1.20.1"))
        self.assertFalse(vr.contains("1.20.2"))
        
    def test_range_wildcard(self):
        vr = VersionRange("1.20.x")
        self.assertTrue(vr.contains("1.20.0"))
        self.assertTrue(vr.contains("1.20.1"))
        self.assertTrue(vr.contains("1.20.99"))
        self.assertFalse(vr.contains("1.21"))
        self.assertFalse(vr.contains("1.19.9"))

    def test_range_comparison_operators(self):
        vr = VersionRange(">=1.20")
        self.assertTrue(vr.contains("1.20"))
        self.assertTrue(vr.contains("1.20.1"))
        self.assertTrue(vr.contains("1.21"))
        self.assertFalse(vr.contains("1.19.9"))
        
        vr2 = VersionRange("<1.19")
        self.assertTrue(vr2.contains("1.18.2"))
        self.assertFalse(vr2.contains("1.19"))
        
    def test_range_interval(self):
        # [1.20, 1.20.4)
        vr = VersionRange("[1.20, 1.20.4)")
        self.assertTrue(vr.contains("1.20"))
        self.assertTrue(vr.contains("1.20.1"))
        self.assertTrue(vr.contains("1.20.3"))
        self.assertFalse(vr.contains("1.20.4"))
        self.assertFalse(vr.contains("1.19.9"))

class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = Evaluator()
        
    def test_single_evidence(self):
        ev = Evidence(
            source="Modrinth",
            confidence=1.0,
            level=SupportLevel.CONFIRMED,
            reason="Hash match"
        )
        res = self.evaluator.evaluate("test.jar", [ev], "test.jar")
        self.assertEqual(res.level, SupportLevel.CONFIRMED)
        self.assertEqual(res.source, "Modrinth")
        
    def test_conflict_resolution(self):
        # Modrinth says CONFIRMED (1.0), Metadata says POSSIBLE (0.6)
        ev1 = Evidence(
            source="Modrinth",
            confidence=1.0,
            level=SupportLevel.CONFIRMED,
            reason="Hash match"
        )
        ev2 = Evidence(
            source="Metadata",
            confidence=0.6,
            level=SupportLevel.POSSIBLE,
            reason="Declared dependency"
        )
        res = self.evaluator.evaluate("test.jar", [ev1, ev2], "test.jar")
        self.assertEqual(res.level, SupportLevel.CONFIRMED)
        
    def test_conflict_resolution_override(self):
        # Modrinth says UNSUPPORTED (1.0), Metadata says POSSIBLE (0.6)
        # Should trust Modrinth
        ev1 = Evidence(
            source="Modrinth",
            confidence=1.0,
            level=SupportLevel.UNSUPPORTED,
            reason="Explicit incompatibility"
        )
        ev2 = Evidence(
            source="Metadata",
            confidence=0.6,
            level=SupportLevel.POSSIBLE,
            reason="Declared dependency"
        )
        res = self.evaluator.evaluate("test.jar", [ev1, ev2], "test.jar")
        self.assertEqual(res.level, SupportLevel.UNSUPPORTED)

if __name__ == '__main__':
    unittest.main()
