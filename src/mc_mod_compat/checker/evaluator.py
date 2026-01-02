from typing import List, Optional
from ..common import ModCheckResult, CheckStatus, SupportLevel, Evidence

class Evaluator:
    def evaluate(self, file_path: str, evidences: List[Evidence], file_name: str) -> ModCheckResult:
        if not evidences:
            return ModCheckResult(
                file_name=file_name,
                file_path=file_path,
                status=CheckStatus.UNKNOWN,
                reason="No evidence found",
                level=SupportLevel.UNKNOWN
            )

        # Sort by confidence descending
        sorted_evidences = sorted(evidences, key=lambda e: e.confidence, reverse=True)
        
        # Pick the highest confidence evidence
        # But we need to handle conflicts? 
        # User says: Modrinth (5*) > CF (4*) > Metadata (3*).
        # So we basically trust the highest confidence source.
        
        best = sorted_evidences[0]
        
        # If we have a CONFIRMED or UNSUPPORTED from a high confidence source, we take it.
        # If the best we have is POSSIBLE (e.g. from local metadata), we take it.
        
        # Map SupportLevel to legacy CheckStatus
        status = CheckStatus.UNKNOWN
        if best.level == SupportLevel.CONFIRMED:
            status = CheckStatus.OK
        elif best.level == SupportLevel.LIKELY:
            status = CheckStatus.OK
        elif best.level == SupportLevel.POSSIBLE:
            status = CheckStatus.OK # Or maybe warning? User says POSSIBLE is "Theoretical support"
        elif best.level == SupportLevel.UNSUPPORTED:
            # Need to know WHY (MC or Loader) to map to WRONG_MC / WRONG_LOADER
            # We can guess from reason text or just use WRONG_MC as generic fail
            if "loader" in best.reason.lower():
                status = CheckStatus.WRONG_LOADER
            else:
                status = CheckStatus.WRONG_MC
        
        return ModCheckResult(
            file_name=file_name,
            file_path=file_path,
            status=status,
            reason=best.reason,
            source=best.source,
            level=best.level,
            evidence=evidences
        )
