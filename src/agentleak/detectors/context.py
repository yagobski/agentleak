# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Context-window rules: a value that is ambiguous alone, next to the word
that says what it is.

``555-0152`` is a phone number, a part number or a ticket. ``1994-10-17`` is a
birth date or a release date. ``128000`` is a salary or a row count. Alone,
none of them is personal data a deterministic rule can claim, and the fast
tier does not claim them. Agents rarely write them alone, though: they write
"you can reach her at 555-0152", "his date of birth is 1994-10-17", "her
salary is $128,000". The word before the value carries the type.

Each rule here has three parts:

* a **value** pattern: the shape the data type can take (a seven-digit local
  number, a calendar date, a run of six to twenty digits, an amount);
* a **cue** lexicon in English, French and Spanish ("call", "joindre",
  "llámale"; "born", "née", "nació"…);
* a **gap** the text between the end of the cue and the start of the value
  must match in full. For most rules that is a short list of glue words
  ("is", "at", "on", "number", "est", "de", "es", "el"…), which is what lets
  "account number is 12345678" through and keeps "account sync job 99812"
  out. The gap never crosses a sentence break and is at most ``window``
  characters long.

A value with no cue is not reported, and a cue with no plausible value is not
reported either. Findings carry ``rule`` (``ctx_phone_local``, ``ctx_dob``…)
and a lower confidence than a shape-validated match, because the type comes
from the context, not from the value.

Health conditions work the other way round, since the value is a phrase, not
a shape: a strong cue ("diagnosed with", "diagnostiqué", "le
diagnosticaron") takes the noun phrase after it; a weak cue ("suffers from",
"souffre de", "padece") takes it only when the phrase holds a clinical word or
a clinical suffix (-itis, -osis, -algia…). "The server suffers from memory
pressure" names no clinical term and is not reported.

Every pattern is linear: value and cue scans are single passes, and the gap
check runs on at most ``window`` characters per candidate. The timing guard is
in ``tests/test_detector_timing.py``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..core.detector import RawMatch, Severity
from ._text import MONTHS, trie_pattern

__all__ = ["ContextRule", "RULES", "HEALTH_RULES", "scan", "matches_for"]


@dataclass(frozen=True)
class ContextRule:
    """One context-window rule. See the module docstring."""

    rule: str
    data_type: str
    severity: Severity
    confidence: float
    value: re.Pattern[str]
    cue: frozenset[str]  # lower-case cue words; see _cue_hits
    gap: re.Pattern[str]
    window: int
    recommendation: str
    # Extra check on (value, cue) once cue and gap agree; None accepts.
    validate: Callable[[str, str], bool] | None = None
    # Words that, just before the cue, make the number something else's id:
    # "the incident on account 7781234" names an incident, not an account.
    veto_before: re.Pattern[str] | None = None


def _words(terms: list[str]) -> frozenset[str]:
    """A cue lexicon: whole words (or fixed phrases), matched case-insensitively.

    All lexicons are matched in one pass by :func:`_cue_hits`, not one regex
    per rule: the pipeline runs the hosting detectors one after another on
    the same text, and seven case-insensitive scans cost 14% of throughput.
    """
    return frozenset(t.lower() for t in terms)


def _glue(terms: list[str]) -> re.Pattern[str]:
    """A gap made only of punctuation and the given glue words (at most six)."""
    sep = r"[\s:=#,()'’\"-]*"
    body = trie_pattern(sorted({t.lower() for t in terms}))
    return re.compile(r"(?i)" + sep + r"(?:(?:" + body + r")(?!\w)\.?" + sep + r"){0,6}")


# A sentence or line break between cue and value cuts the link. "no." and
# "n°" are abbreviations of "number", not full stops.
_BREAK_RE = re.compile(r"(?i)(?<!\bno)(?<!\bnr)[.!?;](?:\s|$)|\n")

# Glue shared by the rules whose cue is a noun or a verb right before the value.
_GLUE_COMMON = [
    # English
    "is", "was", "are", "be", "the", "a", "his", "her", "their", "my", "your", "our",
    "its", "of", "on", "at", "to", "now", "currently", "number", "no", "nr", "num",
    "#", "him", "me", "us", "them", "you", "can", "directly",
    # French
    "est", "était", "le", "la", "l", "les", "de", "du", "d", "au", "à", "son", "sa",
    "ses", "leur", "lui", "numéro", "numero", "n°", "maintenant",
    # Spanish
    "es", "era", "el", "los", "las", "del", "al", "en", "su", "sus", "le", "número",
    "nº", "ahora",
]

