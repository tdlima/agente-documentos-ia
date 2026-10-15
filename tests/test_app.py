"""Teste de ponta a ponta da interface Streamlit (modo demonstração)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
EXEMPLOS = Path(__file__).resolve().parents[1] / "exemplos"


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


def _botao(app, rotulo):
    return next(b for b in app.button if b.label == rotulo)


def test_modo_chat_copiar_e_colar(app):
    resposta = (EXEMPLOS / "oficio" / "resposta.json").read_text("utf-8")

    app.toggle(key="modo_chat").set_value(True).run()
    app.radio(key="tipo_documento").set_value("oficio").run()
    app.text_input(key="oficio__destinatario_nome").input("Maria Souza")
    app.text_input(key="oficio__destinatario_orgao").input("Prefeitura")
    app.text_input(key="oficio__assunto").input("Cessão de espaço")
    app.text_area(key="oficio__conteudo").input("Pedir o ginásio no dia 20/11.")
    app.button[0].click().run()  # Gerar documento -> mostra o prompt

    assert not app.exception and not app.error
    pedido = app.session_state["pedido_chat"]
    assert "Maria Souza" in pedido.prompt
    assert any(c.value == pedido.prompt for c in app.code)

    app.text_area(key="resposta_chat_1").input("isto não é um documento")
    _botao(app, "📥 Ler resposta").click().run()
    assert app.error and "JSON" in app.error[0].value
    assert app.session_state["resultado"] is None

    app.text_area(key="resposta_chat_1").input(f"```json\n{resposta}\n```")
    _botao(app, "📥 Ler resposta").click().run()
    assert not app.exception and not app.error
    assert app.session_state["resultado"].documento.titulo
    assert app.session_state["pedido_chat"] is None


def test_campos_obrigatorios_mostram_erro(app):
    app.radio(key="tipo_documento").set_value("oficio").run()
    app.button[0].click().run()
    assert app.error and "obrigatórios" in app.error[0].value
