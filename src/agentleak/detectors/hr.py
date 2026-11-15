# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""HR data detector: salaries, sick leave, performance reviews, disciplinary
actions, and complaints/grievances.
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity
from .context import matches_for as context_matches

# Tolerant separator: handles flattened "key: value", JSON quotes, and "=".
_SEP = r"[\"'\s:=#-]*"

SALARY_RE = re.compile(
    r"(?i)\b(?:salary|salaire|compensation|base pay)" + _SEP + r"\$?([0-9][0-9,]{3,})"
)
# A pay figure that says it is pay: an amount, a currency, and "gross" or "net"
# in one of the supported languages ("52 000 € brut annuel", "45.000 euros
# brutos anuales", "$95,000 gross per year"). Without the gross/net word the
# same amount is a rent, an invoice or a price, so it is not taken.
_AMOUNT = r"\d{1,3}(?:[ .,\u00a0\u202f]\d{3})+(?:[.,]\d{2})?|\d{4,7}(?:[.,]\d{2})?"
_CURRENCY = r"€|\$|£|eur(?:os?)?|usd|cad|chf|gbp|dollars?|livres?"
_GROSS_NET = (
    r"brut(?:e|s|es)?|net(?:te|s|tes)?|gross|before tax|after tax|brutos?|brutas?|netos?|"
    r"netas?|l[íi]quidos?|brutto|netto|lordo|lordi|bruto"
)
SALARY_EXPR_RE = re.compile(
    r"(?i)(?<![\w.,])(?:(?:" + _CURRENCY + r")\s?(?:" + _AMOUNT + r")|(?:" + _AMOUNT + r")\s?(?:"
    + _CURRENCY + r"))(?:\s*(?:/|par|per|al|a|por|pro|im|ao|all')?\s*"
    r"(?:an|année|annuel(?:le)?s?|mois|mensuel(?:le)?s?|year|yr|month|año|mes|mensuales?|"
    r"anuales?|jahr|monat|anno|mese|ano|mês))?\s+(?:" + _GROSS_NET + r")(?!\w)"
)
SICK_LEAVE_RE = re.compile(r"(?i)\b(?:sick leave|medical leave|congé maladie|stress leave|fmla)\b")
PERFORMANCE_RE = re.compile(
    r"(?i)\b(?:performance review|performance rating|performance plan|pip|évaluation|underperform\w*)\b"
)
DISCIPLINARY_RE = re.compile(
    r"(?i)\b(?:disciplinary|written warning|final warning|misconduct|reprimand|mesure disciplinaire)\b"
)
COMPLAINT_RE = re.compile(r"(?i)\b(?:grievance|harassment complaint|hr complaint|plainte|whistleblow\w*)\b")
TERMINATION_RE = re.compile(r"(?i)\b(?:terminated|termination|laid off|let go|severance)\b")


class HRDetector(Detector):
    name = "hr_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []

        for m in SALARY_RE.finditer(text):
            matches.append(self._match(
                data_type="salary", severity=Severity.HIGH, confidence=0.75,
                matched_value=m.group(1),
                recommendation="Salary data should only reach explicitly authorized agents.",
            ))

        for m in SALARY_EXPR_RE.finditer(text):
            matches.append(self._match(
                data_type="salary", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(), rule="salary_gross_net",
                recommendation="Salary data should only reach explicitly authorized agents.",
            ))

        for m in SICK_LEAVE_RE.finditer(text):
            matches.append(self._match(
                data_type="sick_leave", severity=Severity.HIGH, confidence=0.75,
                matched_value=m.group(0),
                recommendation="Health-related leave is sensitive; keep it out of general channels.",
            ))

        for m in PERFORMANCE_RE.finditer(text):
            matches.append(self._match(
                data_type="performance_review", severity=Severity.MEDIUM, confidence=0.7,
                matched_value=m.group(0),
                recommendation="Do not expose performance assessments outside authorized review flows.",
            ))

        for m in DISCIPLINARY_RE.finditer(text):
            matches.append(self._match(
                data_type="disciplinary_action", severity=Severity.HIGH, confidence=0.8,
                matched_value=m.group(0),
                recommendation="Disciplinary records must not appear in shared memory or logs.",
            ))

        for m in COMPLAINT_RE.finditer(text):
            matches.append(self._match(
                data_type="hr_complaint", severity=Severity.MEDIUM, confidence=0.7,
                matched_value=m.group(0),
                recommendation="Protect complainant identity; restrict complaint details to HR agents.",
            ))

        for m in TERMINATION_RE.finditer(text):
            matches.append(self._match(
                data_type="employment_status", severity=Severity.MEDIUM, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Employment-status changes are confidential until officially communicated.",
            ))

        # "her salary is $128,000 a year", "il gagne 65000 EUR": an amount
        # named by a pay noun, or by an earning verb with a currency or period.
        matches.extend(context_matches(self.name, text, frozenset({"salary"}), matches))
        return matches
