"""Usa o SDK oficial da Anthropic com um transporte HTTP simulado.

Garante que a requisição enviada pelo agente é válida para o SDK (structured
outputs com o schema `Documento`) e que a resposta é convertida corretamente,
sem precisar de chave de API nem de rede.
"""

import json

import anthropic

from docagent.agent import AgenteClaude
from docagent.config import Config
from docagent.models import Solicitacao
from docagent.registry import obter_modelo

try:  # versões recentes do SDK usam httpx2; as anteriores, httpx
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx


def test_requisicao_e_resposta_reais_do_sdk(documento, org):
    capturado = {}

    def responder(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_teste",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": documento.model_dump_json()}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1200, "output_tokens": 800},
            },
        )

    cliente = anthropic.Anthropic(
        api_key="sk-ant-teste",
        http_client=httpx.Client(transport=httpx.MockTransport(responder)),
        max_retries=0,
    )
    agente = AgenteClaude(Config(api_key="x", modelo="claude-sonnet-5-5", max_tokens=4000), cliente=cliente)
    s = Solicitacao(
        modelo=obter_modelo("comunicado_interno"),
        valores={"para": "Equipe", "assunto": "Teste", "mensagem": "Mensagem"},
        organizacao=org,
    )

    resultado = agente.redigir(s)

    corpo = capturado["corpo"]
    assert capturado["url"].endswith("/v1/messages")
    assert corpo["model"] == "claude-sonnet-5-5"
    formato = corpo["output_config"]["format"]
    assert formato["type"] == "json_schema"
    assert "blocos" in formato["schema"]["properties"]
    assert resultado.documento == documento
    assert resultado.uso.tokens_entrada == 1200
