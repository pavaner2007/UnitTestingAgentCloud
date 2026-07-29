"""
TechnicalDebtPrioritizationAgent — ranks all code issues, security risks, and drift findings by business impact.

Aggregates findings from Bug Detection, Pattern Detector, and Architecture Drift, then applies
a priority matrix formula to estimate fix times and recommended fix sequence.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.v2_schemas import (
    TechnicalDebtItem,
    TechnicalDebtReport,
)

logger = logging.getLogger(__name__)


class TechnicalDebtPrioritizationAgent:
    """Prioritizes and ranks technical debt items by business risk, fix effort, and security impact."""

    def prioritize_debt(
        self,
        report_data: dict[str, Any],
        drift_report: dict[str, Any] | None = None,
    ) -> TechnicalDebtReport:
        items: list[TechnicalDebtItem] = []

        code_insights = report_data.get("code_insights") or {}
        issues = code_insights.get("issues") or []
        patterns = code_insights.get("notable_patterns") or []

        # ── 1. Ingest Bug Detection issues ───────────────────────────────────
        for iss in issues:
            sev = (iss.get("severity") or "medium").upper()
            rule = iss.get("rule") or "Static Smell"
            msg = iss.get("message") or "Code issue detected"
            file_p = iss.get("file") or "unknown"
            line_n = iss.get("line")

            if sev == "HIGH":
                p_score = 90.0
                est_time = "30 mins"
                why = "High severity code bug or potential runtime exception."
            elif sev == "MEDIUM":
                p_score = 60.0
                est_time = "15 mins"
                why = "Medium risk code smell affecting maintainability."
            else:
                p_score = 30.0
                est_time = "10 mins"
                why = "Minor code style or convention finding."

            items.append(
                TechnicalDebtItem(
                    rank=0,  # Computed after sorting
                    title=f"Fix {rule} in `{file_p.split('/')[-1]}`",
                    category="Bug",
                    severity=sev if sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "MEDIUM",
                    file_path=file_p,
                    line_number=line_n,
                    priority_score=p_score,
                    estimated_fix_time=est_time,
                    why_fix_first=why,
                    suggested_fix=iss.get("suggestion") or f"Resolve {msg} according to standard coding practices.",
                )
            )

        # ── 2. Ingest Architecture Drift violations ───────────────────────────
        if drift_report:
            violations = drift_report.get("violations") or []
            for v in violations:
                sev = (v.get("severity") or "WARNING").upper()
                rule_id = v.get("rule_id") or "DRIFT"
                viol_files = v.get("violating_files") or ["architecture"]

                p_score = 95.0 if sev == "CRITICAL" else (70.0 if sev == "WARNING" else 40.0)
                est_time = "2 hours" if sev == "CRITICAL" else "45 mins"

                items.append(
                    TechnicalDebtItem(
                        rank=0,
                        title=f"Resolve {v.get('title', 'Architectural Drift')}",
                        category="Architecture Drift",
                        severity=sev if sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "HIGH",
                        file_path=viol_files[0],
                        line_number=1,
                        priority_score=p_score,
                        estimated_fix_time=est_time,
                        why_fix_first=f"Architectural drift violation ({rule_id}) increases coupling and system fragility.",
                        suggested_fix=v.get("suggested_fix") or "Refactor code to conform to architectural boundaries.",
                    )
                )

        # ── 3. Ingest Dangerous Patterns (Hardcoded Secrets / TODOs) ──────────
        for pat in patterns:
            pat_str = str(pat)
            lower = pat_str.lower()
            if "hardcoded" in lower:
                items.append(
                    TechnicalDebtItem(
                        rank=0,
                        title="Remove Hardcoded Secret / Key",
                        category="Security",
                        severity="CRITICAL",
                        file_path=pat_str.split(" in ")[-1] if " in " in pat_str else "Config",
                        line_number=1,
                        priority_score=99.0,
                        estimated_fix_time="20 mins",
                        why_fix_first="Exposed secrets in code pose an immediate security risk if committed to git.",
                        suggested_fix="Extract credentials into environment variables (`.env`).",
                    )
                )
            elif "todo" in lower or "fixme" in lower or "hack" in lower:
                items.append(
                    TechnicalDebtItem(
                        rank=0,
                        title=f"Resolve Developer Placeholder: {pat_str}",
                        category="Tech Debt",
                        severity="LOW",
                        file_path=pat_str.split(" in ")[-1] if " in " in pat_str else "Codebase",
                        line_number=1,
                        priority_score=25.0,
                        estimated_fix_time="15 mins",
                        why_fix_first="Unfinished developer notes or hacks can lead to unexpected edge-case failures.",
                        suggested_fix="Complete the missing implementation or refactor temporary hack.",
                    )
                )

        # Sort by priority score descending
        items.sort(key=lambda x: x.priority_score, reverse=True)

        # Assign rank indices 1, 2, 3...
        for idx, item in enumerate(items, start=1):
            item.rank = idx

        # Estimate total fix hours
        total_hours = 0.0
        for item in items:
            if "hour" in item.estimated_fix_time:
                try:
                    total_hours += float(item.estimated_fix_time.split()[0])
                except Exception:
                    total_hours += 1.0
            else:
                total_hours += 0.35  # ~20 mins default

        return TechnicalDebtReport(
            total_debt_items=len(items),
            estimated_total_fix_hours=round(total_hours, 1),
            items=items,
        )
