"""Teste de ponta a ponta da interface Streamlit (modo demonstração)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def test_app_abre_em_modo_demo(app):
    assert any("Modo demonstração" in i.value for i in app.info)
    assert app.radio(key="tipo_documento").value == "oficio"  # primeiro pela 'ordem' do YAML


def test_gera_documento_e_oferece_downloads(app):
    app.radio(key="tipo_documento").set_value("comunicado_interno").run()
    app.text_input(key="comunicado_interno__para").input("Todos os colaboradores")
    app.text_input(key="comunicado_interno__assunto").input("Novo horário de expediente")
    app.text_area(key="comunicado_interno__mensagem").input("A partir de segunda, das 8h às 17h.")
    app.button[0].click().run()  # botão do formulário: Gerar documento

    assert not app.exception
    assert not app.error
    resultado = app.session_state["resultado"]
    assert resultado is not None
    assert resultado.documento.subtitulo == "Novo horário de expediente"


def test_campos_obrigatorios_mostram_erro(app):
    app.radio(key="tipo_documento").set_value("oficio").run()
    app.button[0].click().run()
    assert app.error and "obrigatórios" in app.error[0].value
