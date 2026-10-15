"""Testes do agente com um cliente falso (não chamam a API)."""

from types import SimpleNamespace

import pytest

from docagent.agent import AgenteClaude, AgenteDemo, ErroAgente, criar_agente
from docagent.config import Config
from docagent.models import Documento, Solicitacao
from docagent.registry import obter_modelo

VALORES_OFICIO = {
    "destinatario_nome": "Maria Souza",
    "destinatario_orgao": "Prefeitura",
    "assunto": "Cessão de espaço",
    "conteudo": "Pedir o ginásio no dia 20/11.",
}


class ClienteFalso:
    """Imita `anthropic.Anthropic().messages.parse`."""

    def __init__(self, documentos, stop_reason="end_turn"):
        self._documentos = list(documentos)
        self.chamadas = []
        self.stop_reason = stop_reason
        self.messages = self

    def parse(self, **kwargs):
        self.chamadas.append(kwargs)
        return SimpleNamespace(
            parsed_output=self._documentos.pop(0),
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )


def _config():
    return Config(api_key="teste", modelo="claude-sonnet-5-5", max_tokens=1000)


def _solicitacao(org):
    return Solicitacao(modelo=obter_modelo("oficio"), valores=VALORES_OFICIO, organizacao=org)


def test_redigir_envia_schema_e_contexto(documento, org):
    cliente = ClienteFalso([documento])
    resultado = AgenteClaude(_config(), cliente=cliente).redigir(_solicitacao(org))

    chamada = cliente.chamadas[0]
    assert chamada["output_format"] is Documento
    assert chamada["model"] == "claude-sonnet-5-5"
    assert "Maria Souza" in chamada["messages"][0]["content"]
    assert resultado.documento == documento
    assert [m["role"] for m in resultado.historico] == ["user", "assistant"]
    assert resultado.uso.tokens_entrada == 100


def test_refinar_mantem_historico(documento, org):
    revisado = documento.model_copy(update={"titulo": "Versão revisada"})
    cliente = ClienteFalso([documento, revisado])
    agente = AgenteClaude(_config(), cliente=cliente)

    v1 = agente.redigir(_solicitacao(org))
    v2 = agente.refinar(v1, "Deixe mais curto")

    assert v2.versao == 2
    assert v2.documento.titulo == "Versão revisada"
    enviadas = cliente.chamadas[1]["messages"]
    assert [m["role"] for m in enviadas] == ["user", "assistant", "user"]
    assert "Deixe mais curto" in enviadas[-1]["content"]
    assert v2.uso.tokens_saida == 100  # acumula as duas chamadas


def test_campos_obrigatorios_sao_validados(org):
    agente = AgenteClaude(_config(), cliente=ClienteFalso([]))
    s = Solicitacao(modelo=obter_modelo("oficio"), valores={}, organizacao=org)
    with pytest.raises(ErroAgente, match="obrigatórios"):
        agente.redigir(s)


@pytest.mark.parametrize("motivo", ["refusal", "max_tokens"])
def test_paradas_anormais_viram_erro_amigavel(documento, org, motivo):
    agente = AgenteClaude(_config(), cliente=ClienteFalso([documento], stop_reason=motivo))
    with pytest.raises(ErroAgente):
        agente.redigir(_solicitacao(org))


def test_resposta_sem_documento(org):
    agente = AgenteClaude(_config(), cliente=ClienteFalso([None]))
    with pytest.raises(ErroAgente, match="interpretada"):
        agente.redigir(_solicitacao(org))


def test_modo_demo_sem_chave():
    agente = criar_agente(Config(api_key=None, modelo="x", max_tokens=1))
    assert isinstance(agente, AgenteDemo)


@pytest.mark.parametrize(
    "modelo_id",
    [
        "oficio",
        "relatorio",
        "pdi",
        "roteiro_entrevista",
        "ata_reuniao",
        "avaliacao_desempenho",
        "comunicado_interno",
    ],
)
def test_agente_demo_gera_todos_os_tipos(modelo_id, org):
    modelo = obter_modelo(modelo_id)
    valores = {c.id: (c.exemplo or "valor de teste") for c in modelo.campos}
    resultado = AgenteDemo().redigir(Solicitacao(modelo=modelo, valores=valores, organizacao=org))
    doc = resultado.documento
    assert doc.titulo == modelo.nome
    assert doc.blocos[0].tipo == "destaque"  # aviso do modo demonstração
    assert doc.blocos[-1].tipo == "assinatura"

    refinado = AgenteDemo().refinar(resultado, "mais curto")
    assert refinado.versao == 2
    assert any("mais curto" in p for p in refinado.documento.pendencias)
