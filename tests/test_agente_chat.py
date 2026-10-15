"""Testes do modo chat (copiar e colar no claude.ai, sem API)."""

import json

import pytest

from docagent.agent import AgenteChat, ErroAgente, ErroRespostaChat, criar_agente, interpretar_resposta_chat
from docagent.config import Config
from docagent.models import Solicitacao
from docagent.prompts import SISTEMA, montar_pedido
from docagent.registry import obter_modelo

from .test_agente import VALORES_OFICIO


def _solicitacao(org):
    return Solicitacao(modelo=obter_modelo("oficio"), valores=VALORES_OFICIO, organizacao=org)


def test_criar_agente_no_modo_chat():
    config = Config(api_key="ignorada", modelo="x", max_tokens=1, modo_chat=True)
    assert isinstance(criar_agente(config), AgenteChat)
    assert not config.modo_demo


def test_prompt_traz_regras_schema_e_pedido(org):
    s = _solicitacao(org)
    pedido = AgenteChat().preparar(s)

    assert SISTEMA.strip() in pedido.prompt
    assert montar_pedido(s) in pedido.prompt  # mesmo pedido enviado à API
    assert '"pendencias"' in pedido.prompt and '"blocos"' in pedido.prompt  # schema de Documento
    assert "```json" in pedido.prompt
    assert pedido.versao == 1
    assert pedido.historico == [{"role": "user", "content": pedido.prompt}]


def test_campos_obrigatorios_sao_validados(org):
    s = Solicitacao(modelo=obter_modelo("oficio"), valores={}, organizacao=org)
    with pytest.raises(ErroAgente, match="obrigatórios"):
        AgenteChat().preparar(s)


@pytest.mark.parametrize(
    "molde",
    [
        "{json}",
        "```json\n{json}\n```",
        "Aqui está o documento:\n\n```json\n{json}\n```\n\nQualquer ajuste, é só pedir.",
        "Segue:\n{json}\nFim.",
    ],
)
def test_le_resposta_com_ou_sem_bloco_de_codigo(documento, org, molde):
    agente = AgenteChat()
    pedido = agente.preparar(_solicitacao(org))
    resposta = molde.replace("{json}", documento.model_dump_json(indent=2))

    resultado = agente.concluir(pedido, resposta)

    assert resultado.documento == documento
    assert [m["role"] for m in resultado.historico] == ["user", "assistant"]
    assert resultado.uso.tokens_entrada == 0


def test_refinamento_traz_documento_atual_e_incrementa_versao(documento, org):
    agente = AgenteChat()
    v1 = agente.concluir(agente.preparar(_solicitacao(org)), documento.model_dump_json())

    pedido = agente.preparar_refinamento(v1, "Deixe mais curto")
    assert "Deixe mais curto" in pedido.prompt
    assert documento.titulo in pedido.prompt  # documento atual vai junto
    assert pedido.versao == 2

    revisado = documento.model_copy(update={"titulo": "Versão revisada"})
    v2 = agente.concluir(pedido, f"```json\n{revisado.model_dump_json()}\n```")
    assert v2.versao == 2
    assert v2.documento.titulo == "Versão revisada"
    assert [m["role"] for m in v2.historico] == ["user", "assistant", "user", "assistant"]


def test_refinamento_vazio(documento, org):
    agente = AgenteChat()
    v1 = agente.concluir(agente.preparar(_solicitacao(org)), documento.model_dump_json())
    with pytest.raises(ErroAgente, match="ajustar"):
        agente.preparar_refinamento(v1, "   ")


def test_resposta_vazia():
    with pytest.raises(ErroAgente, match="Cole a resposta"):
        interpretar_resposta_chat("  \n ")


def test_resposta_sem_json_traz_mensagem_de_correcao():
    with pytest.raises(ErroRespostaChat, match="Não encontrei") as erro:
        interpretar_resposta_chat("Desculpe, não consegui gerar o documento.")
    assert "```json" in erro.value.correcao


def test_json_invalido(documento):
    quebrado = documento.model_dump_json()[:-10]  # sem o fechamento
    with pytest.raises(ErroRespostaChat):
        interpretar_resposta_chat(quebrado + "}")


def test_campo_faltando_aparece_na_correcao(documento):
    dados = documento.model_dump()
    del dados["pendencias"]
    dados["blocos"][0]["tipo"] = "capitulo"

    with pytest.raises(ErroRespostaChat, match="2 problema") as erro:
        interpretar_resposta_chat(json.dumps(dados, ensure_ascii=False))
    assert "pendencias" in erro.value.correcao
    assert "blocos.0.tipo" in erro.value.correcao
