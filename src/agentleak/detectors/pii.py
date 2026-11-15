# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""General PII detector: emails, phones, SSN/SIN, credit cards, IPs, DOB,
client identifiers, UK NINO, Spanish DNI/NIE and social security number,
check-digit-validated national identifiers (see :mod:`.national_ids`), and
keyword-anchored probable names.

Patterns favor precision over recall and attach a per-pattern confidence so
the scoring engine can weigh noisy matches (phones, names) less than crisp
ones (emails, validated cards).
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity
from . import checksums
from ._text import MONTHS as _MONTHS
from ._text import inside_blob
from .context import matches_for as context_matches
from .names import full_names
from .national_ids import scan as scan_national_ids

# Starts only where a run of local-part characters starts. Without the
# look-behind a 50 KB run with no "@" was rescanned from every position
# (quadratic: 1.7 s); the matches are the same, because the leftmost start of
# a run always reaches the same "@" an inner start would.
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9_.+-])[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")
# US SSN (xxx-xx-xxxx) and Canadian SIN (xxx-xxx-xxx) are distinct shapes.
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SIN_RE = re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b")

# A Spanish mobile national part is also 9 digits in 3-3-3 groups
# ("612 345 678"), which collides with the SIN shape above. With its country
# code (+34 / 0034) it is a Spanish number: nine digits, 6-7 for mobiles and
# 8-9 for landlines, in any grouping. Reported as a phone; the SIN loop skips
# anything inside one of these spans (issue #4).
ES_PHONE_RE = re.compile(r"(?<![\w+])(?:\(?\+34\)?|0034)[\s.\-]*[6-9](?:[\s.\-]?\d){8}(?!\d)")
# A bare run of nine digits is not a SIN on its own — it is also an order
# number, a timestamp, or a part code. It becomes one when the text says so,
# which is how people actually write it ("SIN 123456789"), so the unseparated
# form is matched only next to the word that names it. The capture keeps the
# digits alone so the redactor removes the number, not the label.
# "sin" is also the Spanish for "without" ("sin 123456789 dudas"), so the
# short labels count in capitals, or in any case when a separator makes them
# a label ("sin: 123456789", "sin=123456789"), never as a bare word.
SIN_LABELLED_RE = re.compile(
    r"\b(?:SIN|NAS|(?i:sin|nas)(?=[\"']?\s*[:=#])|(?i:social[ _]?insurance(?:[ _]?number)?))"
    r"\b[\"']?[\s:=#]*[\"']?(\d{9}|\d{3}[- ]\d{3}[- ]\d{3})\b"
)
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)
# A phone-shaped number right after the word that names it as something else
# ("order 555-123-4567", "SKU 202-611-1400") is a reference, not a phone.
_NOT_A_PHONE_PREFIX_RE = re.compile(
    r"(?i)\b(?:order|invoice|ticket|case|ref|reference|sku|part|po|serial|tracking|isbn|"
    r"batch|lot|build|commande|facture|pedido|factura|bestellung|rechnung|ordine|fattura)"
    r"(?:\s*(?:no\.?|number|num|nr\.?|n[°º]|#|id))?\s*[:#]?\s*$"
)
# International numbers written with their country code: "+33 6 12 34 56 78",
# "+44 20 7946 0958", "0049 30 901820". The calling codes are the ITU-T E.164
# assignments (North America +1 and Spain +34 have their own patterns above).
# The national part must have 6 to 12 digits, as E.164 allows at most 15 in all.
_CALLING_CODES = (
    "20|27|30|31|32|33|36|39|40|41|43|44|45|46|47|48|49|51|52|53|54|55|56|57|58|"
    "60|61|62|63|64|65|66|81|82|84|86|90|91|92|93|94|95|98|"
    "212|213|216|218|220|221|225|233|234|237|243|254|255|256|260|263|"
    "351|352|353|354|355|356|357|358|359|370|371|372|373|374|375|376|377|378|380|381|382|"
    "385|386|387|389|420|421|423|852|853|855|880|886|961|962|963|964|965|966|967|968|"
    "970|971|972|973|974|975|976|977"
)
INTL_PHONE_RE = re.compile(
    r"(?<![\w+])(?:\+|00)(?:" + _CALLING_CODES + r")"
    r"(?:[\s.\-]?\(0\))?(?:[\s.\-]?\d){6,12}(?!\d|[.,]\d)"
)
# French national format: ten digits from 01 to 09, written in pairs.
FR_PHONE_RE = re.compile(r"(?<![\w+.-])0[1-9](?:[ .-]\d{2}){4}(?![\s\w.-]?\d)")
# Any number next to the word "phone" in one of the supported languages.
PHONE_LABELLED_RE = re.compile(
    r"(?<!\w)(?i:tel|t[ée]l[ée]?phone|phone|mobile|cell(?:phone)?|portable|"
    r"tel[ée]fono|m[óo]vil|celular|telefon|handy|telefone|cellulare|whatsapp)(?:\s*(?:no\.?|number|n[°º]))?"
    r"(?!\w)[\s:=#.]{0,4}(\+?\(?\d[\d\s().\-]{5,18}\d)(?![\d-])"
)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
# IPv6 in expanded/partly-compressed form. Requires at least four groups so we
# never mistake a clock time (12:34:56) for an address; precision over recall.
IPV6_RE = re.compile(
    r"\b(?:[A-Fa-f0-9]{1,4}:){3,7}[A-Fa-f0-9]{1,4}\b"
    r"|\b(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}\b"
)
# "+35236450.6" is a signed decimal number, not "+352" and a phone number.
_SIGNED_DECIMAL_RE = re.compile(r"[+-]?\d+[.,]\d+")
_CLOCK_LIKE_RE = re.compile(r"\d{1,2}(?::\d{1,2})+")
# IPv4 that is actually a software version ("version 1.2.3.4") is not a client
# IP leak — used to suppress that false positive.
_VERSION_PREFIX_RE = re.compile(
    r"\b(?:version|ver|build|release|rev|firmware|fw|protocol|schema|api|package|pkg|"
    r"(?:upgraded|updated|downgraded|bumped|pinned)(?:\s+\w+){0,3}\s+to)\b"
    r"(?:[\s:v.]*|\s+[\w.-]+\s+v?)$",
    re.IGNORECASE,
)
# 12 to 19 digits, optionally grouped. Not when the run continues with another
# digit group ("9400 1000 0000 0000 0000 00" is a parcel number), and validated
# by Luhn *and* a card network's published IIN range and length.
CREDIT_CARD_RE = re.compile(r"(?<![\d-])(?<!\d )\d(?:[ -]?\d){11,18}(?![ -]?\d)")
# Dates only flagged as DOB when anchored to a birth keyword (avoids matching
# trace timestamps and arbitrary dates).
DOB_RE = re.compile(
    r"(?i)\b(?:dob|d\.o\.b\.|date of birth|born(?: on)?|birth ?date"
    r"|n[ée]e? le|date de naissance"
    r"|fecha de nacimiento|fecha nac\.?|f\. ?nac\.?|nacid[oa] el|naci[óo] el"
    r"|geboren am|geburtsdatum|geb\."
    r"|data de nascimento|nascid[oa] em|data di nascita|nat[oa] il)(?!\w)[:\s]*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{1,2}(?:er|º|°)?\.?\s+(?:de\s+)?(?:" + _MONTHS + r")\.?\s+(?:de\s+)?\d{4}"
    r"|(?:" + _MONTHS + r")\.?\s+\d{1,2},?\s+\d{4})(?!\w)"
)
CLIENT_ID_RE = re.compile(r"\b(?:ACC|ACCT|CUST|CLIENT|USER|MEMBER)[-_]?\d{3,}\b", re.IGNORECASE)
# UK National Insurance Number (AB123456C). Uses the official valid-prefix rules
# (excludes administrative prefixes like BG/GB/NK/ZZ and the letters D/F/I/Q/U/V)
# so the shape is distinctive enough to match without a keyword.
NINO_RE = re.compile(
    r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)"
    r"[ABCEGHJ-PRSTW-Z][ABCEGHJ-NPRSTW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"
)
# Spanish DNI (12345678Z) and NIE (X1234567L). The final letter is a checksum
# of the number, so a match is validated, not just pattern-matched: a random
# 8-digits-and-a-letter run passes one time in 23. Uppercase letter only, and
# not glued to a longer token ("ORD-12345678Z", "123456789Z"), for precision.
DNI_RE = re.compile(r"(?<![\w.-])(\d{8}|\d{2}\.\d{3}\.\d{3})[- ]?([A-Z])(?![\w-])")
NIE_RE = re.compile(r"(?<![\w.-])([XYZ])[- ]?(\d{7})[- ]?([A-Z])(?![\w-])")
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
# Spanish social security number (NUSS / número de afiliación): two digits of
# province, eight of number, two of control ("28/12345678/40"). The control is
# a checksum (modulo 97), so a match is validated. Grouped with one consistent
# separator it matches on its own; as a bare run of twelve digits it is also
# an order or a reference, so it needs the label next to it ("NUSS
# 281234567840").
NUSS_RE = re.compile(r"(?<![\w/.-])(\d{2})([ /-])(\d{8})\2(\d{2})(?![\w/-])")
NUSS_LABELLED_RE = re.compile(
    r"\b(?i:nuss|naf|n[uú]mero de afiliaci[oó]n|seguridad social)\b"
    r"[^\d\n]{0,25}?(?<!\d)(\d{2})(\d{8})(\d{2})(?!\d)"
)
# Street address: number + street words + a street-type suffix.
# The suffixes are the common USPS street-type words, minus the ones that are
# mostly surnames (Green, Mills, Ford, Brooks…); the first version knew fifteen,
# and a street ending in "Pines" or "Crescent" went unreported. An
# optional unit and ", City, ST 12345" tail are taken too, so a redaction
# removes the whole address rather than leaving the city and ZIP behind.
_STREET_SUFFIXES = (
    "Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl|"
    "Circle|Cir|Crescent|Cres|Terrace|Ter|Parkway|Pkwy|Highway|Hwy|Square|Sq|Squares|"
    "Trail|Trl|Park|Pike|Plaza|Plz|Point|Pt|Ridge|Rdg|Row|Run|Spur|Station|Sta|"
    "Pines|Manor|Manors|Mews|Loop|Locks|Lock|Landing|Knoll|Knolls|Junction|Jct|"
    "Heights|Hts|Harbor|Hbr|Grove|Gv|Gardens|Gdns|Garden|Freeway|Fwy|Estates|"
    "Crossing|Xing|Crossroad|Crossroads|Cove|Cv|Creek|Crk|Bridge|Brg|Bypass|Byp|"
    "Branch|Br|Bend|Alley|Aly|Villages|Village|Vlg|Views|View|Vw|Valley|Vly|"
    "Turnpike|Tpke|Summit|Springs|Spring|Shores|Shore|Rapids|Port|Prairie|Pass|"
    "Oval|Orchard|Mill|Meadows|Meadow|Lodge|Lights|Island|Isle|Hollow|"
    "Hill|Glen|Gateway|Forest|Fork|Forks|Field|Falls|Extension|Ext|Expressway|"
    "Expy|Divide|Dale|Dam|Courts|Corners|Corner|Common|Commons|Cliffs|Causeway|"
    "Canyon|Camp|Burgs|Burg|Brook|Bluffs|Bluff|Beach|Arcade|Walk|Walks|Wall|"
    "Ways|Well|Unions|Union|Underpass|Tunnel|Track|Throughway|Streets|Stream|"
    "Stravenue|Squares|Skyway|Shoals|Radial|Ramp|Ranch|Rest|Plains|Pines|Parks|"
    "Neck|Motorway|Mount|Mountain|Mountains|Mission|Lakes|Lake|Keys|Key|Inlet|"
    "Harbors|Haven|Fort|Ferry|Crest|Club|Center|Centers|Cape|Causeway"
)
ADDRESS_RE = re.compile(
    # Not after ":" or "." — "10:00 AM. Alex Green" is a time and a person.
    r"(?<![:.\d])\b\d{1,5}\s+(?:[A-Z][A-Za-z.]+\s){1,3}"
    r"(?i:" + _STREET_SUFFIXES + r")\b\.?"
    r"(?:,?\s+(?:Suite|Ste|Apt|Apartment|Unit|#)\.?\s*[A-Za-z0-9-]+)?"
    r"(?:,\s*[A-Z][A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?",
)
# French / Québec civic address: number + street-type word *before* the name
# (e.g. "1240 Rue Saint-Denis", "85 Boulevard René-Lévesque"). Grounded in
# Law 25 — Québec addresses don't use the English "<name> Street" suffix shape.
ADDRESS_FR_RE = re.compile(
    r"\b\d{1,5}(?:[-\s]\d{1,4})?\s+"
    r"(?:Rue|Avenue|Av|Boulevard|Boul|Bd|Chemin|Ch|C[ôo]te|Place|All[ée]e|"
    r"Impasse|Mont[ée]e|Rang|Croissant|Promenade|Terrasse|Carr[ée])\.?\s+"
    r"[A-ZÀ-Ý][\wÀ-ÿ'’.-]+(?:[ -][A-ZÀ-Ý][\wÀ-ÿ'’.-]+){0,3}",
    re.IGNORECASE,
)
# Spanish address: street-type word, then the name, then the number
# ("Calle Mayor 12", "Avenida de Anaga, 5", "C/ Gran Vía, nº 28"). The type
# word may be lowercase, as it usually is in prose ("vive en la calle Mayor
# 12"); the name must be capitalized. An optional floor/door ("3º B") and a
# postal code with its town ("38001 Santa Cruz de Tenerife") are taken too, so
# a redaction removes the whole address. The number has at most three digits
# and is not followed by a unit, so "Camino de Santiago 2023" or "Paseo
# Marítimo 5 minutos" stay out.
_ES_CAP = r"[A-ZÁÉÍÓÚÑ][\w'’-]*"
_ES_LINK = r"(?:(?:de|del|la|las|los|el|y)\s+)*"
ADDRESS_ES_RE = re.compile(
    r"\b(?i:calle|c/|avenida|avda\.?|av\.|plaza|pza\.?|paseo|camino|carretera"
    r"|ctra\.?|ronda|traves[íi]a|glorieta|rambla|urbanizaci[óo]n|urb\.)"
    r"(?:(?<=[/.])\s*|\s+)" + _ES_LINK + _ES_CAP + r"(?:\s+" + _ES_LINK + _ES_CAP + r"){0,4}"
    r",?\s*(?:n[º°o]\.?\s*)?\d{1,3}[A-Za-z]?\b"
    r"(?!\s*(?:km|kms|m|metros|min|minutos|h|horas|veces|personas|euros|€|%)(?!\w))"
    r"(?:,?\s*\d{1,2}[º°ªo]\s*[A-Za-z]?\b)?"
    r"(?:,?\s*(?:0[1-9]|[1-4]\d|5[0-2])\d{3}\b"
    r"(?:\s+" + _ES_CAP + r"(?:\s+" + _ES_LINK + _ES_CAP + r"){0,4})?)?"
)
# A US street address with its city, state and ZIP tail ("262 Kaiser Plain,
# Lloydside, AL 82804"): the street-type word may be one ADDRESS_RE leaves out
# (Plain, Trace, Ford, Wells…) because the tail says what the line is. The
# state must be a USPS code, territories and military included.
_US_STATES = (
    "AL|AK|AS|AZ|AR|CA|CO|CT|DE|DC|FM|FL|GA|GU|HI|ID|IL|IN|IA|KS|KY|LA|ME|MH|MD|MA|MI|"
    "MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|MP|OH|OK|OR|PW|PA|PR|RI|SC|SD|TN|TX|UT|VT|VI|"
    "VA|WA|WV|WI|WY|AA|AE|AP"
)
_CAP_WORD = r"[A-Z][A-Za-z'.-]*"
ADDRESS_US_ZIP_RE = re.compile(
    r"(?<![\w.:])\d{1,6}\s+" + _CAP_WORD + r"(?:\s+" + _CAP_WORD + r"){0,3}"
    r"(?:,?\s+(?:Suite|Ste|Apt|Apartment|Unit|#)\.?\s*[A-Za-z0-9-]+)?"
    r",\s*" + _CAP_WORD + r"(?:\s+" + _CAP_WORD + r"){0,3},\s*(?:" + _US_STATES + r")"
    r"\s+\d{5}(?:-\d{4})?(?![\w-])"
)
# US military mail: "PSC 9148, Box 4175, APO AE 64580", "Unit 4674 Box 2801,
# DPO AA 99206", "USS Carlson, FPO AP 58705". APO/FPO/DPO with AA/AE/AP and a
# ZIP is unambiguous.
ADDRESS_US_MILITARY_RE = re.compile(
    r"\b(?:(?:PSC|CMR|Unit)\s+\d{1,5},?\s+Box\s+\d{1,5}|USN?S\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)"
    r",?\s+(?:APO|FPO|DPO)\s+A[AEP]\s+\d{5}(?![\w-])"
)
# Canadian postal code (A1A 1A1) — distinctive enough to match without a keyword.
POSTAL_RE = re.compile(r"\b[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d\b")
# Probable full name following a person keyword, e.g. "patient Jean Tremblay".
# The keyword is case-insensitive (scoped flag) but the captured name must be
# properly capitalized — a global (?i) would let it swallow trailing lowercase
# words like "Jean Tremblay has".
NAME_RE = re.compile(
    r"\b(?i:patient|client|customer|employee|name|mr|mrs|ms|dr|prof)\b"
    r"[\"'\s:_]+([A-ZÀ-Ý][a-zà-ÿ]+(?:[ -][A-ZÀ-Ý][a-zà-ÿ]+){1,2})"
)


