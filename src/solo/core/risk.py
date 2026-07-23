"""Risk classification — R0/R1/R2/R3 keyword-based classifier.

Reuses the R3_TERMS / R2_TERMS / R1_TERMS taxonomy from PAIOS risk module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from .enums import RiskLevel


# High-risk irreversible action terms (R3)
R3_TERMS: tuple[str, ...] = (
    "delete important", "delete all", "delete permanently",
    "format disk", "wipe drive", "destroy data",
    "irreversible", "irrevocable", "unrecoverable",
    "rm -rf", "remove recursively",
)

# Moderate-risk write action terms (R2)
R2_TERMS: tuple[str, ...] = (
    "write", "overwrite", "modify", "update",
    "rename", "move", "copy",
    "execute", "run script", "install",
    "create file", "upload", "download",
    "change config", "set", "configure",
    "send email", "post", "publish",
    "delete file", "remove file",
    "delete",
)

# Low-risk read/minimal terms (R1)
R1_TERMS: tuple[str, ...] = (
    "read", "list", "search", "query",
    "check", "inspect", "lookup",
    "get info", "stat", "status",
)


@dataclass
class RiskAssessment:
    """Result of a risk classification assessment."""
    level: RiskLevel
    reasons: tuple[str, ...] = field(default_factory=tuple)


class RiskClassifier:
    """Classify task objectives into risk levels R0-R3 by keyword matching."""

    def classify(self, objective: str, task_type: str = "general") -> RiskAssessment:
        """Classify an objective string into a risk level."""
        obj_lower = objective.lower()
        reasons: list[str] = []

        # Check R3 first (most restrictive)
        for term in R3_TERMS:
            if term in obj_lower:
                reasons.append(f"high_risk_or_irreversible_action")
                return RiskAssessment(level=RiskLevel.R3, reasons=(tuple(reasons)))

        # Check R2
        for term in R2_TERMS:
            if term in obj_lower:
                reasons.append(f"write_with_moderate_risk")
                return RiskAssessment(level=RiskLevel.R2, reasons=(tuple(reasons)))

        # Check R1
        for term in R1_TERMS:
            if term in obj_lower:
                reasons.append(f"read_with_minimal_side_effect")
                return RiskAssessment(level=RiskLevel.R1, reasons=(tuple(reasons)))

        # Default: R0 — read-only or no side effects
        reasons.append("read_only_or_no_side_effect")
        return RiskAssessment(level=RiskLevel.R0, reasons=(tuple(reasons)))
