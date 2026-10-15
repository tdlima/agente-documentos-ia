from datetime import date

import pytest

from docagent.models import Solicitacao
from docagent.prompts import montar_pedido
from docagent.registry import ErroModelo, carregar_arquivo, carregar_modelos, obter_modelo

ESPERADOS = {
    "oficio",
    "relatorio",
    "pdi",
    "roteiro_entrevista",
    "ata_reuniao",
    "avaliacao_desempenho",
    "comunicado_interno",
}


def test_todos_os_modelos_carregam():
    assert ESPERADOS <= set(carregar_modelos())


@pytest.mark.parametrize("modelo_id", sorted(ESPERADOS))
def test_modelo_bem_formado(modelo_id):
    m = obter_modelo(modelo_id)
    assert m.campos and m.estrutura and m.instrucoes.strip()
    assert any(c.obrigatorio for c in m.campos), "todo modelo precisa de ao menos um campo obrigatório"
    ids = [c.id for c in m.campos]
    assert len(ids) == len(set(ids)), "ids de campo duplicados"
    for c in m.campos:
        if c.tipo == "selecao":
            assert c.opcoes, f"{c.id} é seleção sem opções"
            assert not c.padrao or c.padrao in c.opcoes


def test_modelo_inexistente():
    with pytest.raises(KeyError):
        obter_modelo("nao_existe")


def test_modelo_invalido(tmp_path):
    arquivo = tmp_path / "ruim.yaml"
    arquivo.write_text("id: x\nnome: Sem campos\n", encoding="utf-8")
    with pytest.raises(ErroModelo):
        carregar_arquivo(arquivo)


def test_pasta_extra_de_modelos(tmp_path, monkeypatch):
    (tmp_path / "proposta.yaml").write_text(
        "id: proposta\nnome: Proposta Comercial\ndescricao: Teste\n"
        "campos:\n  - {id: cliente, rotulo: Cliente, obrigatorio: true}\n"
        "estrutura: [Apresentação]\ninstrucoes: Seja objetivo.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DOCAGENT_TEMPLATES_DIR", str(tmp_path))
    carregar_modelos.cache_clear()
    try:
        assert "proposta" in carregar_modelos()
    finally:
        carregar_modelos.cache_clear()


def test_campos_obrigatorios_faltando():
    m = obter_modelo("oficio")
    faltando = m.campos_obrigatorios_faltando({"assunto": "Teste"})
    assert "Nome do destinatário" in faltando
    assert "Assunto" not in faltando


def test_prompt_contem_contexto(org):
    s = Solicitacao(
        modelo=obter_modelo("comunicado_interno"),
        valores={"para": "Equipe", "assunto": "Novo horário", "mensagem": "Expediente às 8h"},
        organizacao=org,
        instrucoes_extras="Seja breve.",
        data_referencia=date(2026, 10, 15),
    )
    pedido = montar_pedido(s)
    assert "15 de outubro de 2026" in pedido
    assert "Empresa Exemplo Ltda." in pedido
    assert "Expediente às 8h" in pedido
    assert "Seja breve." in pedido
    assert "(não informado)" in pedido  # campos vazios são sinalizados