_CONTEXT_TYPES = frozenset({"phone_number", "date_of_birth"})


def _luhn_ok(digits: str) -> bool:
    """Kept for callers outside this module: Luhn over 13 to 19 digits."""
    nums = "".join(d for d in digits if d.isdigit())
    return 13 <= len(nums) <= 19 and checksums.luhn(nums)


def _inside(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(a <= span[0] and span[1] <= b for a, b in spans)


def _dni_letter_ok(number: str, letter: str) -> bool:
    """The DNI/NIE control letter is the number modulo 23 in a fixed table."""
    return _DNI_LETTERS[int(number) % 23] == letter


def _nuss_ok(province: str, number: str, control: str) -> bool:
    """The NUSS control is the province and number modulo 97; a number below
    ten million counts with the province times ten million, not prefixed."""
    n = int(number)
    base = n + int(province) * 10_000_000 if n < 10_000_000 else int(province + number)
    return base % 97 == int(control)


class PIIDetector(Detector):
    name = "pii_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []

        # No "@", no email; skipping the scan avoids EMAIL_RE's quadratic
        # rescans of long local-part-like runs (base64, hex, dotted ids).
        for m in (EMAIL_RE.finditer(text) if "@" in text else ()):
            matches.append(self._match(
                data_type="email", severity=Severity.MEDIUM, confidence=0.95,
                matched_value=m.group(0),
                recommendation="Mask email addresses before internal channels and logs.",
            ))

        # Check-digit-validated identifiers first: their spans are claimed, so
        # a NIR is not also reported as a card number or a phone.
        id_spans: list[tuple[int, int]] = []
        for id_rule, value, span in scan_national_ids(text):
            id_spans.append(span)
            matches.append(self._match(
                data_type=id_rule.data_type, severity=id_rule.severity,
                confidence=id_rule.confidence, matched_value=value,
                recommendation=id_rule.recommendation, rule=id_rule.rule,
            ))

        for m in SSN_RE.finditer(text):
            # Never issued: area 000 or 666, group 00, serial 0000 (SSA rules).
            if not checksums.us_ssn(m.group(0)) or _inside(m.span(), id_spans):
                continue
            matches.append(self._match(
                data_type="ssn", severity=Severity.HIGH, confidence=0.85,
                matched_value=m.group(0), rule="us_ssn",
                recommendation="Never transmit full social security numbers; tokenize them.",
            ))

        es_phones: list[tuple[int, int]] = []
        for m in ES_PHONE_RE.finditer(text):
            es_phones.append(m.span())
            matches.append(self._match(
                data_type="phone_number", severity=Severity.MEDIUM, confidence=0.65,
                matched_value=m.group(0).strip(),
                recommendation="Avoid sending full phone numbers to tools and logs.",
            ))

        labelled_sins: list[tuple[int, int]] = []
        for m in SIN_LABELLED_RE.finditer(text):
            labelled_sins.append(m.span(1))
            matches.append(self._match(
                data_type="sin", severity=Severity.HIGH, confidence=0.8,
                matched_value=m.group(1), rule="ca_sin_labelled",
                recommendation="Never transmit full social insurance numbers; tokenize them.",
            ))

        for m in SIN_RE.finditer(text):
            # Inside a +34 number: a phone (reported above), not a SIN.
            if _inside(m.span(), es_phones) or _inside(m.span(), labelled_sins):
                continue
            # Unlabelled and space-separated, the 3-3-3 shape is also how a
            # Spanish phone is printed ("612 345 678"), so it must pass Luhn as
            # every issued SIN does; nine random digits pass one time in ten.
            # The hyphenated form ("123-456-789") is the SIN's own print format
            # and is what synthetic test data uses, so its shape still counts,
            # at lower confidence when the check digit fails.
            valid = checksums.ca_sin(m.group(0))
            if not valid and "-" not in m.group(0):
                continue
            matches.append(self._match(
                data_type="sin", severity=Severity.HIGH, confidence=0.9 if valid else 0.7,
                matched_value=m.group(0), rule="ca_sin" if valid else "ca_sin_shape",
                recommendation="Never transmit full social insurance numbers; tokenize them.",
            ))

        phone_spans: list[tuple[int, int]] = list(es_phones)
        for m in PHONE_RE.finditer(text):
            if _inside(m.span(), id_spans) or _NOT_A_PHONE_PREFIX_RE.search(
                text[max(0, m.start() - 40):m.start()]
            ):
                continue
            phone_spans.append(m.span())
            matches.append(self._match(
                data_type="phone_number", severity=Severity.MEDIUM, confidence=0.65,
                matched_value=m.group(0).strip(), rule="phone_nanp",
                recommendation="Avoid sending full phone numbers to tools and logs.",
            ))

        for pattern, rule, group in (
            (INTL_PHONE_RE, "phone_international", 0),
            (FR_PHONE_RE, "phone_fr", 0),
            (PHONE_LABELLED_RE, "phone_labelled", 1),
        ):
            for m in pattern.finditer(text):
                span = m.span(group)
                value = m.group(group).strip()
                digits = sum(ch.isdigit() for ch in value)
                if (
                    not 7 <= digits <= 15
                    or _SIGNED_DECIMAL_RE.fullmatch(value)
                    or _inside(span, phone_spans)
                    or _inside(span, id_spans)
                    or (group == 0 and _NOT_A_PHONE_PREFIX_RE.search(
                        text[max(0, span[0] - 40):span[0]]))
                ):
                    continue
                phone_spans.append(span)
                matches.append(self._match(
                    data_type="phone_number", severity=Severity.MEDIUM, confidence=0.65,
                    matched_value=value, rule=rule,
                    recommendation="Avoid sending full phone numbers to tools and logs.",
                ))

        for m in CREDIT_CARD_RE.finditer(text):
            raw = m.group(0)
            if _inside(m.span(), id_spans) or not checksums.payment_card(raw):
                continue
            matches.append(self._match(
                data_type="credit_card", severity=Severity.HIGH, confidence=0.95,
                matched_value=raw.strip(), rule="payment_card",
                recommendation="Card numbers must never appear in agent channels; use a vault token.",
            ))

        for m in IP_RE.finditer(text):
            # Skip version strings like "version 1.2.3.4" — not a client IP.
            if _VERSION_PREFIX_RE.search(text[max(0, m.start() - 32):m.start()]):
                continue
            matches.append(self._match(
                data_type="ip_address", severity=Severity.LOW, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Strip client IP addresses from internal traces where not required.",
            ))

        for m in IPV6_RE.finditer(text):
            # "2022-02-22:11:30:00" holds "22:11:30:00": a clock time, not an
            # address. Found in the InjecAgent pack, 0.18.0 reported it.
            if _CLOCK_LIKE_RE.fullmatch(m.group(0)):
                continue
            matches.append(self._match(
                data_type="ip_address", severity=Severity.LOW, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Strip client IP addresses from internal traces where not required.",
            ))

        for m in DOB_RE.finditer(text):
            matches.append(self._match(
                data_type="date_of_birth", severity=Severity.MEDIUM, confidence=0.75,
                matched_value=m.group(1),
                recommendation="Generalize dates of birth (e.g. to year) instead of passing exact values.",
            ))

        for m in CLIENT_ID_RE.finditer(text):
            matches.append(self._match(
                data_type="client_identifier", severity=Severity.MEDIUM, confidence=0.7,
                matched_value=m.group(0),
                recommendation="Use opaque, scoped identifiers instead of raw client/account ids.",
            ))

        for m in NINO_RE.finditer(text):
            matches.append(self._match(
                data_type="national_insurance_number", severity=Severity.HIGH, confidence=0.8,
                matched_value=m.group(0),
                recommendation="Never transmit full National Insurance numbers; tokenize them.",
            ))

        for m in DNI_RE.finditer(text):
            if _dni_letter_ok(m.group(1).replace(".", ""), m.group(2)):
                matches.append(self._match(
                    data_type="spanish_national_id", severity=Severity.HIGH, confidence=0.9,
                    matched_value=m.group(0),
                    recommendation="Never transmit full DNI/NIE numbers; tokenize them.",
                ))

        for m in NIE_RE.finditer(text):
            # The NIE prefix stands for a leading digit: X=0, Y=1, Z=2.
            number = str("XYZ".index(m.group(1))) + m.group(2)
            if _dni_letter_ok(number, m.group(3)):
                matches.append(self._match(
                    data_type="spanish_national_id", severity=Severity.HIGH, confidence=0.9,
                    matched_value=m.group(0),
                    recommendation="Never transmit full DNI/NIE numbers; tokenize them.",
                ))

        for m in NUSS_RE.finditer(text):
            if _nuss_ok(m.group(1), m.group(3), m.group(4)):
                matches.append(self._match(
                    data_type="spanish_social_security_number", severity=Severity.HIGH,
                    confidence=0.9, matched_value=m.group(0),
                    recommendation="Never transmit full social security numbers; tokenize them.",
                ))

        for m in NUSS_LABELLED_RE.finditer(text):
            if _nuss_ok(m.group(1), m.group(2), m.group(3)):
                matches.append(self._match(
                    data_type="spanish_social_security_number", severity=Severity.HIGH,
                    confidence=0.9, matched_value=m.group(1) + m.group(2) + m.group(3),
                    recommendation="Never transmit full social security numbers; tokenize them.",
                ))

        for name in full_names(text):
            matches.append(self._match(
                data_type="person_name", severity=Severity.MEDIUM, confidence=0.5,
                matched_value=name,
                recommendation="Minimize full names passed between agents; prefer references.",
            ))

        for m in NAME_RE.finditer(text):
            matches.append(self._match(
                data_type="person_name", severity=Severity.MEDIUM, confidence=0.55,
                matched_value=m.group(1),
                recommendation="Minimize full names passed between agents; prefer references.",
            ))

        for m in ADDRESS_RE.finditer(text):
            matches.append(self._match(
                data_type="address", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(),
                recommendation="Home addresses are re-identifying; remove them from internal channels.",
            ))

        for m in ADDRESS_FR_RE.finditer(text):
            matches.append(self._match(
                data_type="address", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(),
                recommendation="Home addresses are re-identifying; remove them from internal channels.",
            ))

        for m in ADDRESS_ES_RE.finditer(text):
            if inside_blob(text, m.start(), m.end()):
                continue
            matches.append(self._match(
                data_type="address", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(),
                recommendation="Home addresses are re-identifying; remove them from internal channels.",
            ))

        address_values = [m.matched_value for m in matches if m.data_type == "address"]
        for pattern, rule in (
            (ADDRESS_US_ZIP_RE, "address_us_zip"), (ADDRESS_US_MILITARY_RE, "address_us_military"),
        ):
            for m in pattern.finditer(text):
                value = m.group(0).strip()
                if any(value in v for v in address_values):
                    continue
                address_values.append(value)
                matches.append(self._match(
                    data_type="address", severity=Severity.HIGH, confidence=0.75,
                    matched_value=value, rule=rule,
                    recommendation="Home addresses are re-identifying; remove them from internal channels.",
                ))

        for m in POSTAL_RE.finditer(text):
            if inside_blob(text, m.start(), m.end()):
                continue
            matches.append(self._match(
                data_type="address", severity=Severity.MEDIUM, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Postal codes narrow identity; avoid passing them where not required.",
            ))

        # Values that are ambiguous alone, taken when the word before them
        # names them ("reach her at 555-0152", "born on 1994-10-17").
        matches.extend(context_matches(self.name, text, _CONTEXT_TYPES, matches))
        return matches