# --- phone number, national part without area or country code -----------------
# "555-0152", "555.0152"; a Spanish national number without +34
# ("612 34 56 78", "612 345 678"). With a country code or a NANP area code the
# shape rules in pii.py report them without a cue.
_PHONE_VALUE = re.compile(
    r"(?<![\w+./-])(?:\d{3}[-.]\d{4}|[6-9]\d{2}(?:[ .]\d{2}){3}|[6-9]\d{2}(?:[ .]\d{3}){2})"
    r"(?![\w/-]|[.,]\d)"
)
_PHONE_CUE = _words([
    "call", "calls", "called", "calling", "phone", "phoned", "telephone", "tel", "cell",
    "cellphone", "mobile", "text", "sms", "reach", "ring", "dial", "whatsapp", "fax",
    "contact", "number",
    "appelle", "appelez", "appeler", "appelez-le", "appelez-la", "rappelle", "rappelez",
    "rappelez-le", "rappelez-la", "joindre", "téléphone", "telephone", "tél", "portable",
    "numéro", "numero", "texto",
    "llama", "llame", "llamar", "llámale", "llamale", "llámala", "llamala", "llámalo",
    "llamalo", "llámame", "llamame", "teléfono", "telefono", "móvil", "movil", "número",
    "localizar", "localizarla", "localizarlo", "contactar", "contactarlo", "contactarla",
    "mensaje",
])
_PHONE_GAP = _glue(_GLUE_COMMON + ["best", "work", "home", "line", "personal", "private"])

# --- date of birth -----------------------------------------------------------
_DATE_VALUE = re.compile(
    r"(?i)(?<![\w/.-])(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-](?:\d{4}|\d{2})"
    r"|\d{1,2}(?:er|º|°)?\.?\s+(?:de\s+)?(?:" + MONTHS + r")\.?\s+(?:de\s+)?\d{4}"
    r"|(?:" + MONTHS + r")\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
    # Not a timestamp: no time of day glued after the date.
    r"(?![\w/-]|[.:]\d|\s\d{1,2}:\d{2})"
)
_DOB_CUE = _words([
    "born", "birth", "birthday", "birthdate", "dob", "d.o.b",
    "né", "née", "nés", "nées", "naissance", "anniversaire",
    "nació", "nacio", "nacido", "nacida", "nacidos", "nacidas", "nacimiento",
    "cumpleaños", "cumpleanos",
])
# A date of birth is often a few words away from its cue ("née à Lyon le",
# "nació en Sevilla el"): up to five words, none holding a digit.
# A word takes its whole run of word characters (the look-ahead): otherwise a
# run of letters could be split into up to five "words" in every possible way,
# and a gap that fails at its last character ("born aaaa…a@ 1994-10-17") was
# retried for each split, tens of milliseconds per cue. Splitting a run never
# helped a match (it only adds words), so what matches is unchanged.
_DOB_GAP = re.compile(r"[\s,:=#'’\"]*(?:[^\W\d_][\w'’.-]*(?![\w'’.-])[\s,:=#'’\"]*){0,5}")


def _plausible_date(value: str, _cue: str) -> bool:
    nums = [int(n) for n in re.findall(r"\d+", value)]
    year = next((n for n in nums if n >= 1000), None)
    if year is not None and not 1900 <= year <= 2030:
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return 1 <= nums[1] <= 12 and 1 <= nums[2] <= 31
    if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", value):
        a, b = nums[0], nums[1]
        return 1 <= a <= 31 and 1 <= b <= 31 and (a <= 12 or b <= 12)
    return True


# --- account number ----------------------------------------------------------
_ACCOUNT_VALUE = re.compile(r"(?<![\w.,/-])\d(?:[ -]?\d){5,19}(?![\w/-]|[.,]\d)")
_ACCOUNT_CUE = _words([
    # Not "routing": a routing number names a bank, not a customer.
    "account", "accounts", "acct", "a/c", "checking", "chequing", "savings",
    "compte", "cuenta",
])
# An id noun right before "account" governs the number that follows it.
_ACCOUNT_VETO_BEFORE = re.compile(
    r"(?i)(?<!\w)(?:ticket|incident|case|job|batch|order|migration|task|issue|"
    r"incidencia|incidente|caso|pedido|lote|tarea|tâche|tache|commande|dossier|lot)"
    r"s?(?!\w)[\s\w'’-]{0,16}$"
)
_ACCOUNT_GAP = _glue(_GLUE_COMMON + [
    "ending", "ends", "in", "file", "id", "it", "into", "from", "bancaire", "bancaria",
    "corriente", "courant", "épargne", "ahorro",
])

