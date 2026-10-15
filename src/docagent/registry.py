"""Carrega os modelos de documento a partir de arquivos YAML.

Para criar um novo tipo de documento basta adicionar um arquivo `.yaml` em
`src/docagent/templates/` (ou em uma pasta indicada pela variável de ambiente
`DOCAGENT_TEMPLATES_DIR`). Nenhuma linha de Python precisa mudar.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ModeloDocumento

PASTA_PADRAO = Path(__file__).parent / "templates"


class ErroModelo(Exception):
    """Arquivo de modelo inválido."""


def _pastas() -> list[Path]:
    pastas = [PASTA_PADRAO]
    extra = os.getenv("DOCAGENT_TEMPLATES_DIR")
    if extra:
        pastas.append(Path(extra).expanduser())
    return pastas


def carregar_arquivo(caminho: Path) -> ModeloDocumento:
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        return ModeloDocumento.model_validate(dados)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ErroModelo(f"Modelo inválido em {caminho.name}: {exc}") from exc


@lru_cache(maxsize=1)
def carregar_modelos() -> dict[str, ModeloDocumento]:
    """Retorna {id: modelo}. Modelos de pastas extras sobrescrevem os padrões."""
    modelos: dict[str, ModeloDocumento] = {}
    for pasta in _pastas():
        if not pasta.is_dir():
            continue
        for arquivo in sorted(pasta.glob("*.y*ml")):
            modelo = carregar_arquivo(arquivo)
            modelos[modelo.id] = modelo
    return dict(sorted(modelos.items(), key=lambda par: (par[1].ordem, par[1].nome)))


def obter_modelo(modelo_id: str) -> ModeloDocumento:
    modelos = carregar_modelos()
    if modelo_id not in modelos:
        disponiveis = ", ".join(sorted(modelos))
        raise KeyError(f"Modelo '{modelo_id}' não encontrado. Disponíveis: {disponiveis}")
    return modelos[modelo_id]
