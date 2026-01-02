from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..common import ModCheckResult, CheckStatus, Evidence

class VerificationStrategy(ABC):
    @abstractmethod
    def verify(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Optional[ModCheckResult]:
        """Deprecated: Use collect_evidence instead."""
        pass

    @abstractmethod
    def collect_evidence(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> List[Evidence]:
        pass

    def batch_verify(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Dict[str, ModCheckResult]:
        """
        Default implementation just calls verify in a loop.
        Override for API batching.
        """
        results = {}
        for fp in file_paths:
            res = self.verify(fp, target_mc, expected_loader, relaxed)
            if res:
                results[fp] = res
        return results

    def batch_collect_evidence(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Dict[str, List[Evidence]]:
        results = {}
        for fp in file_paths:
            evs = self.collect_evidence(fp, target_mc, expected_loader, relaxed)
            if evs:
                results[fp] = evs
        return results
