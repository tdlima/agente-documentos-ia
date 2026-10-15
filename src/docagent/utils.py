"""Funções auxiliares."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def data_por_extenso(d: date) -> str:
    """15 de outubro de 2026"""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def slug(texto: str, limite: int = 60) -> str:
    """Gera um nome de arquivo seguro: 'Ofício nº 45/2026' -> 'oficio-n-45-2026'."""
    normalizado = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    normalizado = re.sub(r"[^a-zA-Z0-9]+", "-", normalizado).strip("-").lower()
    return (normalizado[:limite].rstrip("-")) or "documento"
