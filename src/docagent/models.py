"""Modelos de dados do DocAgent.

O agente sempre produz um `Documento` com uma estrutura genérica (título,
metadados e uma lista de blocos). Essa estrutura neutra é o que permite que
qualquer tipo de documento seja exportado para Markdown, Word ou PDF pelos
mesmos renderizadores.

Todos os campos são obrigatórios de propósito: o esquema é enviado à API do
Claude como *structured output*, e campos obrigatórios (vazios quando não se
aplicam) deixam o esquema simples e previsível.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

TipoBloco = Literal[
    "titulo",  # subtítulo de seção (H2)
    "paragrafo",  # texto corrido
    "lista",  # lista com marcadores
    "lista_numerada",  # lista ordenada
    "tabela",  # tabela com cabeçalho
    "destaque",  # caixa de destaque / observação importante
    "assinatura",  # bloco de assinatura (nome em `texto`, cargo em `itens[0]`)
]


class Metadado(BaseModel):
    """Par rótulo/valor exibido no topo do documento (ex.: Data, Destinatário)."""

    rotulo: str = Field(description="Rótulo curto, ex.: 'Data', 'Destinatário'.")
    valor: str = Field(description="Valor correspondente.")


class Bloco(BaseModel):
    """Unidade de conteúdo do documento."""

    tipo: TipoBloco = Field(description="Tipo do bloco.")
    texto: str = Field(
        description=(
            "Texto do bloco. Para 'titulo' é o nome da seção; para 'paragrafo' "
            "e 'destaque' é o conteúdo; para 'assinatura' é o nome de quem assina. "
            "Use string vazia para listas e tabelas."
        )
    )
    itens: list[str] = Field(
        description=(
            "Itens de 'lista' e 'lista_numerada'. Para 'assinatura', o primeiro "
            "item é o cargo. Lista vazia nos demais casos."
        )
    )
    colunas: list[str] = Field(description="Cabeçalho da tabela (apenas para 'tabela'; senão, vazio).")
    linhas: list[list[str]] = Field(
        description=(
            "Linhas da tabela, cada uma com o mesmo número de células que "
            "'colunas' (apenas para 'tabela'; senão, vazio)."
        )
    )


class Documento(BaseModel):
    """Documento completo gerado pelo agente."""

    titulo: str = Field(description="Título principal do documento.")
    subtitulo: str = Field(description="Subtítulo ou linha de referência; pode ser vazio.")
    metadados: list[Metadado] = Field(description="Informações de cabeçalho.")
    blocos: list[Bloco] = Field(description="Corpo do documento, em ordem.")
    pendencias: list[str] = Field(
        description=(
            "Pontos que o usuário deve conferir ou completar antes de usar o "
            "documento (dados ausentes, suposições feitas). Lista vazia se nada."
        )
    )


# ---------------------------------------------------------------------------
# Perfil da organização (preenchido uma vez na barra lateral da interface)
# ---------------------------------------------------------------------------


class Organizacao(BaseModel):
    nome: str = ""
    cnpj: str = ""
    endereco: str = ""
    cidade_uf: str = ""
    telefone: str = ""
    email: str = ""
    site: str = ""
    responsavel: str = ""
    cargo_responsavel: str = ""
    segmento: str = ""
    logo: bytes | None = Field(default=None, exclude=True, repr=False)

    def linhas_cabecalho(self) -> list[str]:
        """Linhas de contato usadas no cabeçalho dos arquivos exportados."""
        linhas = []
        if self.cnpj:
            linhas.append(f"CNPJ: {self.cnpj}")
        endereco = " · ".join(p for p in (self.endereco, self.cidade_uf) if p)
        if endereco:
            linhas.append(endereco)
        contato = " · ".join(p for p in (self.telefone, self.email, self.site) if p)
        if contato:
            linhas.append(contato)
        return linhas

    def como_contexto(self) -> str:
        """Descrição textual usada no prompt do agente."""
        campos = {
            "Nome": self.nome,
            "CNPJ": self.cnpj,
            "Endereço": self.endereco,
            "Cidade/UF": self.cidade_uf,
            "Telefone": self.telefone,
            "E-mail": self.email,
            "Site": self.site,
            "Responsável": self.responsavel,
            "Cargo do responsável": self.cargo_responsavel,
            "Segmento de atuação": self.segmento,
        }
        preenchidos = [f"- {k}: {v}" for k, v in campos.items() if v]
        return "\n".join(preenchidos) if preenchidos else "- (não informado)"


# ---------------------------------------------------------------------------
# Definição de modelos de documento (carregados dos arquivos YAML)
# ---------------------------------------------------------------------------

TipoCampo = Literal["texto", "texto_longo", "data", "selecao", "numero", "lista"]


class Campo(BaseModel):
    id: str
    rotulo: str
    tipo: TipoCampo = "texto"
    obrigatorio: bool = False
    ajuda: str = ""
    exemplo: str = ""
    opcoes: list[str] = Field(default_factory=list)
    padrao: str = ""


class ModeloDocumento(BaseModel):
    id: str
    nome: str
    icone: str = "📄"
    ordem: int = 100
    categoria: str = "Geral"
    descricao: str
    campos: list[Campo]
    estrutura: list[str] = Field(description="Seções esperadas, na ordem em que devem aparecer.")
    instrucoes: str = Field(description="Orientações de redação para o agente.")
    tom_padrao: str = "formal"

    def campos_obrigatorios_faltando(self, valores: dict[str, str]) -> list[str]:
        return [c.rotulo for c in self.campos if c.obrigatorio and not str(valores.get(c.id, "")).strip()]


class Solicitacao(BaseModel):
    """Tudo o que o agente precisa para redigir um documento."""

    modelo: ModeloDocumento
    valores: dict[str, str]
    organizacao: Organizacao = Field(default_factory=Organizacao)
    tom: str = "formal"
    instrucoes_extras: str = ""
    data_referencia: date = Field(default_factory=date.today)
