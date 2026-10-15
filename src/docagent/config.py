"""Configurações lidas de variáveis de ambiente (ou de um arquivo .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv é opcional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

MODELO_PADRAO = "claude-sonnet-5-5"

MODELOS_DISPONIVEIS = {
    "claude-sonnet-5-5": "Claude Sonnet 5.5 — equilíbrio entre qualidade e velocidade",
    "claude-opus-5-5": "Claude Opus 5.5 — máxima qualidade",
    "claude-haiku-5-5": "Claude Haiku 5.5 — mais rápido e econômico",
}


@dataclass(frozen=True)
class Config:
    api_key: str | None
    modelo: str
    max_tokens: int

    @property
    def modo_demo(self) -> bool:
        return not self.api_key


def carregar_config() -> Config:
    return Config(
        api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        modelo=os.getenv("DOCAGENT_MODEL", MODELO_PADRAO),
        max_tokens=int(os.getenv("DOCAGENT_MAX_TOKENS", "8000")),
    )
