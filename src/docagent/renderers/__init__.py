"""Exportadores: transformam um `Documento` em Markdown, Word ou PDF.

Todos recebem a mesma estrutura genérica, por isso qualquer novo tipo de
documento ganha as três exportações automaticamente.
"""

from __future__ import annotations

from typing import Literal

from ..models import Documento, Organizacao
from .docx import para_docx
from .markdown import para_markdown
from .pdf import para_pdf

Formato = Literal["md", "docx", "pdf"]

MIME = {
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def exportar(doc: Documento, org: Organizacao | None, formato: Formato) -> bytes:
    org = org or Organizacao()
    if formato == "md":
        return para_markdown(doc, org).encode("utf-8")
    if formato == "docx":
        return para_docx(doc, org)
    if formato == "pdf":
        return para_pdf(doc, org)
    raise ValueError(f"Formato não suportado: {formato}")


__all__ = ["MIME", "Formato", "exportar", "para_docx", "para_markdown", "para_pdf"]
