"""Pure deterministic contract clause validators — zero LLM calls, zero network I/O."""
from __future__ import annotations

from legal_agent.schemas.legal import LegalContract, RiskFlag, RiskLevel


def check_required_fields(contract: LegalContract) -> list[str]:
    """Return warning strings for commonly expected fields that are absent.

    Checks effective_date, governing_law, and expiration_date for None.

    Args:
        contract: The extracted LegalContract to inspect.

    Returns:
        List of human-readable warning strings; empty if all fields present.
    """
    fields: list[tuple[str, str | None]] = [
        ("effective_date", contract.effective_date),
        ("governing_law", contract.governing_law),
        ("expiration_date", contract.expiration_date),
    ]
    return [
        f"{name} not extracted — manual review recommended"
        for name, value in fields
        if value is None
    ]


def score_limitation_of_liability(clause: str | None) -> RiskFlag | None:
    """Score the limitation of liability clause for risk.

    Args:
        clause: Verbatim clause text or None if not found.

    Returns:
        RiskFlag if a risk is detected, else None.
    """
    if clause is None:
        return RiskFlag(
            clause_type="limitation_of_liability",
            risk_level=RiskLevel.HIGH,
            reason="No limitation of liability clause found in contract.",
            suggested_action="Escalate to legal counsel before signing.",
        )
    if len(clause) < 50:
        return RiskFlag(
            clause_type="limitation_of_liability",
            risk_level=RiskLevel.MEDIUM,
            reason="Limitation of liability clause is unusually short — may be incomplete.",
            suggested_action="Request full clause text from counterparty.",
        )
    return None


def score_termination_risk(
    termination_for_convenience: bool,
    most_favored_nation: bool,
) -> list[RiskFlag]:
    """Score termination and MFN clauses for risk.

    Args:
        termination_for_convenience: True if such a clause is present.
        most_favored_nation: True if an MFN clause is present.

    Returns:
        List of RiskFlags; may be empty.
    """
    flags: list[RiskFlag] = []
    if not termination_for_convenience:
        flags.append(RiskFlag(
            clause_type="termination_for_convenience",
            risk_level=RiskLevel.MEDIUM,
            reason="No termination for convenience clause — exit may require cause.",
            suggested_action="Negotiate termination for convenience clause.",
        ))
    if most_favored_nation:
        flags.append(RiskFlag(
            clause_type="most_favored_nation",
            risk_level=RiskLevel.MEDIUM,
            reason=(
                "MFN clause detected — pricing obligations may be triggered by other deals."
            ),
            suggested_action="Review MFN scope with commercial team.",
        ))
    return flags


def compute_overall_risk(flags: list[RiskFlag]) -> RiskLevel:
    """Compute the highest risk level present across all RiskFlags.

    Args:
        flags: All RiskFlags produced for a contract.

    Returns:
        RiskLevel.HIGH if any flag is HIGH, MEDIUM if any is MEDIUM, else LOW.
    """
    if any(f.risk_level == RiskLevel.HIGH for f in flags):
        return RiskLevel.HIGH
    if any(f.risk_level == RiskLevel.MEDIUM for f in flags):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def run_full_validation(
    contract: LegalContract,
) -> tuple[list[RiskFlag], RiskLevel, list[str]]:
    """Run all validators and return consolidated flags, risk level, and warnings.

    Args:
        contract: The extracted LegalContract to validate.

    Returns:
        Tuple of (risk_flags, overall_risk_level, warnings).
    """
    warnings = check_required_fields(contract)
    flags: list[RiskFlag] = []
    lol_flag = score_limitation_of_liability(contract.limitation_of_liability)
    if lol_flag:
        flags.append(lol_flag)
    flags.extend(
        score_termination_risk(
            contract.termination_for_convenience,
            contract.most_favored_nation,
        )
    )
    return flags, compute_overall_risk(flags), warnings