# --- salary ------------------------------------------------------------------
_CURRENCY = r"(?:€|\$|£|(?:eur(?:os?)?|usd|cad|chf|gbp|dollars?|livres?)(?!\w))"
_PERIOD = (
    r"(?:\s?(?:/|per|a|an|par|al|por|each|every)\s?(?:year|yr|annum|month|mo|an|année|"
    r"mois|año|ano|mes)(?!\w)|\s(?:annually|yearly|monthly|annuel(?:le)?s?|"
    r"mensuel(?:le)?s?|anuales?|mensuales?|brut(?:e|s|es)?|net(?:te|s|tes)?|brutos?|"
    r"netos?|gross|net)(?!\w))"
)
_SALARY_VALUE = re.compile(
    r"(?i)(?<![\w.,])(?:[$€£]\s?)?(?:\d{1,3}(?:[ ,.  ]\d{3})+|\d{4,7})(?:[.,]\d{2})?"
    r"(?:\s?k(?!\w))?(?:\s?" + _CURRENCY + r")?" + _PERIOD + r"?(?![\w]|[.,]\d)"
)
_SALARY_NOUN_CUE = _words([
    "salary", "salaries", "wage", "wages", "compensation", "base pay", "annual pay",
    "take-home pay", "gross pay", "net pay",
    "salaire", "rémunération", "remuneration", "traitement annuel",
    "sueldo", "salario", "remuneración", "remuneracion", "retribución", "retribucion",
])
_SALARY_VERB_CUE = _words([
    "earn", "earns", "earned", "earning", "makes", "made", "making",
    "gagne", "gagnait", "touche", "touchait",
    "cobra", "cobraba", "gana", "ganaba", "percibe",
])
_SALARY_GAP = _glue(_GLUE_COMMON + [
    "about", "around", "roughly", "approximately", "approx", "nearly", "over",
    "environ", "unos", "alrededor", "aproximadamente",
])


def _paid_amount(value: str, _cue: str) -> bool:
    """After a verb ("earns", "gagne", "cobra") the amount must say it is
    money paid over time: a currency or a period. "earns 4000 points" is not."""
    return bool(re.search(r"[$€£]|" + _CURRENCY + "|" + _PERIOD, value, re.IGNORECASE))


_RECOMMEND = {
    "phone_number": "Avoid sending full phone numbers to tools and logs.",
    "date_of_birth": "Generalize dates of birth (e.g. to year) instead of passing exact values.",
    "account_number": "Never forward full account numbers; use last-4 or a token.",
    "salary": "Salary data should only reach explicitly authorized agents.",
    "health_condition": "Avoid restating specific diagnoses in channels that don't need them.",
}

RULES: tuple[ContextRule, ...] = (
    ContextRule("ctx_phone_local", "phone_number", Severity.MEDIUM, 0.55, _PHONE_VALUE,
                _PHONE_CUE, _PHONE_GAP, 40, _RECOMMEND["phone_number"]),
    ContextRule("ctx_dob", "date_of_birth", Severity.MEDIUM, 0.6, _DATE_VALUE,
                _DOB_CUE, _DOB_GAP, 48, _RECOMMEND["date_of_birth"], _plausible_date),
    ContextRule("ctx_account_number", "account_number", Severity.HIGH, 0.6, _ACCOUNT_VALUE,
                _ACCOUNT_CUE, _ACCOUNT_GAP, 40, _RECOMMEND["account_number"],
                veto_before=_ACCOUNT_VETO_BEFORE),
    ContextRule("ctx_salary", "salary", Severity.HIGH, 0.6, _SALARY_VALUE,
                _SALARY_NOUN_CUE, _SALARY_GAP, 40, _RECOMMEND["salary"]),
    ContextRule("ctx_salary_verb", "salary", Severity.HIGH, 0.55, _SALARY_VALUE,
                _SALARY_VERB_CUE, _SALARY_GAP, 32, _RECOMMEND["salary"], _paid_amount),
)

