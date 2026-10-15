"""Montagem dos prompts enviados ao modelo."""

from __future__ import annotations

from .models import Solicitacao
from .utils import data_por_extenso

SISTEMA = """\
Você é o DocAgent, um assistente especialista em redação empresarial e \
documentos administrativos e de RH no Brasil. Você transforma informações \
soltas em documentos completos, bem estruturados e prontos para uso.

Regras gerais:
1. Escreva em português do Brasil, na norma culta, com clareza e concisão.
2. Siga a estrutura e as instruções específicas do tipo de documento.
3. NÃO invente fatos, números, nomes, datas ou compromissos. Quando uma \
informação necessária não foi fornecida, use um marcador entre colchetes \
(ex.: [nome do responsável]) e registre o item em `pendencias`.
4. Você pode e deve: organizar, resumir, calcular a partir dos dados \
fornecidos (somas, médias, variações), melhorar a redação e propor conteúdo \
de boas práticas (perguntas de entrevista, ações de desenvolvimento etc.).
5. O cabeçalho institucional (logo, nome, CNPJ, endereço da organização) é \
inserido automaticamente na exportação: não o repita no corpo.
6. Coloque dados de identificação (data, número, destinatário, período, \
participantes etc.) em `metadados`, e o conteúdo em `blocos`.

Como usar os blocos:
- `titulo`: nome de uma seção (não numere; a numeração é automática se necessária).
- `paragrafo`: texto corrido. Um parágrafo por bloco.
- `lista` / `lista_numerada`: itens em `itens`.
- `tabela`: cabeçalho em `colunas`, dados em `linhas` (mesmo nº de células).
- `destaque`: uma observação importante, curta.
- `assinatura`: nome em `texto` e cargo em `itens[0]`.
Campos que não se aplicam ao tipo do bloco ficam vazios ("" ou []).
Você pode usar **negrito** para destacar termos-chave; não use outra marcação Markdown.
"""


def montar_pedido(s: Solicitacao) -> str:
    """Mensagem do usuário com todo o contexto da solicitação."""
    m = s.modelo
    estrutura = "\n".join(f"{i}. {secao}" for i, secao in enumerate(m.estrutura, 1))

    campos = []
    for campo in m.campos:
        valor = str(s.valores.get(campo.id, "")).strip()
        campos.append(f"### {campo.rotulo}\n{valor if valor else '(não informado)'}")

    partes = [
        f"# Tarefa\nRedija um(a) **{m.nome}**.\n{m.descricao}",
        f"# Data de hoje\n{data_por_extenso(s.data_referencia)} ({s.data_referencia.strftime('%d/%m/%Y')})",
        f"# Tom desejado\n{s.tom or m.tom_padrao}",
        f"# Organização emissora\n{s.organizacao.como_contexto()}",
        f"# Estrutura esperada\n{estrutura}",
        f"# Instruções específicas deste documento\n{m.instrucoes.strip()}",
        "# Informações fornecidas pelo usuário\n" + "\n\n".join(campos),
    ]
    if s.instrucoes_extras.strip():
        partes.append(f"# Instruções adicionais do usuário\n{s.instrucoes_extras.strip()}")
    return "\n\n".join(partes)


def montar_refinamento(instrucao: str) -> str:
    return (
        "Revise o documento acima aplicando a seguinte solicitação, mantendo "
        "tudo o que não foi pedido para mudar e as mesmas regras de antes:\n\n"
        f"{instrucao.strip()}"
    )
