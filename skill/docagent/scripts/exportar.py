"""Valida um documento em JSON e o exporta para Word, PDF e/ou Markdown.

Uso:
    python scripts/exportar.py documento.json \\
        [--org organizacao.json] [--logo logo.png] \\
        [--formatos docx pdf md] [--saida PASTA] [--nome NOME_DO_ARQUIVO]

O JSON segue o formato descrito em referencias/formato_documento.md. Campos
vazios podem ser omitidos (subtitulo, metadados, pendencias e, em cada bloco,
texto/itens/colunas/linhas): o script completa com valores vazios.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import ValidationError  # noqa: E402

from docagent.models import Documento, Organizacao  # noqa: E402
from docagent.renderers import exportar  # noqa: E402
from docagent.utils import slug  # noqa: E402

PADROES_DOC = {"subtitulo": "", "metadados": [], "pendencias": []}
PADROES_BLOCO = {"texto": "", "itens": [], "colunas": [], "linhas": []}


def completar(dados: dict) -> dict:
    """Preenche campos opcionais omitidos com valores vazios."""
    for chave, valor in PADROES_DOC.items():
        dados.setdefault(chave, valor)
    for bloco in dados.get("blocos", []):
        if isinstance(bloco, dict):
            for chave, valor in PADROES_BLOCO.items():
                bloco.setdefault(chave, valor)
    return dados


def carregar_documento(caminho: Path) -> Documento:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"ERRO: JSON inválido em {caminho} (linha {exc.lineno}, coluna {exc.colno}): {exc.msg}")
    try:
        return Documento.model_validate(completar(dados))
    except ValidationError as exc:
        linhas = [f"ERRO: o documento não segue o formato esperado ({exc.error_count()} problema(s)):"]
        for erro in exc.errors():
            local = ".".join(str(p) for p in erro["loc"])
            linhas.append(f"  - {local}: {erro['msg']}")
        linhas.append("Consulte referencias/formato_documento.md, corrija o JSON e rode novamente.")
        sys.exit("\n".join(linhas))


def carregar_org(caminho: Path | None, logo: Path | None) -> Organizacao:
    dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho else {}
    campos = set(Organizacao.model_fields) - {"logo"}
    org = Organizacao(**{k: str(v) for k, v in dados.items() if k in campos and v})
    if logo:
        org.logo = logo.read_bytes()
    return org


def avisos(doc: Documento) -> list[str]:
    """Verificações de qualidade que não impedem a exportação."""
    msgs = []
    for i, b in enumerate(doc.blocos):
        if b.tipo == "tabela":
            n = len(b.colunas)
            if any(len(linha) != n for linha in b.linhas):
                msgs.append(f"bloco {i} (tabela): linhas com nº de células diferente das colunas")
        if b.tipo in ("lista", "lista_numerada") and not b.itens:
            msgs.append(f"bloco {i} ({b.tipo}): lista sem itens")
        if b.tipo in ("titulo", "paragrafo", "destaque", "assinatura") and not b.texto.strip():
            msgs.append(f"bloco {i} ({b.tipo}): texto vazio")
    return msgs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("documento", type=Path)
    parser.add_argument("--org", type=Path, help="JSON com os dados da organização")
    parser.add_argument("--logo", type=Path, help="imagem PNG/JPG do logo")
    parser.add_argument("--formatos", nargs="+", default=["docx", "pdf"], choices=["docx", "pdf", "md"])
    parser.add_argument("--saida", type=Path, default=Path("."), help="pasta de saída")
    parser.add_argument("--nome", help="nome base dos arquivos (padrão: derivado do título)")
    args = parser.parse_args()

    doc = carregar_documento(args.documento)
    org = carregar_org(args.org, args.logo)
    args.saida.mkdir(parents=True, exist_ok=True)
    nome = slug(args.nome or doc.titulo)

    for formato in args.formatos:
        destino = args.saida / f"{nome}.{formato}"
        destino.write_bytes(exportar(doc, org, formato))
        print(f"OK  {destino}")

    for msg in avisos(doc):
        print(f"AVISO  {msg}")
    if doc.pendencias:
        print("\nPENDÊNCIAS PARA O USUÁRIO CONFERIR:")
        for p in doc.pendencias:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
