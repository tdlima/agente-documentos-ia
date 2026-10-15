"""O agente redator.

Fluxo:
    Solicitação (modelo + campos + organização)
        └─> prompt estruturado
              └─> Claude (structured outputs: resposta validada contra `Documento`)
                    └─> Documento  ──> renderizadores (MD / DOCX / PDF)

O histórico da conversa é mantido em `Resultado`, o que permite refinar o
documento em várias rodadas ("deixe mais curto", "inclua uma tabela"...).

Sem `ANTHROPIC_API_KEY`, o `AgenteDemo` monta um documento a partir dos
campos preenchidos, para que o projeto possa ser testado sem custo.

O `AgenteChat` troca a API pelo chat do Claude: gera o prompt para copiar e
colar no claude.ai e valida a resposta colada de volta, reaproveitando o
mesmo prompt, schema e renderizadores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .config import Config, carregar_config
from .models import Bloco, Documento, Metadado, Solicitacao
from .prompts import (
    SISTEMA,
    montar_correcao_chat,
    montar_pedido,
    montar_prompt_chat,
    montar_refinamento,
    montar_refinamento_chat,
)
from .utils import data_por_extenso


class ErroAgente(Exception):
    """Falha ao gerar o documento, com mensagem amigável para o usuário."""


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_saida: int = 0

    def somar(self, entrada: int, saida: int) -> None:
        self.tokens_entrada += entrada
        self.tokens_saida += saida


@dataclass
class Resultado:
    documento: Documento
    solicitacao: Solicitacao
    historico: list[dict[str, Any]] = field(default_factory=list)
    uso: Uso = field(default_factory=Uso)
    versao: int = 1


# ---------------------------------------------------------------------------
# Agente com Claude
# ---------------------------------------------------------------------------


class AgenteClaude:
    """Redige documentos usando a API do Claude com saída estruturada."""

    def __init__(self, config: Config | None = None, cliente: Any | None = None):
        self.config = config or carregar_config()
        if cliente is None:
            if not self.config.api_key:
                raise ErroAgente("Defina ANTHROPIC_API_KEY para usar o Claude.")
            import anthropic

            cliente = anthropic.Anthropic(api_key=self.config.api_key)
        self.cliente = cliente

    # -- API pública --------------------------------------------------------

    def redigir(self, solicitacao: Solicitacao) -> Resultado:
        faltando = solicitacao.modelo.campos_obrigatorios_faltando(solicitacao.valores)
        if faltando:
            raise ErroAgente("Preencha os campos obrigatórios: " + ", ".join(faltando))

        historico = [{"role": "user", "content": montar_pedido(solicitacao)}]
        uso = Uso()
        documento = self._chamar(historico, uso)
        return Resultado(
            documento=documento,
            solicitacao=solicitacao,
            historico=historico + [self._como_mensagem(documento)],
            uso=uso,
        )

    def refinar(self, resultado: Resultado, instrucao: str) -> Resultado:
        if not instrucao.strip():
            raise ErroAgente("Descreva o que deseja ajustar no documento.")
        historico = resultado.historico + [{"role": "user", "content": montar_refinamento(instrucao)}]
        novo = self._chamar(historico, resultado.uso)
        return Resultado(
            documento=novo,
            solicitacao=resultado.solicitacao,
            historico=historico + [self._como_mensagem(novo)],
            uso=resultado.uso,
            versao=resultado.versao + 1,
        )

    # -- Internos -----------------------------------------------------------

    @staticmethod
    def _como_mensagem(doc: Documento) -> dict[str, Any]:
        return {"role": "assistant", "content": doc.model_dump_json()}

    def _chamar(self, mensagens: list[dict[str, Any]], uso: Uso) -> Documento:
        import anthropic

        try:
            resposta = self.cliente.messages.parse(
                model=self.config.modelo,
                max_tokens=self.config.max_tokens,
                system=SISTEMA,
                messages=mensagens,
                output_format=Documento,
            )
        except anthropic.AuthenticationError as exc:
            raise ErroAgente("Chave de API inválida. Confira ANTHROPIC_API_KEY.") from exc
        except anthropic.RateLimitError as exc:
            raise ErroAgente("Limite de uso da API atingido. Tente novamente em instantes.") from exc
        except anthropic.APIConnectionError as exc:
            raise ErroAgente("Não foi possível conectar à API do Claude.") from exc
        except anthropic.APIStatusError as exc:
            raise ErroAgente(f"Erro da API do Claude ({exc.status_code}): {exc.message}") from exc

        if getattr(resposta, "usage", None):
            uso.somar(resposta.usage.input_tokens, resposta.usage.output_tokens)

        if resposta.stop_reason == "refusal":
            raise ErroAgente("O modelo recusou esta solicitação. Revise o conteúdo informado.")
        if resposta.stop_reason == "max_tokens":
            raise ErroAgente(
                "O documento ficou maior que o limite de tokens. "
                "Aumente DOCAGENT_MAX_TOKENS ou peça um documento mais enxuto."
            )
        documento = resposta.parsed_output
        if documento is None:
            raise ErroAgente("A resposta do modelo não pôde ser interpretada. Tente novamente.")
        return documento


# ---------------------------------------------------------------------------
# Agente de demonstração (sem chave de API)
# ---------------------------------------------------------------------------


class AgenteDemo:
    """Monta o documento diretamente dos campos, sem IA.

    Útil para conhecer a interface, rodar testes e validar exportações.
    """

    AVISO = (
        "Modo demonstração: o texto abaixo foi montado a partir dos campos, sem IA. "
        "Configure ANTHROPIC_API_KEY para que o agente redija o documento completo."
    )

    def redigir(self, solicitacao: Solicitacao) -> Resultado:
        faltando = solicitacao.modelo.campos_obrigatorios_faltando(solicitacao.valores)
        if faltando:
            raise ErroAgente("Preencha os campos obrigatórios: " + ", ".join(faltando))
        return Resultado(documento=self._montar(solicitacao), solicitacao=solicitacao)

    def refinar(self, resultado: Resultado, instrucao: str) -> Resultado:
        doc = resultado.documento.model_copy(deep=True)
        doc.pendencias.append(f"Ajuste solicitado (não aplicado no modo demonstração): {instrucao}")
        return Resultado(
            documento=doc,
            solicitacao=resultado.solicitacao,
            versao=resultado.versao + 1,
        )

    def _montar(self, s: Solicitacao) -> Documento:
        m, org = s.modelo, s.organizacao
        metadados = [Metadado(rotulo="Data", valor=data_por_extenso(s.data_referencia))]
        blocos: list[Bloco] = [_bloco("destaque", self.AVISO)]
        pendencias: list[str] = []

        for campo in m.campos:
            valor = str(s.valores.get(campo.id, "")).strip()
            if not valor:
                if campo.obrigatorio:
                    pendencias.append(f"Preencher: {campo.rotulo}")
                continue
            if campo.tipo in ("texto", "data", "selecao", "numero") and len(valor) <= 80:
                metadados.append(Metadado(rotulo=campo.rotulo, valor=valor))
            elif campo.tipo == "lista" or "\n" in valor:
                itens = [linha.strip(" -•\t") for linha in valor.splitlines() if linha.strip()]
                blocos += [_bloco("titulo", campo.rotulo), _bloco("lista", itens=itens)]
            else:
                blocos += [_bloco("titulo", campo.rotulo), _bloco("paragrafo", valor)]

        blocos += [
            _bloco("titulo", "Estrutura recomendada"),
            _bloco("lista_numerada", itens=m.estrutura),
        ]
        if org.responsavel:
            blocos.append(_bloco("assinatura", org.responsavel, itens=[org.cargo_responsavel]))

        return Documento(
            titulo=m.nome,
            subtitulo=str(s.valores.get("assunto") or s.valores.get("titulo") or ""),
            metadados=metadados,
            blocos=blocos,
            pendencias=pendencias,
        )


def _bloco(tipo: str, texto: str = "", itens: list[str] | None = None) -> Bloco:
    return Bloco(tipo=tipo, texto=texto, itens=itens or [], colunas=[], linhas=[])


# ---------------------------------------------------------------------------
# Agente via chat do Claude (copiar e colar, sem API)
# ---------------------------------------------------------------------------


class ErroRespostaChat(ErroAgente):
    """Resposta colada que não virou um `Documento`; `correcao` é o texto para pedir o ajuste no chat."""

    def __init__(self, mensagem: str, correcao: str):
        super().__init__(mensagem)
        self.correcao = correcao


@dataclass
class PedidoChat:
    """Prompt aguardando a resposta do chat do Claude."""

    prompt: str
    solicitacao: Solicitacao
    historico: list[dict[str, Any]]
    versao: int = 1


class AgenteChat:
    """Mesmo fluxo do `AgenteClaude`, com o chat do Claude no lugar da API.

    Em duas etapas: `preparar` (ou `preparar_refinamento`) gera o texto a colar
    no chat; `concluir` valida a resposta colada contra `Documento`.
    """

    def preparar(self, solicitacao: Solicitacao) -> PedidoChat:
        faltando = solicitacao.modelo.campos_obrigatorios_faltando(solicitacao.valores)
        if faltando:
            raise ErroAgente("Preencha os campos obrigatórios: " + ", ".join(faltando))
        prompt = montar_prompt_chat(solicitacao)
        return PedidoChat(
            prompt=prompt,
            solicitacao=solicitacao,
            historico=[{"role": "user", "content": prompt}],
        )

    def preparar_refinamento(self, resultado: Resultado, instrucao: str) -> PedidoChat:
        if not instrucao.strip():
            raise ErroAgente("Descreva o que deseja ajustar no documento.")
        prompt = montar_refinamento_chat(resultado.documento, instrucao)
        return PedidoChat(
            prompt=prompt,
            solicitacao=resultado.solicitacao,
            historico=resultado.historico + [{"role": "user", "content": prompt}],
            versao=resultado.versao + 1,
        )

    def concluir(self, pedido: PedidoChat, resposta: str) -> Resultado:
        documento = interpretar_resposta_chat(resposta)
        return Resultado(
            documento=documento,
            solicitacao=pedido.solicitacao,
            historico=pedido.historico + [AgenteClaude._como_mensagem(documento)],
            versao=pedido.versao,
        )


def interpretar_resposta_chat(resposta: str) -> Documento:
    """Extrai o JSON da resposta colada (com ou sem bloco ```json) e valida contra `Documento`."""
    texto = resposta.strip()
    if not texto:
        raise ErroAgente("Cole a resposta do Claude antes de continuar.")

    cerca = re.search(r"```(?:json)?\s*\n(.*?)```", texto, re.S)
    if cerca:
        texto = cerca.group(1)
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim < inicio:
        raise ErroRespostaChat(
            "Não encontrei um JSON na resposta colada.",
            montar_correcao_chat("- A resposta não contém um objeto JSON."),
        )

    try:
        return Documento.model_validate_json(texto[inicio : fim + 1])
    except ValidationError as exc:
        erros = [f"- {'.'.join(str(p) for p in e['loc']) or '(raiz)'}: {e['msg']}" for e in exc.errors()[:8]]
        if exc.error_count() > 8:
            erros.append(f"- ... e mais {exc.error_count() - 8} problema(s).")
        raise ErroRespostaChat(
            f"A resposta colada não segue o formato do documento ({exc.error_count()} problema(s)).",
            montar_correcao_chat("\n".join(erros)),
        ) from exc


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------


def criar_agente(config: Config | None = None) -> AgenteClaude | AgenteDemo | AgenteChat:
    """Agente do chat se `modo_chat`; senão, Claude se houver chave de API; senão, demonstração."""
    config = config or carregar_config()
    if config.modo_chat:
        return AgenteChat()
    return AgenteDemo() if config.modo_demo else AgenteClaude(config)
