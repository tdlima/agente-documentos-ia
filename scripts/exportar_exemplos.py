"""Reexporta os exemplos de `exemplos/` para DOCX, PDF e Markdown.

Cada pasta contém a entrada do formulário (`entrada.json`), o prompt exato que o
agente envia ao modelo (`prompt.md`) e a resposta estruturada (`resposta.json`).

Uso:  python scripts/exportar_exemplos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from docagent.models import Documento, Organizacao  # noqa: E402
from docagent.renderers import exportar  # noqa: E402

EXEMPLOS = RAIZ / "exemplos"


def main() -> None:
    dados_org = json.loads((EXEMPLOS / "organizacao.json").read_text("utf-8"))
    org = Organizacao(**dados_org, logo=(EXEMPLOS / "logo_exemplo.png").read_bytes())
    for pasta in sorted(p for p in EXEMPLOS.iterdir() if p.is_dir()):
        resposta = pasta / "resposta_refinada.json"
        if not resposta.exists():
            resposta = pasta / "resposta.json"
        doc = Documento.model_validate_json(resposta.read_text("utf-8"))
        for formato in ("docx", "pdf", "md"):
            (pasta / f"{pasta.name}.{formato}").write_bytes(exportar(doc, org, formato))
        print(f"{pasta.name}: exportado a partir de {resposta.name}")


if __name__ == "__main__":
    main()
