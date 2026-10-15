import json
from pathlib import Path

import pytest

from docagent.models import Documento, Organizacao

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLOS = RAIZ / "exemplos"


@pytest.fixture
def org() -> Organizacao:
    return Organizacao(
        nome="Empresa Exemplo Ltda.",
        cnpj="00.000.000/0001-00",
        endereco="Rua das Flores, 100",
        cidade_uf="Montes Claros/MG",
        email="contato@exemplo.com.br",
        responsavel="João Lima",
        cargo_responsavel="Diretor Administrativo",
        logo=(EXEMPLOS / "logo_exemplo.png").read_bytes(),
    )


@pytest.fixture(params=["pdi_exemplo.json", "oficio_exemplo.json"])
def documento(request) -> Documento:
    return Documento.model_validate(json.loads((EXEMPLOS / request.param).read_text("utf-8")))
