# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Check-digit validators for identifiers, implemented from public specifications.

A pattern says a string has the *shape* of an identifier. A check digit says it
*is* one, or at least that it was built by the issuer's algorithm: a random run
of digits passes a mod-97 key one time in 97, a Luhn check one time in ten.
Detectors use these functions so that format-only matches do not fire.

Every function takes the identifier with or without separators and returns a
bool; none raises on malformed input. Each one names the specification it
follows. No code or data was copied from another implementation.
"""

from __future__ import annotations

import re
import zlib

_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z]")


def compact(value: str) -> str:
    """The identifier with spaces, dots, dashes and slashes removed."""
    return _NON_ALNUM_RE.sub("", value)


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


# ---------------------------------------------------------------------------
# Generic algorithms
# ---------------------------------------------------------------------------


def luhn(digits: str) -> bool:
    """Luhn mod-10 (ISO/IEC 7812-1, Annex B)."""
    if not digits or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff(digits: str) -> bool:
    """Verhoeff dihedral-group check (Verhoeff 1969), used by Aadhaar."""
    if not digits or not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def iso7064_mod97(value: str) -> bool:
    """ISO 7064 MOD 97-10 over an alphanumeric string (letters A=10 … Z=35)."""
    try:
        return int("".join(str(int(ch, 36)) for ch in value)) % 97 == 1
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Banking and cards
# ---------------------------------------------------------------------------

# IBAN length per country, from the SWIFT IBAN Registry (ISO 13616). Lengths
# are facts of the standard, listed here by hand.
IBAN_LENGTHS: dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16, "BG": 22,
    "BH": 22, "BI": 27, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28, "CZ": 24,
    "DE": 22, "DJ": 27, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24, "FI": 18,
    "FK": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27,
    "GT": 28, "HN": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IS": 26,
    "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20,
    "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MN": 20,
    "MR": 27, "MT": 31, "MU": 30, "NI": 28, "NL": 18, "NO": 15, "OM": 23, "PK": 24,
    "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22, "RU": 33, "SA": 24,
    "SC": 31, "SD": 18, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "SO": 23, "ST": 25,
    "SV": 28, "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
    "YE": 30,
}


# Countries whose BBAN opens with a four-letter bank code (registry BBAN format
# "4!a…"); a digit there is not an IBAN of that country.
_IBAN_LETTER_BANK = frozenset({"BG", "GB", "GI", "IE", "MT", "NL", "RO", "VG"})


def iban(value: str) -> bool:
    """IBAN: registered country, that country's exact length, ISO 7064 mod-97,
    and a letter bank code where the registry requires one."""
    raw = compact(value).upper()
    expected = IBAN_LENGTHS.get(raw[:2])
    if expected is None or len(raw) != expected or not raw[2:4].isdigit():
        return False
    if raw[:2] in _IBAN_LETTER_BANK and not raw[4:8].isalpha():
        return False
    # Italy and San Marino open the BBAN with the CIN control letter.
    if raw[:2] in ("IT", "SM") and not raw[4].isalpha():
        return False
    return iso7064_mod97(raw[4:] + raw[:4])


def card_network(digits: str) -> str | None:
    """The card network whose published IIN range and length fit, else None.

    Ranges are the issuers' public BIN ranges (Visa 4; Mastercard 51-55 and
    2221-2720; Amex 34/37; Discover 6011, 644-649, 65; JCB 3528-3589; Diners
    300-305, 36, 38-39; UnionPay 62; Maestro 50, 56-69).
    """
    n = len(digits)
    if not digits.isdigit() or not 12 <= n <= 19:
        return None
    p2, p3, p4, p6 = int(digits[:2]), int(digits[:3]), int(digits[:4]), int(digits[:6])
    if digits[0] == "4" and n in (13, 16, 19):
        return "visa"
    if (51 <= p2 <= 55 or 2221 <= p4 <= 2720) and n == 16:
        return "mastercard"
    if p2 in (34, 37) and n == 15:
        return "amex"
    if (p4 == 6011 or 644 <= p3 <= 649 or p2 == 65 or 622126 <= p6 <= 622925) and 16 <= n <= 19:
        return "discover"
    if 3528 <= p4 <= 3589 and 16 <= n <= 19:
        return "jcb"
    if (300 <= p3 <= 305 or p2 in (36, 38, 39)) and 14 <= n <= 19:
        return "diners"
    if p2 == 62 and 16 <= n <= 19:
        return "unionpay"
    if (p2 == 50 or 56 <= p2 <= 69) and 12 <= n <= 19:
        return "maestro"
    return None


def payment_card(value: str) -> bool:
    """A card number: a known network's IIN and length, and a valid Luhn digit."""
    digits = _digits(value)
    return card_network(digits) is not None and luhn(digits)


# ---------------------------------------------------------------------------
# National identifiers
# ---------------------------------------------------------------------------


