"""Garante que os exemplos versionados continuam coerentes com o código.

- `prompt.md` é exatamente o que o agente envia hoje para aquela entrada;
- `resposta*.json` respeita o schema `Documento` (o mesmo exigido da API).
"""

import json
from datetime import date

import pytest

from docagent.models import Documento, Organizacao, Solicitacao
from docagent.prompts import montar_pedido
from docagent.registry import obter_modelo

from .conftest import EXEMPLOS

PASTAS = sorted(p for p in EXEMPLOS.iterdir() if p.is_dir())


@pytest.mark.parametrize("pasta", PASTAS, ids=lambda p: p.name)
def test_prompt_versionado_e_reproduzivel(pasta):
    entrada = json.loads((pasta / "entrada.json").read_text("utf-8"))
    org = Organizacao(**json.loads((EXEMPLOS / "organizacao.json").read_text("utf-8")))
    s = Solicitacao(
        modelo=obter_modelo(entrada["modelo"]),
        valores=entrada["valores"],
        organizacao=org,
        data_referencia=date(2026, 10, 15),
    )
    assert montar_pedido(s) == (pasta / "prompt.md").read_text("utf-8")


@pytest.mark.parametrize("pasta", PASTAS, ids=lambda p: p.name)
def test_respostas_respeitam_o_schema(pasta):
    for arquivo in pasta.glob("resposta*.json"):
        doc = Documento.model_validate_json(arquivo.read_text("utf-8"))
        for bloco in doc.blocos:
            if bloco.tipo == "tabela":
                assert all(len(linha) == len(bloco.colunas) for linha in bloco.linhas)
