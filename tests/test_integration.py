import unittest
import os
import sys
import tempfile
import json
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mc_mod_compat.common import CheckStatus, ModCheckResult
from mc_mod_compat.checker.pipeline import CheckerPipeline
from mc_mod_compat.checker.local import LocalVerificationStrategy
from mc_mod_compat.checker.online import OnlineVerificationStrategy

class TestIntegration(unittest.TestCase):
    def setUp(self):
        # Create a dummy file
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jar")
        self.test_file.write(b"dummy content")
        self.test_file.close()
        
    def tearDown(self):
        if os.path.exists(self.test_file.name):
            os.remove(self.test_file.name)
            
    def test_pipeline_local_fallback(self):
        # Mock API clients to return nothing (simulating not found online)
        mock_mr = MagicMock()
        mock_mr.get_versions_by_hashes.return_value = {}
        
        mock_cf = MagicMock()
        mock_cf.get_fingerprint_matches.return_value = {}
        
        # Strategies
        online_strat = OnlineVerificationStrategy(mock_mr, mock_cf)
        local_strat = LocalVerificationStrategy()
        
        # Pipeline
        pipeline = CheckerPipeline([online_strat, local_strat])
        
        # Run check
        results = pipeline.check_files(
            [self.test_file.name], 
            target_mc="1.20.1", 
            expected_loader="fabric"
        )
        
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res.file_path, self.test_file.name)
        # Since the file is dummy, local strat should return UNKNOWN or fail silently and pipeline wraps it as UNKNOWN
        # Actually local strat returns None on exception (zip error), so it won't be in results from local_strat.
        # Pipeline then adds it as UNKNOWN at the end.
        self.assertEqual(res.status, CheckStatus.UNKNOWN)
        
    def test_pipeline_online_success(self):
        # Mock API to return success
        mock_mr = MagicMock()
        # Modrinth returns dict of hash -> version_data
        mock_mr.get_versions_by_hashes.return_value = {
            "some_hash": {
                "game_versions": ["1.20.1"],
                "loaders": ["fabric"],
                "name": "Test Mod",
                "version_number": "1.0.0",
                "id": "test_id"
            }
        }
        
        # We need to mock compute_sha1 to return "some_hash"
        # Since compute_sha1 is imported in online.py, we need to patch it there.
        with unittest.mock.patch('mc_mod_compat.checker.online.compute_sha1', return_value="some_hash"):
             online_strat = OnlineVerificationStrategy(mock_mr, None)
             pipeline = CheckerPipeline([online_strat])
             
             results = pipeline.check_files(
                [self.test_file.name], 
                target_mc="1.20.1", 
                expected_loader="fabric"
             )
             
             self.assertEqual(len(results), 1)
             res = results[0]
             self.assertEqual(res.status, CheckStatus.OK)
             self.assertEqual(res.mod_name, "Test Mod")
             self.assertEqual(res.source, "modrinth")

if __name__ == '__main__':
    unittest.main()
