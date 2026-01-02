from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus

class CheckerPipeline:
    def __init__(self, strategies: List[VerificationStrategy]):
        self.strategies = strategies

    def check_files(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False, max_workers: int = 4) -> List[ModCheckResult]:
        """
        Run strategies in order. If a strategy returns a result (and it's definitive?), use it.
        Actually, we usually want to try Online first, then Local if not found.
        """
        
        # We need to process files that haven't been resolved yet.
        pending_files = set(file_paths)
        final_results: Dict[str, ModCheckResult] = {}
        
        for strategy in self.strategies:
            if not pending_files:
                break
                
            # Convert set to list for batch processing
            current_batch = list(pending_files)
            
            # Run batch verify
            # Note: Strategies should return results for files they found.
            # If a file is NOT found/checked by strategy, it shouldn't be in the result dict.
            results = strategy.batch_verify(current_batch, target_mc, expected_loader, relaxed)
            
            for fp, res in results.items():
                # If we got a valid result (even if it's WRONG_MC, it's a result)
                # We accept it.
                # However, if status is UNKNOWN or SKIPPED, maybe we want to continue to next strategy?
                # For now, let's assume strategies return definitive results if they can.
                if res.status != CheckStatus.UNKNOWN:
                    final_results[fp] = res
                    if fp in pending_files:
                        pending_files.remove(fp)
        
        # Any remaining files are Unknown
        results_list = list(final_results.values())
        for fp in pending_files:
            results_list.append(ModCheckResult(
                file_name=fp.split("/")[-1], # approximate
                file_path=fp,
                status=CheckStatus.UNKNOWN,
                reason="all_strategies_failed"
            ))
            
        return results_list
