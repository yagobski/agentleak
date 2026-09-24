# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Credentials must leave ``redact`` whole.

Every case here was found by piping text through the published 0.14.1 wheel.
Each one returned output that *looked* sanitised — a placeholder appeared — and
still carried the secret: the body of a PEM key under a redacted header, the
username of a connection string whose password had been mistaken for an email,
a plain ``password: hunter2`` left untouched because assignments were
detect-only.
"""

from __future__ import annotations

import pytest

from agentleak.defenses import sanitize_text

PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun\n"
    "VTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxK\n"
    "-----END RSA PRIVATE KEY-----"
)


def test_pem_body_is_removed_not_just_its_header():
    out = sanitize_text(f"key:\n{PEM}\nend")
    assert "MIIEow" not in out
    assert "VTLw7on" not in out
    assert out.startswith("key:\n[REDACTED_PRIVATE_KEY]")
    assert out.endswith("\nend")


def test_truncated_pem_still_loses_its_body():
    text = PEM.rsplit("\n", 1)[0]  # no END line: a key cut off by a log limit
    out = sanitize_text(text)
    assert "MIIEow" not in out and "VTLw7on" not in out


@pytest.mark.parametrize(
    "text, gone",
    [
        ("postgres://admin:supersecret@db.internal:5432/prod", ["admin", "supersecret"]),
        ("mongodb+srv://user:pass123@cluster0.mongodb.net/db", ["user:", "pass123"]),
        ("git clone https://bot:tok3nvalue@github.com/org/repo.git", ["bot:", "tok3nvalue"]),
    ],
)
def test_url_with_credentials_is_redacted_whole(text, gone):
    out = sanitize_text(text)
    for fragment in gone:
        assert fragment not in out, out
    assert "REDACTED_EMAIL" not in out, "a password is not an email address"
    assert "REDACTED_CONNECTION_STRING" in out


@pytest.mark.parametrize(
    "text, secret",
    [
        ("password: hunter2", "hunter2"),
        ("DB_PASSWORD=hunter2", "hunter2"),
        ("export OPENAI_API_KEY=abcd1234efgh5678", "abcd1234efgh5678"),
        ('aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
         "wJalrXUtnFEMI"),
    ],
)
def test_assigned_secret_value_is_redacted_and_the_code_kept(text, secret):
    out = sanitize_text(text)
    assert secret not in out, out
    # The key name survives: redacting the value does not delete the code.
    assert text.split("=")[0].split(":")[0].strip() in out


def test_references_are_still_left_alone():
    for line in (
        'api_key = os.environ.get("OPENAI_API_KEY")',
        "token = settings.API_KEY",
        "page_token = response.next_page_token",
        "api_key=API_KEY, temperature=0",
    ):
        assert sanitize_text(line) == line, line


def test_github_fine_grained_pat():
    pat = "github_pat_11ABCDEFG0123456789_" + "a" * 59
    assert "github_pat_" not in sanitize_text(f"token {pat} here")


def test_spaced_iban():
    out = sanitize_text("IBAN FR76 3000 6000 0112 3456 7890 189 please wire")
    assert out == "IBAN [REDACTED_IBAN] please wire"


@pytest.mark.parametrize(
    "text",
    ["Né le 12/03/1985 à Montréal", "née le 1985-03-12", "date de naissance : 12/03/1985"],
)
def test_french_date_of_birth(text):
    assert "1985" not in sanitize_text(text)


def test_pii_inside_ordinary_text_still_wins_over_key_name_spans():
    # The inner-span rule exists for imprecise key-name spans; it must keep
    # working there, so the sentence around an SSN survives.
    out = sanitize_text("ssn: 412-55-9087 and more text")
    assert out == "ssn: [REDACTED_SSN] and more text"


def test_cli_accepts_mask_as_the_documented_alias():
    from typer.testing import CliRunner

    from agentleak.cli import app

    result = CliRunner().invoke(app, ["redact", "--style", "mask"], input="SSN 412-55-9087\n")
    assert result.exit_code == 0, result.output
    assert "XXXXXXX9087" in result.output


def test_extra_patterns_accepts_a_dict_as_documented():
    from agentleak.defenses import Sanitizer

    san = Sanitizer(extra_patterns={"PROJ_ID": r"PROJ-\d{6}"})
    assert san.sanitize("see PROJ-123456") == "see [REDACTED_PROJ_ID]"