# --- health condition --------------------------------------------------------
# Cues that name a diagnosis outright, and cues that only suggest one.
_HEALTH_STRONG_CUE = _words([
    "diagnosed with", "diagnosed as", "diagnosis of", "tested positive for",
    "diagnostic de", "diagnostic d", "diagnostiqué avec", "diagnostiquée avec",
    "diagnostiqué d", "diagnostiquée d", "diagnostiqué de", "diagnostiquée de",
    "diagnosticado de", "diagnosticada de", "diagnosticado con", "diagnosticada con",
    "le diagnosticaron", "la diagnosticaron", "les diagnosticaron", "diagnóstico de",
    "diagnostico de",
])
_HEALTH_WEAK_CUE = _words([
    "suffers from", "suffered from", "suffering from", "treated for", "treatment for",
    "dealing with", "living with", "lives with", "history of", "presented with",
    "presents with", "complains of", "complained of", "recovering from",
    "souffre de", "souffre d", "souffrait de", "atteint de", "atteinte de", "atteint d",
    "atteinte d", "suivi pour", "suivie pour", "traité pour", "traitée pour",
    "antécédents de", "antécédents d",
    "padece", "padece de", "padecía", "sufre de", "sufría de", "tratamiento por",
    "tratamiento para", "tratamiento de", "tratado por", "tratada por", "tratado de",
    "tratada de", "antecedentes de",
])
# Clinical words and suffixes: what turns "suffers from X" into a diagnosis.
_CLINICAL_RE = re.compile(
    r"(?i)(?<!\w)(?:"
    + trie_pattern(sorted({
        "pain", "pains", "ache", "aches", "headache", "headaches", "migraine", "migraines",
        "nausea", "fever", "cough", "dizziness", "insomnia", "addiction", "disorder",
        "disease", "syndrome", "infection", "injury", "fracture", "mutation", "tumor",
        "tumour", "lesion", "ulcer", "seizures", "allergy", "asthma", "cancer",
        "douleur", "douleurs", "maladie", "trouble", "troubles",
        "insomnie", "asthme",
        "dolor", "dolores", "migraña", "migrana", "enfermedad", "síndrome", "sindrome",
        "trastorno", "infección", "infeccion", "insomnio", "adicción", "adiccion",
        "mutación", "mutacion", "asma",
    }))
    + r")(?!\w)"
    r"|\w{3,}(?:itis|osis|emia|aemia|pathy|algia|plegia|trophy|ectomy|pathie|algie|patía|patia)(?!\w)"
)
_HEALTH_STOP = frozenset({
    "for", "since", "last", "at", "during", "in", "on", "and", "but", "with", "after",
    "before", "this", "that", "which", "who", "when", "while", "ago", "today", "yesterday",
    "depuis", "pendant", "au", "aux", "et", "mais", "avec", "cette", "ce", "qui", "quand",
    "hier", "desde", "durante", "hace", "la", "el", "los", "las", "y", "pero", "con",
    "que", "cuando", "ayer", "hoy",
})
_DETERMINERS = frozenset({"a", "an", "the", "un", "une", "le", "la", "les", "el", "una", "los", "las"})
_HEALTH_PHRASE_RE = re.compile(r"[^\W\d_][\w'’-]*|\d+")

HEALTH_RULES = ("ctx_health_diagnosis", "ctx_health_symptom")

_ALL_CUES = frozenset().union(
    *(rule.cue for rule in RULES), _HEALTH_STRONG_CUE, _HEALTH_WEAK_CUE
)
_ANY_CUE_RE = re.compile(r"(?i)(?<!\w)(?:" + trie_pattern(sorted(_ALL_CUES)) + r")(?!\w)")
# The hosting detectors run one after another on the same event text, so the
# cue pass of the last text is kept. A tuple is swapped in whole, so a reader
# on another thread sees an old entry or a new one, never half of each.
_last_hits: tuple[str, list[tuple[int, int, str, str]]] = ("", [])


def _cue_hits(text: str) -> list[tuple[int, int, str, str]]:
    """Every cue word in *text*, as ``(start, end, lower-case term, word)``."""
    global _last_hits
    cached_text, cached = _last_hits
    if cached_text is text or cached_text == text:
        return cached
    hits = [(m.start(), m.end(), m.group(0).lower(), m.group(0)) for m in _ANY_CUE_RE.finditer(text)]
    _last_hits = (text, hits)
    return hits


