"""Testes adicionais: regras de negócio isoladas, serviço a serviço."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from helpers import BASE, COLUMNS

from onfly_report.exceptions import InputFileError, MissingExchangeRateError
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository
from onfly_report.services.currency_converter import convert_to_brl
from onfly_report.services.report_builder import format_money
from onfly_report.services.status_policy import is_billable
from onfly_report.services.stay_calculator import calculate_room_nights

RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}


@pytest.mark.parametrize(
    ("checkin", "checkout", "rooms", "expected"),
    [
        (date(2025, 1, 10), date(2025, 1, 13), 1, 3),  # exemplo do README (não inclusivo)
        (date(2025, 1, 30), date(2025, 2, 2), 1, 3),  # virada de mês
        (date(2024, 12, 30), date(2025, 1, 2), 1, 3),  # virada de ano
        (date(2024, 2, 28), date(2024, 3, 1), 1, 2),  # fevereiro de ano bissexto
        (date(2025, 2, 28), date(2025, 3, 1), 1, 1),  # fevereiro comum
        (date(2025, 1, 10), date(2025, 1, 13), 3, 9),  # multiplica pelo número de quartos
    ],
)
def test_room_nights_use_date_difference(checkin, checkout, rooms, expected):
    assert calculate_room_nights(checkin, checkout, rooms) == expected


def test_conversion_multiplies_by_rate():
    assert convert_to_brl(Decimal("100.00"), "USD", RATES) == Decimal("542.00")
    assert convert_to_brl(Decimal("150.00"), "EUR", RATES) == Decimal("882.00")
    assert convert_to_brl(Decimal("123.45"), "BRL", RATES) == Decimal("123.45")


def test_conversion_is_exact_decimal_without_rounding():
    result = convert_to_brl(Decimal("0.01"), "USD", RATES)
    assert isinstance(result, Decimal)
    assert result == Decimal("0.0542")  # nada de float nem arredondamento intermediário
    # Em float, 0.09 * 5.42 vira 0.48779999999999996; em Decimal a conta é exata.
    assert convert_to_brl(Decimal("0.09"), "USD", RATES) == Decimal("0.4878")


def test_missing_rate_is_an_input_error():
    with pytest.raises(MissingExchangeRateError, match="GBP") as excinfo:
        convert_to_brl(Decimal("10.00"), "GBP", RATES)
    assert isinstance(excinfo.value, InputFileError)  # o CLI responde com código 2


@pytest.mark.parametrize(
    ("status", "expected"),
    [("CONFIRMED", True), ("CANCELLED", False), ("NO_SHOW", False), ("PENDING", False), ("", False)],
)
def test_only_confirmed_is_billable(status, expected):
    assert is_billable(status) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.675", "2.68"),
        ("2.665", "2.67"),  # half-up, não arredondamento bancário (que daria 2.66)
        ("1.005", "1.01"),
        ("0.125", "0.13"),
        ("0.004", "0.00"),
        ("1234.5", "1234.50"),
        ("396170", "396170.00"),
        ("0", "0.00"),
    ],
)
def test_format_money_half_up_two_places(value, expected):
    assert format_money(Decimal(value)) == expected


def test_repository_reads_every_row(tmp_path):
    path = tmp_path / "reservas.csv"
    lines = [",".join(COLUMNS)]
    for index in range(1, 251):
        row = {**BASE, "reservation_id": f"R-{index}"}
        lines.append(",".join(row[column] for column in COLUMNS))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = CsvReservationRepository(path).read()

    assert len(rows) == 250
    assert rows[-1].values["reservation_id"] == "R-250"