def us_ssn(value: str) -> bool:
    """US SSN issuance rules (SSA): area not 000 or 666, group not 00, serial
    not 0000. Area 900-999 is the IRS ITIN range, a taxpayer identifier of the
    same sensitivity, so it is accepted."""
    d = _digits(value)
    if len(d) != 9:
        return False
    return d[:3] not in ("000", "666") and d[3:5] != "00" and d[5:] != "0000"


def ca_sin(value: str) -> bool:
    """Canadian SIN: nine digits, Luhn (ESDC). 8 is never a first digit."""
    d = _digits(value)
    return len(d) == 9 and d[0] != "8" and luhn(d)


def fr_nir(value: str) -> bool:
    """French NIR (numéro de sécurité sociale): 13 characters + a 2-digit key,
    key = 97 - (number mod 97). Corsican departments 2A/2B count as 19/18.
    Sex digit 1-4 or 7-8; month 01-12, 20-42 or 50-99 (INSEE)."""
    raw = compact(value).upper()
    if len(raw) != 15 or raw[0] not in "123478":
        return False
    month = raw[3:5]
    if not month.isdigit() or not (
        1 <= int(month) <= 12 or 20 <= int(month) <= 42 or 50 <= int(month) <= 99
    ):
        return False
    body = raw[:13]
    if body[5:7] == "2A":
        body = body[:5] + "19" + body[7:]
    elif body[5:7] == "2B":
        body = body[:5] + "18" + body[7:]
    if not body.isdigit() or not raw[13:].isdigit():
        return False
    return 97 - int(body) % 97 == int(raw[13:])


_IT_ODD = {
    **{str(i): v for i, v in enumerate((1, 0, 5, 7, 9, 13, 15, 17, 19, 21))},
    **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
        1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16,
        10, 22, 25, 24, 23,
    ), strict=True)),
}
_IT_OMOCODIA = "LMNPQRSTUV"  # letters that replace digits 0-9 in homonym codes
_IT_MONTHS = "ABCDEHLMPRST"


def it_codice_fiscale(value: str) -> bool:
    """Italian codice fiscale (DM 23/12/1976): 16 characters, final control
    letter from the odd/even position tables, month letter, day 01-31 or
    41-71, digits possibly replaced by omocodia letters."""
    raw = compact(value).upper()
    if len(raw) != 16 or not raw[:6].isalpha() or raw[8] not in _IT_MONTHS:
        return False
    day = "".join(str(_IT_OMOCODIA.index(c)) if c in _IT_OMOCODIA else c for c in raw[9:11])
    if not day.isdigit() or not (1 <= int(day) <= 31 or 41 <= int(day) <= 71):
        return False
    for pos in (6, 7, 9, 10, 12, 13, 14):
        if not (raw[pos].isdigit() or raw[pos] in _IT_OMOCODIA):
            return False
    if not raw[11].isalpha() or not raw[15].isalpha():
        return False
    total = 0
    for i, ch in enumerate(raw[:15]):
        if i % 2 == 0:  # 1st, 3rd, … position (odd in 1-based counting)
            total += _IT_ODD[ch]
        else:
            total += int(ch) if ch.isdigit() else ord(ch) - ord("A")
    return chr(ord("A") + total % 26) == raw[15]


def de_steuer_id(value: str) -> bool:
    """German Steuerliche Identifikationsnummer (§139b AO): 11 digits, no
    leading 0; in the first ten, exactly one digit repeats (twice or three
    times) and the rest appear once; ISO 7064 MOD 11,10 check digit."""
    d = _digits(value)
    if len(d) != 11 or d[0] == "0":
        return False
    counts = [d[:10].count(c) for c in set(d[:10])]
    repeated = [n for n in counts if n > 1]
    if len(repeated) != 1 or repeated[0] not in (2, 3):
        return False
    product = 10
    for ch in d[:10]:
        s = (int(ch) + product) % 10 or 10
        product = (s * 2) % 11
    check = 11 - product
    return (0 if check == 10 else check) == int(d[10])


def uk_nhs(value: str) -> bool:
    """UK NHS number (NHS Data Dictionary): ten digits, mod-11 with weights
    10..2; a remainder giving 10 is never issued."""
    d = _digits(value)
    if len(d) != 10:
        return False
    check = 11 - sum(int(c) * w for c, w in zip(d[:9], range(10, 1, -1), strict=True)) % 11
    if check == 10:
        return False
    return (0 if check == 11 else check) == int(d[9])


def nl_bsn(value: str) -> bool:
    """Dutch BSN: nine digits, the "11-proef" (weights 9..2, last digit -1)."""
    d = _digits(value)
    if len(d) != 9 or d == "0" * 9:
        return False
    total = sum(int(c) * w for c, w in zip(d[:8], range(9, 1, -1), strict=True)) - int(d[8])
    return total % 11 == 0


