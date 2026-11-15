"""Testes adicionais: dados de referência.

1. A amostra de validação deve reproduzir as tabelas do README (lidas do próprio README).
2. O dataset real é comparado com um oráculo independente, que recalcula o relatório direto do
   CSV sem usar o pacote, e com os números-chave conferidos manualmente.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from helpers import PROJECT_ROOT, SRC_DIR

DATA_DIR = PROJECT_ROOT / "data"
RATES_PATH = DATA_DIR / "taxas_cambio.csv"


def generate(input_path: Path, output_path: Path, top: int = 5) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "onfly_report",
            "--input",
            str(input_path),
            "--rates",
            str(RATES_PATH),
            "--output",
            str(output_path),
            "--top",
            str(top),
        ],
        cwd=str(PROJECT_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report.pop("generated_at")  # ignorado na comparação, como diz o README
    return report


# --- 1. Amostra do README ----------------------------------------------------------------------


def readme_sample_tables() -> list[list[list[str]]]:
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("<!-- AMOSTRA:INICIO -->")[1].split("<!-- AMOSTRA:FIM -->")[0]
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("|"):
            cells = [cell.strip().replace("\\_", "_").strip("`") for cell in line.strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):  # ignora a linha separadora
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def test_validation_sample_matches_readme(tmp_path):
    summary_table, month_table, hotel_table = readme_sample_tables()
    report = generate(DATA_DIR / "exemplo-validacao.csv", tmp_path / "exemplo.json")

    expected_summary = {field: int(value) if "." not in value else value for field, value in summary_table[1:]}
    assert report["summary"] == expected_summary

    month_header, *month_rows = month_table
    expected_months = [dict(zip(month_header, row, strict=True)) for row in month_rows]
    for month in expected_months:
        month["reservations"] = int(month["reservations"])
        month["room_nights"] = int(month["room_nights"])
    assert report["by_month"] == expected_months

    hotel_header, *hotel_rows = hotel_table
    expected_hotels = [dict(zip(hotel_header, row, strict=True)) for row in hotel_rows]
    for hotel in expected_hotels:
        hotel["room_nights"] = int(hotel["room_nights"])
    assert report["top_hotels"] == expected_hotels


# --- 2. Dataset real ----------------------------------------------------------------------------


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def oracle(input_path: Path, top: int) -> dict:
    """Implementação mínima e independente das regras do README."""
    with RATES_PATH.open(encoding="utf-8", newline="") as handle:
        rates = {row["currency"]: Decimal(row["rate_to_brl"]) for row in csv.DictReader(handle)}
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    counts: dict[str, int] = defaultdict(int)
    nights_total, amount_total = 0, Decimal(0)
    months: dict[str, list] = defaultdict(lambda: [0, 0, Decimal(0)])
    hotels: dict[str, list] = {}
    for row in rows:
        counts[row["status"]] += 1
        if row["status"] != "CONFIRMED":
            continue
        stay = date.fromisoformat(row["checkout_date"]) - date.fromisoformat(row["checkin_date"])
        nights = stay.days * int(row["rooms"])
        brl = Decimal(row["amount"]) * rates[row["currency"]]
        nights_total += nights
        amount_total += brl
        month = months[row["checkin_date"][:7]]
        month[0], month[1], month[2] = month[0] + 1, month[1] + nights, month[2] + brl
        hotel = hotels.setdefault(row["hotel_id"], [row["hotel_name"], 0, Decimal(0)])
        hotel[1], hotel[2] = hotel[1] + nights, hotel[2] + brl

    ranking = sorted(hotels.items(), key=lambda item: (-item[1][2], item[0]))[:top]
    return {
        "report_version": "1.0",
        "summary": {
            "total_reservations": len(rows),
            "confirmed_reservations": counts["CONFIRMED"],
            "cancelled_reservations": counts["CANCELLED"],
            "no_show_reservations": counts["NO_SHOW"],
            "total_room_nights": nights_total,
            "total_amount_brl": money(amount_total),
            "average_nightly_rate_brl": money(amount_total / nights_total) if nights_total else "0.00",
        },
        "by_month": [
            {"month": key, "reservations": value[0], "room_nights": value[1], "total_brl": money(value[2])}
            for key, value in sorted(months.items())
        ],
        "top_hotels": [
            {"hotel_id": key, "hotel_name": value[0], "room_nights": value[1], "total_brl": money(value[2])}
            for key, value in ranking
        ],
    }


@pytest.mark.parametrize("top", [1, 5, 12, 50])
def test_full_dataset_matches_independent_oracle(tmp_path, top):
    input_path = DATA_DIR / "reservas_hoteis.csv"

    assert generate(input_path, tmp_path / "report.json", top=top) == oracle(input_path, top)


def test_full_dataset_headline_numbers(tmp_path):
    """Números-chave do dataset real, conferidos à mão (trava contra regressões no oráculo)."""
    report = generate(DATA_DIR / "reservas_hoteis.csv", tmp_path / "report.json")

    assert report["summary"] == {
        "total_reservations": 300,
        "confirmed_reservations": 235,
        "cancelled_reservations": 31,
        "no_show_reservations": 34,
        "total_room_nights": 1347,
        "total_amount_brl": "396170.00",
        "average_nightly_rate_brl": "294.11",
    }
    assert [month["month"] for month in report["by_month"]] == [
        "2024-12",
        "2025-01",
        "2025-02",
        "2025-03",
        "2025-04",
        "2025-05",
        "2025-06",
    ]
    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H06", "H10", "H12", "H07", "H11"]
