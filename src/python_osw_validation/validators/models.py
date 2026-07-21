from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ValidationFinding:
    """Internal validator result that maps to the legacy errors/issues response."""

    message: str
    filename: Optional[str] = None
    feature_index: Optional[Any] = None
    code: str = "VALIDATION_ERROR"
    severity: str = "error"
