"""Testes adicionais: contrato do CLI (schema, ordenação, arredondamento e códigos de saída)."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from helpers import BASE, COLUMNS, PROJECT_ROOT, SRC_DIR, run_cli

MONEY = re.compile(r"^\d+\.\d{2}$")
RATES = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"


def write_inputs(tmp_path: Path, rows: list[dict[str, str]], rates: str = RATES) -> tuple[Path, Path]:
    input_path = tmp_path / "reservas.csv"
    rates_path = tmp_path / "rates.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({**BASE, **row} for row in rows)
    rates_path.write_text(rates, encoding="utf-8")
    return input_path, rates_path


def run_raw(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=str(PROJECT_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


# --- Schema -------------------------------------------------------------------------------------


def test_report_schema_types_and_money_format(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1"},
            {"reservation_id": "R-2", "hotel_id": "H02", "currency": "USD", "amount": "33.33"},
            {"reservation_id": "R-3", "status": "CANCELLED"},
        ],
    )

    assert list(report) == ["report_version", "generated_at", "summary", "by_month", "top_hotels"]
    assert report["report_version"] == "1.0"
    assert datetime.fromisoformat(report["generated_at"]).utcoffset() == timedelta(hours=-3)
    assert report["generated_at"].endswith("-03:00")

    summary = report["summary"]
    assert list(summary) == [
        "total_reservations",
        "confirmed_reservations",
        "cancelled_reservations",
        "no_show_reservations",
        "total_room_nights",
        "total_amount_brl",
        "average_nightly_rate_brl",
    ]
    for key in list(summary)[:5]:
        assert type(summary[key]) is int, key
    for key in ("total_amount_brl", "average_nightly_rate_brl"):
        assert MONEY.match(summary[key]), summary[key]

    for month in report["by_month"]:
        assert list(month) == ["month", "reservations", "room_nights", "total_brl"]
        assert re.match(r"^\d{4}-\d{2}$", month["month"])
        assert MONEY.match(month["total_brl"])
    for hotel in report["top_hotels"]:
        assert list(hotel) == ["hotel_id", "hotel_name", "room_nights", "total_brl"]
        assert MONEY.match(hotel["total_brl"])


# --- Agregações ---------------------------------------------------------------------------------


def test_by_month_uses_checkin_month_ascending_and_only_confirmed(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "checkin_date": "2025-03-05", "checkout_date": "2025-03-07", "amount": "300.00"},
            {"reservation_id": "R-2", "checkin_date": "2025-01-30", "checkout_date": "2025-02-02", "amount": "100.00"},
            {
                "reservation_id": "R-3",
                "status": "CANCELLED",
                "checkin_date": "2025-02-10",
                "checkout_date": "2025-02-12",
            },
            {"reservation_id": "R-4", "status": "NO_SHOW", "checkin_date": "2025-04-10", "checkout_date": "2025-04-12"},
        ],
    )

    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 1, "room_nights": 3, "total_brl": "100.00"},
        {"month": "2025-03", "reservations": 1, "room_nights": 2, "total_brl": "300.00"},
    ]


def test_nights_across_year_boundary_with_multiple_rooms(tmp_path):
    report = run_cli(
        tmp_path,
        [{"reservation_id": "R-1", "checkin_date": "2024-12-30", "checkout_date": "2025-01-02", "rooms": "2"}],
    )

    assert report["summary"]["total_room_nights"] == 6
    assert report["by_month"][0]["month"] == "2024-12"


def test_top_hotels_aggregate_per_hotel_and_break_ties_by_hotel_id(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H03", "hotel_name": "Hotel C", "amount": "500.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "200.00"},
            {"reservation_id": "R-3", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "300.00"},
            {"reservation_id": "R-4", "hotel_id": "H02", "hotel_name": "Hotel B", "amount": "500.00"},
            {"reservation_id": "R-5", "hotel_id": "H04", "hotel_name": "Hotel D", "amount": "900.00"},
        ],
        top=3,
    )

    assert report["top_hotels"] == [
        {"hotel_id": "H04", "hotel_name": "Hotel D", "room_nights": 1, "total_brl": "900.00"},
        {"hotel_id": "H01", "hotel_name": "Hotel A", "room_nights": 2, "total_brl": "500.00"},
        {"hotel_id": "H02", "hotel_name": "Hotel B", "room_nights": 1, "total_brl": "500.00"},
    ]


def test_top_hotels_ignore_non_billable_and_respect_limit(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "50.00"},
            {"reservation_id": "R-3", "hotel_id": "H09", "status": "NO_SHOW", "amount": "5000.00"},
            {"reservation_id": "R-4", "hotel_id": "H08", "status": "CANCELLED", "amount": "4000.00"},
        ],
        top=10,
    )

    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H01", "H02"]


def test_default_top_is_five(tmp_path):
    rows = [{"reservation_id": f"R-{i}", "hotel_id": f"H{i:02d}", "amount": f"{i}00.00"} for i in range(1, 8)]
    input_path, rates_path = write_inputs(tmp_path, rows)
    output_path = tmp_path / "report.json"

    process = run_raw("--input", str(input_path), "--rates", str(rates_path), "--output", str(output_path))

    assert process.returncode == 0, process.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H07", "H06", "H05", "H04", "H03"]


def test_hotel_name_with_comma_is_preserved(tmp_path):
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "hotel_name": "Hotel Madrid, Gran Vía"}])

    assert report["top_hotels"][0]["hotel_name"] == "Hotel Madrid, Gran Vía"


def test_reads_more_than_200_reservations(tmp_path):
    rows = [{"reservation_id": f"R-{i}", "amount": "1.00"} for i in range(1, 251)]

    report = run_cli(tmp_path, rows)

    assert report["summary"]["total_reservations"] == 250
    assert report["summary"]["total_amount_brl"] == "250.00"


# --- Exatidão -----------------------------------------------------------------------------------


def test_rounds_only_on_serialization(tmp_path):
    """3 x USD 0.01 = 3 x 0.0542 = 0.1626 -> 0.16 (arredondando cada linha daria 0.15)."""
    rows = [{"reservation_id": f"R-{i}", "currency": "USD", "amount": "0.01"} for i in range(1, 4)]

    report = run_cli(tmp_path, rows)

    assert report["summary"]["total_amount_brl"] == "0.16"
    assert report["by_month"][0]["total_brl"] == "0.16"
    assert report["top_hotels"][0]["total_brl"] == "0.16"


def test_money_is_exact_decimal_not_float(tmp_path):
    """USD 0.75 x 5.42 = 4.065 exato -> 4.07. Em float daria 4.0649999... -> 4.06."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "currency": "USD", "amount": "0.75"}])

    assert report["summary"]["total_amount_brl"] == "4.07"


