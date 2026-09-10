"""
Issue: what detect_issues() produces. One per column-problem found.
"""

from dataclasses import dataclass, field


@dataclass
class Issue:
    column: str
    issue_type: str        # "missing_numeric" | "label_inconsistency" | "format_error"
    severity: str           # "low" | "medium" | "high" -- rough, for triage/logging only
    details: dict = field(default_factory=dict)

    def __repr__(self):
        return f"Issue({self.column}, {self.issue_type}, severity={self.severity}, {self.details})"
