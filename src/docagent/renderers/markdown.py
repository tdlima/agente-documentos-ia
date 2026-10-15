"""Exportação para Markdown."""

from __future__ import annotations

from ..models import Documento, Organizacao
from .tema import normalizar_tabela


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def para_markdown(doc: Documento, org: Organizacao | None = None) -> str:
    org = org or Organizacao()
    linhas: list[str] = []

    if org.nome:
        linhas.append(f"**{org.nome}**  ")
        linhas += [f"{linha}  " for linha in org.linhas_cabecalho()]
        linhas += ["", "---", ""]

    linhas.append(f"# {doc.titulo}")
    if doc.subtitulo:
        linhas += ["", f"*{doc.subtitulo}*"]
    if doc.metadados:
        linhas.append("")
        linhas += [f"**{m.rotulo}:** {m.valor}  " for m in doc.metadados]

    for b in doc.blocos:
        linhas.append("")
        if b.tipo == "titulo":
            linhas.append(f"## {b.texto}")
        elif b.tipo == "paragrafo":
            linhas.append(b.texto)
        elif b.tipo == "lista":
            linhas += [f"- {item}" for item in b.itens]
        elif b.tipo == "lista_numerada":
            linhas += [f"{i}. {item}" for i, item in enumerate(b.itens, 1)]
        elif b.tipo == "tabela":
            colunas = b.colunas or [""] * max((len(r) for r in b.linhas), default=1)
            linhas.append("| " + " | ".join(_celula(c) for c in colunas) + " |")
            linhas.append("|" + "|".join(" --- " for _ in colunas) + "|")
            for row in normalizar_tabela(colunas, b.linhas):
                linhas.append("| " + " | ".join(_celula(c) for c in row) + " |")
        elif b.tipo == "destaque":
            linhas += [f"> {parte}" for parte in b.texto.splitlines() or [""]]
        elif b.tipo == "assinatura":
            cargo = b.itens[0] if b.itens else ""
            linhas += ["", "______________________________________  ", f"**{b.texto}**  "]
            if cargo:
                linhas.append(cargo)

    return "\n".join(linhas).strip() + "\n"