def _phrase_after(text: str, start: int) -> tuple[str, int, int] | None:
    """The noun phrase after a cue: up to six words, ended by punctuation or by
    a temporal or linking word ("for", "since", "depuis", "desde"…)."""
    chunk = text[start:start + 80]
    cut = re.search(r"[.,;:!?()\n\"]", chunk)
    if cut:
        chunk = chunk[:cut.start()]
    words = list(_HEALTH_PHRASE_RE.finditer(chunk))[:6]
    kept: list[re.Match[str]] = []
    for i, w in enumerate(words):
        if i and w.group(0).lower() in _HEALTH_STOP:
            break
        kept.append(w)
    if not kept:
        return None
    s, e = start + kept[0].start(), start + kept[-1].end()
    return text[s:e], s, e


def _health(text: str) -> Iterator[tuple[str, str, tuple[int, int], float]]:
    hits = _cue_hits(text)
    for rule, cues, confidence in (
        ("ctx_health_diagnosis", _HEALTH_STRONG_CUE, 0.6),
        ("ctx_health_symptom", _HEALTH_WEAK_CUE, 0.5),
    ):
        for _start, end, term, _word in hits:
            if term not in cues:
                continue
            found = _phrase_after(text, end)
            if not found:
                continue
            phrase, s, e = found
            first = phrase.split()[0].lower()
            clinical = bool(_CLINICAL_RE.search(phrase))
            # A strong cue names a diagnosis, usually as a bare noun ("diagnosed
            # with osteoarthritis"); "diagnosed with a misconfigured proxy" has
            # a determiner and no clinical word, and is not taken.
            if rule == "ctx_health_diagnosis":
                if not clinical and (first in _DETERMINERS or phrase.isdigit()):
                    continue
            elif not clinical:
                continue
            yield rule, phrase, (s, e), confidence


# Longest value any rule takes; bounds the search after a cue.
_MAX_VALUE = 64


def scan(text: str, data_types: frozenset[str] | set[str]) -> Iterator[tuple[ContextRule, str, tuple[int, int]]]:
    """Yield ``(rule, value, span)`` for every context-window match of the
    given data types (health conditions excluded: see :func:`matches_for`).

    Cue first: values are only looked for in the ``window`` after a cue, so a
    text with no cue costs one scan, and a costly value pattern (dates with
    month names) runs on a few dozen characters, not on the whole event."""
    hits = _cue_hits(text)
    if not hits:
        return
    for rule in RULES:
        if rule.data_type not in data_types:
            continue
        taken: set[tuple[int, int]] = set()
        for start, end, term, word in hits:
            if term not in rule.cue:
                continue
            if rule.veto_before and rule.veto_before.search(text, max(0, start - 24), start):
                continue
            limit = min(len(text), end + rule.window + _MAX_VALUE)
            for m in rule.value.finditer(text, end, limit):
                if m.start() - end > rule.window:
                    break
                if m.end() == limit < len(text):
                    # Cut by the search bound: read the value on the full text.
                    full = rule.value.match(text, m.start())
                    if full is None:
                        continue
                    m = full
                gap = text[end:m.start()]
                if _BREAK_RE.search(gap) or not rule.gap.fullmatch(gap):
                    continue
                if rule.validate is not None and not rule.validate(m.group(0), word):
                    continue
                if m.span() not in taken:
                    taken.add(m.span())
                    yield rule, m.group(0).strip(), m.span()
                break


def matches_for(
    detector: str, text: str, data_types: frozenset[str], existing: list[RawMatch],
) -> list[RawMatch]:
    """Context matches for one hosting detector, minus values it already
    reported under the same type (a shape rule outranks a context rule)."""
    taken = [(m.data_type, m.matched_value) for m in existing]

    def known(data_type: str, value: str) -> bool:
        return any(t == data_type and (value in v or v in value) for t, v in taken)

    out: list[RawMatch] = []
    for rule, value, _span in scan(text, data_types):
        if known(rule.data_type, value):
            continue
        taken.append((rule.data_type, value))
        out.append(RawMatch(
            data_type=rule.data_type, severity=rule.severity, confidence=rule.confidence,
            matched_value=value, recommendation=rule.recommendation, detector=detector,
            rule=rule.rule,
        ))
    if "health_condition" in data_types:
        for rule_name, value, _span, confidence in _health(text):
            if known("health_condition", value):
                continue
            taken.append(("health_condition", value))
            out.append(RawMatch(
                data_type="health_condition", severity=Severity.MEDIUM, confidence=confidence,
                matched_value=value, recommendation=_RECOMMEND["health_condition"],
                detector=detector, rule=rule_name,
            ))
    return out
