"""Política de status das reservas."""

from __future__ import annotations

BILLABLE_STATUSES = frozenset({"CONFIRMED"})


def is_billable(status: str) -> bool:
    """Indica se a reserva entra nos totais financeiros e de noites.

    Lista de permissão: só CONFIRMED é faturável. CANCELLED, NO_SHOW ou qualquer status novo
    ficam fora dos totais por padrão.
    """
    return status in BILLABLE_STATUSES
