# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Spanish dates of birth and street addresses (issue #4).

The English and French forms were already covered ("date of birth: …",
"12 Main Street", "1240 Rue Saint-Denis"); the Spanish ones came out with no
finding. A Spanish address puts the street type first and the number after
the name ("Calle Mayor 12"), so it needs its own shape.
"""
from agentleak.detectors.pii import PIIDetector


def _values(text, data_type):
    return [m.matched_value for m in PIIDetector().detect(text) if m.data_type == data_type]


def test_spanish_birth_labels():
    for text in [
        "fecha de nacimiento: 03/04/1975",
        "Fecha de nacimiento 1975-04-03",
        "F. nac.: 03-04-1975",
        "fecha nac. 3/4/75",
        "nacido el 03/04/1975 en Santa Cruz",
        "Nació el 03/04/1975.",
    ]:
        assert _values(text, "date_of_birth"), text


def test_other_spanish_dates_are_not_births():
    assert _values("La factura es del 03/04/2025.", "date_of_birth") == []
    assert _values("Fecha de entrega: 03/04/2025", "date_of_birth") == []


def test_spanish_addresses_whole():
    cases = {
        "Vive en Calle Mayor 12, 3º B, 38001 Santa Cruz de Tenerife.":
            "Calle Mayor 12, 3º B, 38001 Santa Cruz de Tenerife",
        "Avenida de Anaga 5, 38001 Santa Cruz de Tenerife":
            "Avenida de Anaga 5, 38001 Santa Cruz de Tenerife",
        "Calle Mayor 12, 3o B, 38001 Santa Cruz": "Calle Mayor 12, 3o B, 38001 Santa Cruz",
        "vive en la calle de la Rosa 7": "calle de la Rosa 7",
        "C/ Gran Vía, 28, 28013 Madrid": "C/ Gran Vía, 28, 28013 Madrid",
        "Paseo de la Castellana, nº 100": "Paseo de la Castellana, nº 100",
        "Avda. Tres de Mayo 71": "Avda. Tres de Mayo 71",
        "en la Plaza del Pilar 3": "Plaza del Pilar 3",
        "Ctra. General del Norte 45": "Ctra. General del Norte 45",
    }
    for text, expected in cases.items():
        assert _values(text, "address") == [expected], text


def test_spanish_prose_without_an_address():
    for text in [
        "La calle estaba vacía a las 12.",
        "Nos vemos en la calle Mayor, junto a la farmacia.",
        "Hice el Camino de Santiago 2023 con mis hermanos.",
        "El hotel está en el Paseo Marítimo 5 minutos andando.",
        "Camino Real 3 km más allá.",
        "La plaza tiene 12 bancos.",
    ]:
        assert _values(text, "address") == [], text
