# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Key-name-aware sensitivity detector.

Dictionary and pattern detectors only fire when they *recognise the value*
(``diabetes``, a NAM shape, an email). Realistic records leak plenty of
sensitive values the dictionaries have never seen — a rare diagnosis, an
experimental drug, a foreign account number. But the surrounding **field name**
is itself a strong signal: if a value sits under ``diagnosis``, ``ssn``, or
``account_number``, it is sensitive regardless of what the value looks like.

This detector reads that signal. It scans the searchable text (which renders
structured content as ``key: value | key: value`` and preserves raw JSON
``"key": "value"`` forms) and flags the value carried by a known-sensitive key.
It closes the output-only blind spot on the *internal* channels the rest of the
tool is built around.
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity

# Sensitive field name (as a regex stem) -> (data_type, severity, advice).
# data_types map onto the AgentRisk taxonomy so levels resolve correctly.
_SENSITIVE_KEYS: dict[str, tuple[str, Severity, str]] = {
    r"ssn|social[_ ]?security(?:[_ ]?number)?": (
        "ssn", Severity.CRITICAL,
        "A government identifier is a direct re-identifier — never place it on internal channels.",
    ),
    r"national[_ ]?id(?:entifier)?|national[_ ]?id[_ ]?number|"
    r"num[ée]ro[_ ](?:de[_ ])?s[ée]curit[ée][_ ]sociale|n[°º]?[_ ]?s[ée]cu|\bnir\b|"
    r"\bdni\b|\bnie\b|\bnif\b|n[uú]mero[_ ]de[_ ]la[_ ]seguridad[_ ]social|\bnuss\b|"
    r"codice[_ ]fiscale|steuer[_ -]?id|steuerliche[_ ]identifikationsnummer|"
    r"sozialversicherungsnummer|personalausweisnummer|\bcpf\b|\bbsn\b|"
    r"burgerservicenummer|\bpesel\b|personnummer|aadhaar|\btfn\b|tax[_ ]file[_ ]number|"
    r"passport(?:[_ ]?(?:number|no))?|num[ée]ro[_ ]de[_ ]passeport|pasaporte|reisepass(?:nummer)?|"
    r"passaporte|passaporto": (
        "national_id", Severity.CRITICAL,
        "A government identifier is a direct re-identifier — never place it on internal channels.",
    ),
    r"sin|social[_ ]?insurance(?:[_ ]?number)?|nas|num[ée]ro[_ ]d[’'_ ]?assurance[_ ]sociale": (
        "sin", Severity.CRITICAL,
        "A government identifier is a direct re-identifier — never place it on internal channels.",
    ),
    r"health[_ ]?id|health[_ ]?identifier|mrn|medical[_ ]?record(?:[_ ]?number)?|nam|"
    r"nhs[_ ]?(?:number|no)|num[ée]ro[_ ]d[’'_ ]?assurance[_ ]maladie|carte[_ ]vitale|"
    r"tarjeta[_ ]sanitaria|krankenversichertennummer|n[uú]mero[_ ]do[_ ]sus|tessera[_ ]sanitaria": (
        "health_identifier", Severity.CRITICAL,
        "Health identifiers are regulated re-identifiers; mask them before any internal channel.",
    ),
    r"diagnos(?:is|es)|condition|chief[_ ]complaint|presenting[_ ]complaint|symptoms?|"
    r"motif[_ ]de[_ ]consultation|sympt[ôo]mes?|s[íi]ntomas?|symptome|sintomi|"
    r"diagnosti(?:c|que|co)|diagn[óo]stico|diagnose|diagnosi|"
    r"pathologie|maladie|enfermedad|patolog[íi]a|erkrankung|krankheit|doen[çc]a|malattia|"
    r"[ée]tat[_ ]de[_ ]sant[ée]|antecedentes[_ ]m[ée]dicos": (
        "health_condition", Severity.CRITICAL,
        "A diagnosis is special-category data; don't restate it on channels that don't need it.",
    ),
    r"medications?|prescriptions?|\bdrug\b|\brx\b|m[ée]dicaments?|traitement|ordonnance|"
    r"medicamentos?|medicaci[óo]n|tratamiento|receta|medikamente?|medikation|"
    r"f[áa]rmacos?|farmaci|terapia": (
        "medication", Severity.CRITICAL,
        "Medication reveals conditions; share only with authorised agents.",
    ),
    r"account[_ ]?(?:number|no|id)|iban|num[ée]ro[_ ]de[_ ]compte|n[uú]mero[_ ]de[_ ]cuenta|"
    r"cuenta[_ ]bancaria|kontonummer|n[uú]mero[_ ]da[_ ]conta|numero[_ ]di[_ ]conto|"
    r"conto[_ ]corrente|rib": (
        "account_number", Severity.CRITICAL,
        "Account numbers enable fraud; tokenise before internal channels.",
    ),
    r"credit[_ ]?card|card[_ ]?number|\bpan\b|num[ée]ro[_ ]de[_ ]carte|carte[_ ]bancaire|"
    r"n[uú]mero[_ ]de[_ ]tarjeta|tarjeta[_ ]de[_ ]cr[ée]dito|kartennummer|kreditkarte|"
    r"n[uú]mero[_ ]do[_ ]cart[ãa]o|cart[ãa]o[_ ]de[_ ]cr[ée]dito|numero[_ ](?:di[_ ])?carta|"
    r"carta[_ ]di[_ ]credito": (
        "credit_card", Severity.CRITICAL,
        "Card numbers are PCI-DSS regulated; never persist or forward them in the clear.",
    ),
    r"salary|compensation|base[_ ]?pay|salaire|r[ée]mun[ée]ration|salario|sueldo|"
    r"retribuci[óo]n|gehalt|lohn|sal[áa]rio|remunera[çc][ãa]o|stipendio|retribuzione": (
        "salary", Severity.HIGH,
        "Compensation is sensitive HR data; keep it in the restricted HR file.",
    ),
    r"income|revenus?|ingresos|einkommen|renda|rendimento|reddito": (
        "income", Severity.HIGH,
        "Income figures are sensitive financial data; minimise their spread.",
    ),
    r"credit[_ ]?score|cote[_ ]de[_ ]cr[ée]dit|score[_ ]de[_ ]cr[ée]dit|"
    r"puntuaci[óo]n[_ ]crediticia|schufa(?:[_ ]score)?|score[_ ]de[_ ]cr[ée]dito|"
    r"punteggio[_ ]di[_ ]credito": (
        "credit_score", Severity.HIGH,
        "Credit scores are sensitive financial data; keep them out of internal channels.",
    ),
    r"date[_ ]?of[_ ]?birth|\bdob\b|birth[_ ]?date|date[_ ]de[_ ]naissance|"
    r"fecha[_ ]de[_ ]nacimiento|fecha[_ ]nacimiento|fecha[_ ]nac|geburtsdatum|geburtstag|"
    r"data[_ ]de[_ ]nascimento|data[_ ]di[_ ]nascita|naissance|nacimiento": (
        "date_of_birth", Severity.HIGH,
        "Date of birth is a re-identifying quasi-identifier; remove it from internal channels.",
    ),
    r"(?:home[_ ]?|mailing[_ ]?)?address|adresse(?:[_ ]postale)?|domicile|"
    r"direcci[óo]n(?:[_ ]postal)?|domicilio|anschrift|wohnadresse|endere[çc]o|morada|"
    r"indirizzo|residenza": (
        "address", Severity.HIGH,
        "Home addresses are re-identifying; remove them from internal channels.",
    ),
    r"disciplinary(?:[_ ]?note|[_ ]?action)?": (
        "disciplinary_action", Severity.HIGH,
        "Disciplinary records are sensitive HR data; keep them restricted.",
    ),
    r"phone(?:[_ ]?number)?|telephone|mobile|t[ée]l[ée]phone|t[ée]l|portable|"
    r"tel[ée]fono|m[óo]vil|celular|telefon(?:nummer)?|handy(?:nummer)?|telefone|"
    r"telemovel|telem[óo]vel|cellulare|numero[_ ]di[_ ]telefono": (
        "phone_number", Severity.MEDIUM,
        "Phone numbers are contact PII; share only when necessary.",
    ),
    r"performance[_ ]?review": (
        "performance_review", Severity.MEDIUM,
        "Performance reviews are sensitive HR data; keep them restricted.",
    ),
    r"patient[_ ]?name|student[_ ]?name|customer[_ ]?name|full[_ ]?name|"
    r"nom|nom[_ ]complet|nom[_ ]du[_ ]patient|nom[_ ]et[_ ]pr[ée]nom|pr[ée]nom|"
    r"nombre(?:[_ ]completo)?|nombre[_ ]y[_ ]apellidos|apellidos?|"
    r"vollst[äa]ndiger[_ ]name|vorname|nachname|"
    r"nome(?:[_ ]completo)?|sobrenome|cognome|nominativo": (
        "person_name", Severity.LOW,
        "Names are PII; avoid restating them on channels that don't need them.",
    ),
}

