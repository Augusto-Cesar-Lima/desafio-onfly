"""Conversão de valores para BRL."""

from __future__ import annotations

from decimal import Decimal

from ..exceptions import MissingExchangeRateError


def convert_to_brl(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Converte um valor na moeda informada para BRL: ``amount * rate_to_brl``.

    A conta é feita em ``Decimal`` e sem arredondamento; o arredondamento acontece só na
    serialização do relatório.
    """
    try:
        rate = rates[currency]
    except KeyError as err:
        raise MissingExchangeRateError(f"moeda sem taxa de câmbio: {currency!r}") from err
    return amount * rate
