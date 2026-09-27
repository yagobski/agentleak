# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Names and addresses in a sentence, with no key in front of them.

Prose recall was 0 of 96 for names and 1 of 52 for addresses: the only person
pattern needed a keyword ("patient ..."), and the street list knew fifteen
suffixes. Each exclusion below exists because the pack sweep produced it.
"""

from __future__ import annotations

import pytest

from agentleak.detectors.names import full_names
from agentleak.detectors.pii import ADDRESS_RE, PIIDetector


@pytest.mark.parametrize("text, name", [
    ("summary generated for Jean Tremblay today", "Jean Tremblay"),
    ("forward it to Maria Rodriguez.", "Maria Rodriguez"),
    ("Marc-André Tremblay signed", "Marc-André Tremblay"),
    ("see Émilie Roy's file", "Émilie Roy"),
    ("Michael Warren The end", "Michael Warren"),
])
def test_full_name_in_prose(text, name):
    assert full_names(text) == [name]


@pytest.mark.parametrize("text", [
    "Grace Period applies",           # given name that is an ordinary word: not listed
    "Jordan River flows south",       # a place
    "Victoria Street is closed",      # a street
    "63196 Amanda Manors Suite 825",  # a street named after a person
    "Andrea Trail, Amber Crescent",
    "the Adam Optimizer converged",
    "Maria\nThompson",                # never across a line break
])
def test_not_a_person(text):
    assert full_names(text) == []


@pytest.mark.parametrize("text, address", [
    ("ship to 21009 Adams Locks Suite 885, New Jonathanshire, DC 45977 today",
     "21009 Adams Locks Suite 885, New Jonathanshire, DC 45977"),
    ("lives at 758 Ritter Pines", "758 Ritter Pines"),
    ("12 Main Street", "12 Main Street"),
])
def test_address_in_prose(text, address):
    assert ADDRESS_RE.findall(text) == [address]


def test_a_time_before_a_person_named_green_is_not_an_address():
    types = {m.data_type for m in PIIDetector().detect("at 10:00 AM. Alex Green called")}
    assert "address" not in types


def test_the_gazetteer_does_not_find_itself():
    # The source of the name list must not read as a list of people when
    # `agentleak scan` reads this repository.
    from agentleak.detectors import names
    assert full_names(names._GIVEN_NAMES) == []
