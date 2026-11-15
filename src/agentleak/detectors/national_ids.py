# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""National and health identifiers that carry a check digit.

Each rule is a shape plus a validator from :mod:`.checksums`. Where the shape
alone is distinctive (a formatted CPF ``529.982.247-25``, a codice fiscale) the
validator is enough. Where it is not — nine or eleven bare digits are also
order numbers, phone numbers and timestamps — the rule also needs the word
that names the identifier within a few characters before it ("BSN", "PESEL",
"Steuer-ID"). That is how people write them, and it keeps a one-in-ten
checksum from turning every eleventh number into a finding.

Read by :class:`~agentleak.detectors.pii.PIIDetector`; the rule ids end up in
``Finding.metadata["rule"]``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..core.detector import Severity
from . import checksums as cs


@dataclass(frozen=True)
class IdRule:
    """One identifier format."""

    rule: str
    country: str
    label: str
    data_type: str
    pattern: re.Pattern[str]
    validator: Callable[[str], bool]
    confidence: float
    severity: Severity = Severity.HIGH
    # Whether the pattern requires a naming keyword (documentation only; the
    # keyword, when needed, is part of ``pattern``).
    keyword_gated: bool = False
    # Lower-case substrings, one of which a keyword-gated match must contain;
    # checked with ``in`` before the pattern runs.
    hints: tuple[str, ...] = ()

    @property
    def recommendation(self) -> str:
        if self.data_type == "business_identifier":
            return (f"{self.label} identifies a business; for a sole trader it identifies a "
                    "person. Keep it out of channels that do not need it.")
        if self.data_type == "health_identifier":
            return f"Remove or mask the {self.label} before internal channels; it keys medical records."
        return f"Never transmit a full {self.label}; tokenize it."


def _kw(words: str, value: str) -> re.Pattern[str]:
    """``words`` (a case-insensitive alternation), then at most 25 characters
    of label punctuation ("number:", "n°", "#"), then the captured value."""
    return re.compile(
        r"(?<![\w])(?i:" + words + r")(?![\w])[^\d\n]{0,25}?(?<![\w.-])(" + value + r")(?![\w-])"
    )


def _bare(value: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w.-])(" + value + r")(?![\w-]|\.\d)")