# Values that are not real leaks — empty, placeholders, or already redacted.
_TRIVIAL_VALUE_RE = re.compile(
    # ``[REDACTED_SSN]`` is AgentLeak's own Sanitizer placeholder: a redacted
    # value is the fix, not a leak (the tail regex has already eaten the "]").
    r"^(?:none|null|n/?a|true|false|redacted|\[?redacted(?:_[a-z0-9_]+)?\]?|"
    r"unknown|\?+|-+|x{3,}|\*{2,}|"
    r"<[^>]*>|\{\{.*|\$\{.*)$",
    re.IGNORECASE,
)


# A snake_case prefix usually names whose address it is (billing_address), but
# these name a machine or a mailbox, not a home. Checked on the match, not in
# the pattern, so the exclusions cost nothing on text without an address key.
_NOT_A_HOME_PREFIX_RE = re.compile(
    r"(?i)(?:ip|mac|source|server|host|remote|local|bind|proxy|peer|socket|sock|email|mail|"
    r"base|return|target|dest|network|wallet|contract|memory|url|web|node|broadcast|gateway|"
    r"from|to|reply|sender|recipient|listen)_$"
)


# A value that is code, not data: an attribute path (``self.source_address``),
# a call (``IPv4Address(``) or a private identifier (``_complete_bpnumber``).
# Source files are scanned with the same detectors.
_CODE_VALUE_RE = re.compile(r"^(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+|[A-Za-z_][\w.]*\(.*|_\w+)$")


