from typing import List, Dict, Optional
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus
from .evaluator import Evaluator
import os

class CheckerPipeline:
    def __init__(self, strategies: List[VerificationStrategy]):
        self.strategies = strategies
        self.evaluator = Evaluator()

    def check_files(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False, max_workers: int = 4) -> List[ModCheckResult]:
        """
        Collect evidence from all strategies and evaluate the final result.
        """
        
        # Dictionary to hold evidence for each file
        file_evidence: Dict[str, List] = {fp: [] for fp in file_paths}
        
        # 1. Collect evidence from all strategies
        # We can run strategies sequentially, but inside each strategy they might do batch processing.
        for strategy in self.strategies:
            try:
                # Use batch_collect_evidence if available (Base class has default implementation)
                results = strategy.batch_collect_evidence(file_paths, target_mc, expected_loader, relaxed)
                
                for fp, evs in results.items():
                    if fp in file_evidence:
                        file_evidence[fp].extend(evs)
            except Exception as e:
                print(f"Strategy {strategy} failed: {e}")
                
        # 2. Evaluate results
        final_results = []
        for fp in file_paths:
            evs = file_evidence.get(fp, [])
            file_name = os.path.basename(fp)
            result = self.evaluator.evaluate(fp, evs, file_name)
            final_results.append(result)
            
        return final_results