def test_average_nightly_rate_is_half_up(tmp_path):
    """1.00 BRL / 8 noites = 0.125 -> 0.13 em half-up."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "rooms": "8", "amount": "1.00"}])

    assert report["summary"]["total_room_nights"] == 8
    assert report["summary"]["average_nightly_rate_brl"] == "0.13"


def test_without_billable_reservations_everything_is_zero(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "status": "CANCELLED"},
            {"reservation_id": "R-2", "status": "NO_SHOW"},
        ],
    )

    assert report["summary"] == {
        "total_reservations": 2,
        "confirmed_reservations": 0,
        "cancelled_reservations": 1,
        "no_show_reservations": 1,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []


# --- Códigos de saída ---------------------------------------------------------------------------


@pytest.mark.parametrize("top", ["0", "-1", "abc"])
def test_invalid_top_exits_with_2(tmp_path, top):
    input_path, rates_path = write_inputs(tmp_path, [{}])

    process = run_raw("--input", str(input_path), "--rates", str(rates_path), "--top", top)

    assert process.returncode == 2


def test_missing_required_argument_exits_with_2(tmp_path):
    input_path, _ = write_inputs(tmp_path, [{}])

    assert run_raw("--input", str(input_path)).returncode == 2


@pytest.mark.parametrize("missing", ["input", "rates"])
def test_missing_file_exits_with_2(tmp_path, missing):
    input_path, rates_path = write_inputs(tmp_path, [{}])
    paths = {"input": input_path, "rates": rates_path}
    paths[missing] = tmp_path / "nao-existe.csv"

    process = run_raw("--input", str(paths["input"]), "--rates", str(paths["rates"]))

    assert process.returncode == 2
    assert "não encontrad" in process.stderr


def test_currency_without_rate_exits_with_2(tmp_path):
    input_path, rates_path = write_inputs(tmp_path, [{"currency": "GBP"}])

    process = run_raw("--input", str(input_path), "--rates", str(rates_path), "--output", str(tmp_path / "r.json"))

    assert process.returncode == 2
    assert "GBP" in process.stderr
    assert "linha 2" in process.stderr


def test_malformed_row_exits_with_2(tmp_path):
    input_path, rates_path = write_inputs(tmp_path, [{"checkin_date": "10/01/2025"}])

    process = run_raw("--input", str(input_path), "--rates", str(rates_path), "--output", str(tmp_path / "r.json"))

    assert process.returncode == 2


def test_creates_output_directory_and_prints_summary(tmp_path):
    input_path, rates_path = write_inputs(tmp_path, [{"amount": "100.00"}])
    output_path = tmp_path / "nested" / "dir" / "report.json"

    process = run_raw("--input", str(input_path), "--rates", str(rates_path), "--output", str(output_path))

    assert process.returncode == 0, process.stderr
    assert output_path.is_file()
    assert process.stdout.strip() == "Reservas: 1 | Confirmadas: 1 | Noites: 1 | Total BRL: 100.00"