# The longest value we will believe a sensitive key carries. Past this, the
# capture has stopped describing a field and started swallowing narrative, so
# the match is dropped rather than stored: an unbounded span is not evidence,
# and it would enter scoring as its own "distinct secret".
_MAX_VALUE_LEN = 120

# Trailing characters that belong to the sentence, not to the value.
_VALUE_TAIL_RE = re.compile(r"[\s.;:!?)\]]+$")


def _compile(stem: str) -> re.Pattern[str]:
    """Compile the key-name pattern for one sensitive-field stem.

    The stem may end a longer snake_case key (``current_salary``,
    ``patient_diagnosis``, ``home_phone``): an underscore before it counts as
    a boundary, as it does for the secret key names.

    The value runs up to the next *field* delimiter — quote, pipe, comma,
    semicolon, closing brace, newline — or up to the end of the *sentence*.

    That last clause is what keeps prose honest. ``final_output``, ``log`` and
    ``inter_agent_message`` carry sentences, not JSON, and a sentence supplies
    none of the structural delimiters; without a sentence boundary the capture
    ran from the key to the end of the line, so ``medication: insulin. Please
    forward to the specialist.`` was stored as a 42-character "medication".
    A period only ends the value when whitespace or the end of the text follows
    it, so decimals (``3.5``), hostnames and addresses inside a value survive.
    """
    return re.compile(
        rf"""["']?(?:(?<=_)|\b)(?:{stem})\b["']?\s*[:=]\s*["']?((?:[^"'|,;}}\n.]|\.(?!\s|$))+)""",
        re.IGNORECASE,
    )


_COMPILED: list[tuple[re.Pattern[str], str, Severity, str]] = [
    (_compile(stem), data_type, severity, advice)
    for stem, (data_type, severity, advice) in _SENSITIVE_KEYS.items()
]


# One pass that finds which stems are present at all, written as a key (stem
# then ":" or "="). Only those stems' full patterns run afterwards, so the
# multilingual lexicon costs one scan per event instead of one per stem. A
# full-pattern match always implies a prefilter match, so results are exact.
_PREFILTER = re.compile(
    r"(?:(?<=_)|\b)(?:" + "|".join(f"(?P<k{i}>{stem})" for i, stem in enumerate(_SENSITIVE_KEYS))
    + r")\b[\"']?\s*[:=]",
    re.IGNORECASE,
)


class SensitiveKeyDetector(Detector):
    name = "keyname_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []
        present = {m.lastgroup for m in _PREFILTER.finditer(text)}
        if not present:
            return matches
        for index, (pattern, data_type, severity, advice) in enumerate(_COMPILED):
            if f"k{index}" not in present:
                continue
            for m in pattern.finditer(text):
                value = m.group(1).strip().strip("\"'")
                value = _VALUE_TAIL_RE.sub("", value)
                if len(value) < 2 or _TRIVIAL_VALUE_RE.match(value) or _CODE_VALUE_RE.match(value):
                    continue
                if data_type == "address" and _NOT_A_HOME_PREFIX_RE.search(
                    text[max(0, m.start() - 12):m.start()]
                ):
                    continue
                if len(value) > _MAX_VALUE_LEN:
                    # Not a field value any more. Reporting it would put an
                    # unreadable span in the evidence and a phantom secret in
                    # the vault; the value detectors still cover this text.
                    continue
                matches.append(self._match(
                    data_type=data_type, severity=severity,
                    confidence=0.6, matched_value=value, recommendation=advice,
                ))
        return matches
