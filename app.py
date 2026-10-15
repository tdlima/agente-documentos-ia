"""DocAgent — interface web (Streamlit).

Execute com:  streamlit run app.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from docagent.agent import (  # noqa: E402
    AgenteChat,
    ErroAgente,
    ErroRespostaChat,
    PedidoChat,
    Resultado,
    criar_agente,
)
from docagent.config import MODELOS_DISPONIVEIS, Config, carregar_config  # noqa: E402
from docagent.models import Campo, ModeloDocumento, Organizacao, Solicitacao  # noqa: E402
from docagent.registry import carregar_modelos  # noqa: E402
from docagent.renderers import MIME, exportar, para_markdown  # noqa: E402
from docagent.utils import slug  # noqa: E402

st.set_page_config(page_title="DocAgent · Documentos com IA", page_icon="📄", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Inter+Tight:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter Tight', sans-serif; }
    h1, h2, h3 { font-family: 'Instrument Serif', serif !important; font-weight: 400 !important; }
    .tag { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.8rem;
           background:#F1ECE3; color:#1F2A44; margin-right:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

CAMPOS_ORG = [
    ("nome", "Nome da organização"),
    ("cnpj", "CNPJ"),
    ("endereco", "Endereço"),
    ("cidade_uf", "Cidade/UF"),
    ("telefone", "Telefone"),
    ("email", "E-mail"),
    ("site", "Site"),
    ("responsavel", "Responsável (quem assina)"),
    ("cargo_responsavel", "Cargo do responsável"),
    ("segmento", "Segmento de atuação"),
]


# ---------------------------------------------------------------------------
# Barra lateral: configuração e perfil da organização
# ---------------------------------------------------------------------------


def barra_lateral() -> tuple[Config, Organizacao]:
    base = carregar_config()
    with st.sidebar:
        st.markdown("## ⚙️ Configuração")
        modo_chat = st.toggle(
            "Usar o chat do Claude (copiar e colar)",
            key="modo_chat",
            help="Sem API: o app gera o prompt para você colar no claude.ai e lê a resposta colada de volta.",
        )
        if modo_chat:
            config = Config(api_key=None, modelo=base.modelo, max_tokens=base.max_tokens, modo_chat=True)
            st.info(
                "**Modo chat** — copie o prompt gerado, cole em uma conversa no claude.ai "
                "e cole a resposta aqui. Use a mesma conversa para os ajustes."
            )
        else:
            chave = st.text_input(
                "Chave da API Anthropic",
                type="password",
                value="",
                placeholder="Usando ANTHROPIC_API_KEY" if base.api_key else "sk-ant-...",
                help="Opcional se a variável ANTHROPIC_API_KEY já estiver definida. "
                "A chave fica apenas nesta sessão.",
            )
            modelos = list(MODELOS_DISPONIVEIS)
            indice = modelos.index(base.modelo) if base.modelo in modelos else 0
            modelo = st.selectbox(
                "Modelo", modelos, index=indice, format_func=lambda m: MODELOS_DISPONIVEIS[m]
            )
            config = Config(api_key=chave or base.api_key, modelo=modelo, max_tokens=base.max_tokens)
            if config.modo_demo:
                st.info(
                    "**Modo demonstração** — sem chave de API, o documento é montado a partir dos "
                    "campos, sem IA. Ou ative o chat do Claude acima."
                )
            else:
                st.success("Claude conectado ✓")

        st.markdown("## 🏢 Sua organização")
        st.caption("Usado no cabeçalho dos arquivos e no contexto do agente.")

        perfil = st.file_uploader("Carregar perfil salvo (.json)", type=["json"], key="perfil_up")
        if perfil is not None and st.session_state.get("perfil_carregado") != perfil.file_id:
            dados = json.loads(perfil.getvalue().decode("utf-8"))
            for chave_org, _ in CAMPOS_ORG:
                st.session_state[f"org_{chave_org}"] = dados.get(chave_org, "")
            st.session_state["perfil_carregado"] = perfil.file_id

        with st.expander("Dados da organização", expanded=False):
            valores = {k: st.text_input(rotulo, key=f"org_{k}") for k, rotulo in CAMPOS_ORG}
            logo = st.file_uploader("Logo (PNG ou JPG)", type=["png", "jpg", "jpeg"])

        org = Organizacao(**valores, logo=logo.getvalue() if logo else None)
        st.download_button(
            "💾 Salvar perfil",
            data=json.dumps(org.model_dump(), ensure_ascii=False, indent=2),
            file_name="perfil_organizacao.json",
            mime="application/json",
            width="stretch",
            disabled=not org.nome,
        )
        st.markdown("---")
        st.caption(
            "DocAgent · feito com Claude · [código no GitHub](https://github.com/tdlima/agente-documentos-ia)"
        )
    return config, org


# ---------------------------------------------------------------------------
# Formulário dinâmico
# ---------------------------------------------------------------------------


def widget(modelo: ModeloDocumento, campo: Campo) -> str:
    chave = f"{modelo.id}__{campo.id}"
    rotulo = campo.rotulo + (" *" if campo.obrigatorio else "")
    ajuda = campo.ajuda or None
    exemplo = campo.exemplo.strip().splitlines()[0] if campo.exemplo.strip() else ""
    placeholder = f"Ex.: {exemplo}" if exemplo else None

    if campo.tipo == "selecao":
        indice = campo.opcoes.index(campo.padrao) if campo.padrao in campo.opcoes else 0
        return st.selectbox(rotulo, campo.opcoes, index=indice, key=chave, help=ajuda)
    if campo.tipo == "data":
        valor = st.date_input(rotulo, value=date.today(), key=chave, help=ajuda, format="DD/MM/YYYY")
        return valor.strftime("%d/%m/%Y") if valor else ""
    if campo.tipo in ("texto_longo", "lista"):
        placeholder = f"Ex.:\n{campo.exemplo.strip()}" if campo.exemplo.strip() else None
        return st.text_area(
            rotulo, value=campo.padrao, key=chave, help=ajuda, placeholder=placeholder, height=130
        )
    return st.text_input(rotulo, value=campo.padrao, key=chave, help=ajuda, placeholder=placeholder)


def formulario(modelo: ModeloDocumento) -> tuple[dict[str, str], str, str, bool]:
    with st.form(f"form_{modelo.id}"):
        curtos = [c for c in modelo.campos if c.tipo not in ("texto_longo", "lista")]
        longos = [c for c in modelo.campos if c.tipo in ("texto_longo", "lista")]
        valores: dict[str, str] = {}
        colunas = st.columns(2)
        for i, campo in enumerate(curtos):
            with colunas[i % 2]:
                valores[campo.id] = widget(modelo, campo)
        for campo in longos:
            valores[campo.id] = widget(modelo, campo)

        with st.expander("Opções avançadas"):
            tom = st.text_input("Tom de voz", value=modelo.tom_padrao, key=f"{modelo.id}__tom")
            extras = st.text_area(
                "Instruções adicionais para o agente",
                key=f"{modelo.id}__extras",
                placeholder="Ex.: limite a uma página; cite a Lei nº 8.742/1993; use linguagem simples.",
            )
        enviado = st.form_submit_button("✨ Gerar documento", type="primary", width="stretch")
    return valores, tom, extras, enviado


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


def painel_chat(pedido: PedidoChat) -> None:
    """Copiar o prompt para o claude.ai e colar a resposta de volta."""
    with st.container(border=True):
        ajuste = pedido.versao > 1
        st.markdown("### 💬 " + ("Ajuste pelo chat do Claude" if ajuste else "Redigir pelo chat do Claude"))
        st.markdown(
            "**1.** Copie o texto abaixo (ícone no canto do quadro) e cole "
            + ("na mesma conversa do claude.ai." if ajuste else "em uma conversa nova do claude.ai.")
        )
        st.code(pedido.prompt, language="markdown", height=260, wrap_lines=True)
        st.link_button("Abrir o claude.ai ↗", "https://claude.ai/new")

        st.markdown("**2.** Cole aqui a resposta do Claude (o bloco JSON).")
        with st.form(f"resposta_chat_{pedido.versao}"):
            resposta = st.text_area(
                "Resposta do Claude",
                key=f"resposta_chat_{pedido.versao}",
                height=180,
                label_visibility="collapsed",
                placeholder='```json\n{"titulo": ...}\n```',
            )
            col_ok, col_cancelar = st.columns([3, 2])
            enviado = col_ok.form_submit_button("📥 Ler resposta", type="primary", width="stretch")
            cancelado = col_cancelar.form_submit_button("Cancelar", width="stretch")

    if cancelado:
        st.session_state.pedido_chat = None
        st.rerun()
    if enviado:
        try:
            st.session_state.resultado = AgenteChat().concluir(pedido, resposta)
            st.session_state.pedido_chat = None
            st.rerun()
        except ErroRespostaChat as exc:
            st.error(str(exc))
            st.markdown("Cole esta mensagem na mesma conversa para o Claude corrigir:")
            st.code(exc.correcao, language="markdown", wrap_lines=True)
        except ErroAgente as exc:
            st.error(str(exc))


def mostrar_resultado(resultado: Resultado, org: Organizacao, config: Config) -> None:
    doc = resultado.documento
    st.markdown("### Documento gerado")
    info = [f"<span class='tag'>versão {resultado.versao}</span>"]
    if resultado.uso.tokens_entrada:
        info.append(
            f"<span class='tag'>{resultado.uso.tokens_entrada + resultado.uso.tokens_saida:,} "
            "tokens</span>".replace(",", ".")
        )
    st.markdown(" ".join(info), unsafe_allow_html=True)

    if doc.pendencias:
        with st.container(border=True):
            st.markdown("**⚠️ Confira antes de usar**")
            for p in doc.pendencias:
                st.markdown(f"- {p}")

    aba_previa, aba_md = st.tabs(["👁️ Prévia", "📝 Markdown"])
    markdown = para_markdown(doc, org)
    with aba_previa, st.container(border=True):
        # reduz os títulos para a prévia não competir com a página
        st.markdown(re.sub(r"^(#{1,2}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", markdown, flags=re.M))
    with aba_md:
        st.code(markdown, language="markdown")

    st.markdown("#### Baixar")
    nome = slug(doc.titulo)
    colunas = st.columns(3)
    for coluna, (formato, rotulo) in zip(
        colunas, [("docx", "📘 Word (.docx)"), ("pdf", "📕 PDF"), ("md", "📄 Markdown")]
    ):
        with coluna:
            st.download_button(
                rotulo,
                data=exportar(doc, org, formato),
                file_name=f"{nome}.{formato}",
                mime=MIME[formato],
                width="stretch",
                key=f"dl_{formato}_{resultado.versao}",
            )

    st.markdown("#### Refinar com o agente")
    with st.form("refinar", clear_on_submit=True):
        pedido = st.text_area(
            "O que deseja ajustar?",
            placeholder="Ex.: deixe mais curto; troque o tom para mais cordial; "
            "acrescente uma tabela com o cronograma.",
            height=90,
        )
        if st.form_submit_button("🔁 Aplicar ajuste", width="stretch"):
            try:
                agente = criar_agente(config)
                if isinstance(agente, AgenteChat):
                    st.session_state.pedido_chat = agente.preparar_refinamento(resultado, pedido)
                else:
                    with st.spinner("O agente está revisando o documento..."):
                        st.session_state.resultado = agente.refinar(resultado, pedido)
                st.rerun()
            except ErroAgente as exc:
                st.error(str(exc))


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


def main() -> None:
    config, org = barra_lateral()
    modelos = carregar_modelos()

    st.markdown("# DocAgent")
    st.markdown(
        "Descreva o que precisa em poucas linhas — o agente redige o documento "
        "completo, pronto para baixar em **Word, PDF ou Markdown**."
    )

    ids = list(modelos)
    escolhido = st.radio(
        "Tipo de documento",
        ids,
        format_func=lambda i: f"{modelos[i].icone} {modelos[i].nome.split(' –')[0]}",
        horizontal=True,
        key="tipo_documento",
    )
    modelo = modelos[escolhido]
    if st.session_state.get("modelo_atual") != modelo.id:
        st.session_state.modelo_atual = modelo.id
        st.session_state.resultado = None
        st.session_state.pedido_chat = None

    st.caption(f"**{modelo.nome}** · {modelo.categoria} — {modelo.descricao}")

    esquerda, direita = st.columns([5, 6], gap="large")
    with esquerda:
        valores, tom, extras, enviado = formulario(modelo)
        if enviado:
            solicitacao = Solicitacao(
                modelo=modelo, valores=valores, organizacao=org, tom=tom, instrucoes_extras=extras
            )
            try:
                agente = criar_agente(config)
                if isinstance(agente, AgenteChat):
                    st.session_state.pedido_chat = agente.preparar(solicitacao)
                    st.session_state.resultado = None
                else:
                    with st.spinner("O agente está redigindo seu documento..."):
                        st.session_state.resultado = agente.redigir(solicitacao)
                    st.session_state.pedido_chat = None
            except ErroAgente as exc:
                st.error(str(exc))

    with direita:
        resultado: Resultado | None = st.session_state.get("resultado")
        pedido: PedidoChat | None = st.session_state.get("pedido_chat") if config.modo_chat else None
        if pedido is not None:
            painel_chat(pedido)
        if resultado is not None:
            mostrar_resultado(resultado, org, config)
        elif pedido is None:
            with st.container(border=True):
                st.markdown("#### Como funciona")
                st.markdown(
                    "1. Preencha o perfil da sua organização na barra lateral (uma vez).\n"
                    "2. Escolha o tipo de documento e preencha os campos — tópicos bastam.\n"
                    "3. O agente redige seguindo a estrutura e as boas práticas do documento.\n"
                    "4. Revise a prévia, peça ajustes e baixe o arquivo."
                )
                st.markdown("**Estrutura que será seguida:**")
                st.markdown("\n".join(f"- {s}" for s in modelo.estrutura))


main()
