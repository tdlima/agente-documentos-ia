"""Testa a skill empacotada como se estivesse instalada no Claude."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from .conftest import EXEMPLOS, RAIZ

sys.path.insert(0, str(RAIZ / "scripts"))
from empacotar_skill import montar  # noqa: E402


@pytest.fixture(scope="module")
def skill(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("skill")
    arquivo_zip = montar(base)
    destino = tmp_path_factory.mktemp("instalada")
    with zipfile.ZipFile(arquivo_zip) as z:
        nomes = z.namelist()
        assert all(n.startswith("docagent/") for n in nomes), "a pasta da skill deve ser a raiz do ZIP"
        assert "docagent/SKILL.md" in nomes
        z.extractall(destino)
    return destino / "docagent"


def _rodar(skill: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=skill, capture_output=True, text=True, encoding="utf-8", check=False
    )


def test_lista_modelos(skill):
    r = _rodar(skill, "scripts/modelo.py", "--listar")
    assert r.returncode == 0, r.stderr
    assert "oficio" in r.stdout and "roteiro_entrevista" in r.stdout


def test_guia_do_modelo(skill):
    r = _rodar(skill, "scripts/modelo.py", "relatorio")
    assert r.returncode == 0, r.stderr
    assert "Estrutura esperada" in r.stdout and "Resumo executivo" in r.stdout


def test_exporta_documento(skill, tmp_path):
    org = tmp_path / "org.json"
    org.write_text((EXEMPLOS / "organizacao.json").read_text("utf-8"), encoding="utf-8")
    r = _rodar(
        skill,
        "scripts/exportar.py",
        str(EXEMPLOS / "relatorio" / "resposta.json"),
        "--org",
        str(org),
        "--logo",
        str(EXEMPLOS / "logo_exemplo.png"),
        "--formatos",
        "docx",
        "pdf",
        "md",
        "--saida",
        str(tmp_path / "saida"),
        "--nome",
        "relatorio",
    )
    assert r.returncode == 0, r.stderr
    for ext in ("docx", "pdf", "md"):
        assert (tmp_path / "saida" / f"relatorio.{ext}").stat().st_size > 500
    assert "PENDÊNCIAS" in r.stdout


def test_campos_vazios_podem_ser_omitidos(skill, tmp_path):
    doc = tmp_path / "doc.json"
    doc.write_text('{"titulo": "Teste", "blocos": [{"tipo": "paragrafo", "texto": "Olá"}]}', encoding="utf-8")
    r = _rodar(skill, "scripts/exportar.py", str(doc), "--saida", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "teste.pdf").exists()


def test_erro_de_formato_e_explicado(skill, tmp_path):
    doc = tmp_path / "ruim.json"
    doc.write_text('{"blocos": [{"tipo": "inexistente"}]}', encoding="utf-8")
    r = _rodar(skill, "scripts/exportar.py", str(doc))
    assert r.returncode != 0
    assert "titulo" in r.stderr and "blocos.0.tipo" in r.stderr


def test_regras_de_redacao_iguais_ao_app(skill):
    from docagent.prompts import SISTEMA

    assert SISTEMA in (skill / "referencias" / "regras_de_redacao.md").read_text("utf-8")
