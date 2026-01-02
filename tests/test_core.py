import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mc_mod_compat.core.metadata import heuristic_detect_mc_versions, eval_simple_constraints

class TestMetadata(unittest.TestCase):
    def test_heuristic_versions(self):
        self.assertEqual(heuristic_detect_mc_versions("mod-1.20.1.jar"), ["1.20.1"])
        self.assertEqual(heuristic_detect_mc_versions("mymod-fabric-1.19.2.jar"), ["1.19.2"])
        
    def test_constraints(self):
        self.assertTrue(eval_simple_constraints("1.20.1", "1.20.1"))
        self.assertTrue(eval_simple_constraints("1.20.1", "*"))
        # This is the "simple" logic we kept
        self.assertTrue(eval_simple_constraints("1.20.1", "1.20")) 
        self.assertFalse(eval_simple_constraints("1.19", "1.20"))

if __name__ == '__main__':
    unittest.main()