_BE_2000_CUTOFF = 30  # two-digit years below this may be 20YY births


def be_national_number(value: str) -> bool:
    """Belgian national register number: YYMMDD + 3-digit counter + 2-digit
    key, key = 97 - (first nine mod 97); for births from 2000 the nine digits
    are prefixed with 2."""
    d = _digits(value)
    if len(d) != 11:
        return False
    base, key = int(d[:9]), int(d[9:])
    if 97 - base % 97 == key:
        return True
    # The "2" prefix marks a birth in 2000 or later. A fixed cutoff, not
    # today's date: detection must give the same answer on every day it runs.
    return int(d[:2]) < _BE_2000_CUTOFF and 97 - int("2" + d[:9]) % 97 == key


def pl_pesel(value: str) -> bool:
    """Polish PESEL: 11 digits, weights 1-3-7-9, month carries the century."""
    d = _digits(value)
    if len(d) != 11:
        return False
    month = int(d[2:4]) % 20
    if not 1 <= month <= 12:
        return False
    total = sum(int(c) * w for c, w in zip(d[:10], (1, 3, 7, 9, 1, 3, 7, 9, 1, 3), strict=True))
    return (10 - total % 10) % 10 == int(d[10])


def se_personnummer(value: str) -> bool:
    """Swedish personnummer / samordningsnummer: (YY)YYMMDD-NNNC, Luhn over the
    ten digits YYMMDDNNNC; day 61-91 marks a coordination number."""
    d = _digits(value)
    if len(d) == 12:
        d = d[2:]
    if len(d) != 10:
        return False
    month, day = int(d[2:4]), int(d[4:6])
    if not 1 <= month <= 12 or not (1 <= day <= 31 or 61 <= day <= 91):
        return False
    return luhn(d)


def _mod11_digit(digits: str, weights: tuple[int, ...]) -> int:
    rest = sum(int(c) * w for c, w in zip(digits, weights, strict=True)) % 11
    return 0 if rest < 2 else 11 - rest


def br_cpf(value: str) -> bool:
    """Brazilian CPF (Receita Federal): 11 digits, two mod-11 check digits."""
    d = _digits(value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    first = _mod11_digit(d[:9], tuple(range(10, 1, -1)))
    second = _mod11_digit(d[:10], tuple(range(11, 1, -1)))
    return d[9:] == f"{first}{second}"


def br_cnpj(value: str) -> bool:
    """Brazilian CNPJ (company registry): 14 digits, two mod-11 check digits."""
    d = _digits(value)
    if len(d) != 14 or d == d[0] * 14:
        return False
    first = _mod11_digit(d[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _mod11_digit(d[:13], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return d[12:] == f"{first}{second}"


def in_aadhaar(value: str) -> bool:
    """Indian Aadhaar (UIDAI): 12 digits, first digit 2-9, Verhoeff check."""
    d = _digits(value)
    return len(d) == 12 and d[0] not in "01" and verhoeff(d)


def au_tfn(value: str) -> bool:
    """Australian tax file number (ATO): weighted sum divisible by 11; nine
    digits (weights 1,4,3,7,5,8,6,9,10) or the older eight (10,7,8,4,6,3,5,1)."""
    d = _digits(value)
    if len(d) == 9:
        weights: tuple[int, ...] = (1, 4, 3, 7, 5, 8, 6, 9, 10)
    elif len(d) == 8:
        weights = (10, 7, 8, 4, 6, 3, 5, 1)
    else:
        return False
    return sum(int(c) * w for c, w in zip(d, weights, strict=True)) % 11 == 0


# ---------------------------------------------------------------------------
# Token checksums
# ---------------------------------------------------------------------------

_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def base62(n: int, width: int) -> str:
    out = ""
    while n:
        n, r = divmod(n, 62)
        out = _BASE62[r] + out
    return out.rjust(width, "0")


def crc32_token(token: str) -> bool:
    """GitHub-style token checksum (also used by npm): the last six characters
    are the base62 CRC32 of the 30 random characters before them, as GitHub
    documented when it introduced the ``gh*_`` formats in 2021."""
    _prefix, _sep, body = token.rpartition("_")
    if len(body) != 36:
        return False
    return base62(zlib.crc32(body[:30].encode()), 6) == body[30:]


__all__ = [
    "IBAN_LENGTHS", "au_tfn", "base62", "be_national_number", "br_cnpj", "br_cpf",
    "ca_sin", "card_network", "compact", "crc32_token", "de_steuer_id", "fr_nir",
    "iban", "in_aadhaar", "iso7064_mod97", "it_codice_fiscale", "luhn", "nl_bsn",
    "payment_card", "pl_pesel", "se_personnummer", "uk_nhs",
    "us_ssn", "verhoeff",
]