RULES: tuple[IdRule, ...] = (
    IdRule(
        "fr_nir", "FR", "French social security number (NIR)", "national_id",
        _bare(r"[1-478][ .]?\d{2}[ .]?(?:0[1-9]|1[0-2]|[2-9]\d)[ .]?(?:\d{2}|2[ABab])[ .]?\d{3}[ .]?\d{3}[ .]?\d{2}"),
        cs.fr_nir, 0.9,
    ),
    IdRule(
        "it_codice_fiscale", "IT", "Italian codice fiscale", "national_id",
        re.compile(r"(?<![A-Za-z0-9])([A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}"
                   r"[A-Z][0-9LMNPQRSTUV]{3}[A-Z])(?![A-Za-z0-9])"),
        cs.it_codice_fiscale, 0.92,
    ),
    IdRule(
        "de_steuer_id", "DE", "German tax identification number (Steuer-ID)", "national_id",
        _kw(r"steuer[- ]?id(?:entifikationsnummer)?|steuerliche[ _]identifikationsnummer|"
            r"identifikationsnummer|idnr|tax[ _-]?id|tin",
            r"\d{2}[ ]?\d{3}[ ]?\d{3}[ ]?\d{3}"),
        cs.de_steuer_id, 0.9, keyword_gated=True,
        hints=('steuer', 'identifikation', 'idnr', 'tax', 'tin'),
    ),
    IdRule(
        "uk_nhs_number", "GB", "NHS number", "health_identifier",
        _kw(r"nhs", r"\d{3}[ -]?\d{3}[ -]?\d{4}"),
        cs.uk_nhs, 0.9, Severity.CRITICAL, keyword_gated=True,
        hints=('nhs',),
    ),
    IdRule(
        "nl_bsn", "NL", "Dutch citizen service number (BSN)", "national_id",
        _kw(r"bsn|burgerservicenummer|sofi[- ]?nummer", r"\d{4}\.?\d{2}\.?\d{3}|\d{9}"),
        cs.nl_bsn, 0.9, keyword_gated=True,
        hints=('bsn', 'burgerservice', 'sofi'),
    ),
    IdRule(
        "be_national_number", "BE", "Belgian national register number", "national_id",
        _bare(r"\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}"),
        cs.be_national_number, 0.9,
    ),
    IdRule(
        "be_national_number_labelled", "BE", "Belgian national register number", "national_id",
        _kw(r"rijksregisternummer|num[ée]ro national|national (?:register )?number|niss|insz|"
            r"registre national",
            r"\d{11}|\d{6}[ -]\d{3}[ -]?\d{2}"),
        cs.be_national_number, 0.88, keyword_gated=True,
        hints=('rijksregister', 'national', 'niss', 'insz', 'registre'),
    ),
    IdRule(
        "pl_pesel", "PL", "Polish PESEL", "national_id",
        _kw(r"pesel", r"\d{11}"),
        cs.pl_pesel, 0.92, keyword_gated=True,
        hints=('pesel',),
    ),
    IdRule(
        "se_personnummer", "SE", "Swedish personal identity number", "national_id",
        _kw(r"personnummer|samordningsnummer|personal identity number|pnr",
            r"(?:\d{2})?\d{6}[-+ ]?\d{4}"),
        cs.se_personnummer, 0.9, keyword_gated=True,
        hints=('personnummer', 'samordning', 'personal identity', 'pnr'),
    ),
    IdRule(
        "br_cpf", "BR", "Brazilian CPF", "national_id",
        _bare(r"\d{3}\.\d{3}\.\d{3}-\d{2}"),
        cs.br_cpf, 0.92,
    ),
    IdRule(
        "br_cpf_labelled", "BR", "Brazilian CPF", "national_id",
        _kw(r"cpf", r"\d{11}"),
        cs.br_cpf, 0.9, keyword_gated=True,
        hints=('cpf',),
    ),
    IdRule(
        "br_cnpj", "BR", "Brazilian company registry number (CNPJ)", "business_identifier",
        _bare(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"),
        cs.br_cnpj, 0.9, Severity.LOW,
    ),
    IdRule(
        "in_aadhaar", "IN", "Aadhaar number", "national_id",
        _kw(r"aadhaar|aadhar|uidai|uid", r"[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}"),
        cs.in_aadhaar, 0.9, keyword_gated=True,
        hints=('aadha', 'uid'),
    ),
    IdRule(
        "au_tfn", "AU", "Australian tax file number", "national_id",
        _kw(r"tfn|tax[ _]file[ _](?:number|no)", r"\d{3}[ -]?\d{3}[ -]?\d{2,3}"),
        cs.au_tfn, 0.9, keyword_gated=True,
        hints=('tfn', 'tax'),
    ),
    IdRule(
        "us_ssn_labelled", "US", "social security number", "ssn",
        _kw(r"ssn|social[ _]security(?:[ _](?:number|no))?", r"\d{9}"),
        cs.us_ssn, 0.85, keyword_gated=True,
        hints=('ssn', 'social'),
    ),
)


_DIGIT_RE = re.compile(r"\d")


def scan(text: str) -> list[tuple[IdRule, str, tuple[int, int]]]:
    """Every validated identifier in ``text`` as ``(rule, value, span)``."""
    out: list[tuple[IdRule, str, tuple[int, int]]] = []
    if not _DIGIT_RE.search(text):
        return out
    lowered = text.lower()
    for rule in RULES:
        if rule.hints and not any(h in lowered for h in rule.hints):
            continue
        for m in rule.pattern.finditer(text):
            value = m.group(1)
            if rule.validator(value):
                out.append((rule, value, m.span(1)))
    return out


__all__ = ["IdRule", "RULES", "scan"]
