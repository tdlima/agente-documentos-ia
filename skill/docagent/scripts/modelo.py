"""Mostra os modelos de documento disponíveis e o guia de redação de cada um.

Uso:
    python scripts/modelo.py --listar
    python scripts/modelo.py oficio
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docagent.registry import carregar_modelos, obter_modelo  # noqa: E402


def listar() -> None:
    for m in carregar_modelos().values():
        print(f"{m.id:<22} {m.nome} — {m.descricao}")


def guia(modelo_id: str) -> None:
    m = obter_modelo(modelo_id)
    print(f"# {m.nome}  (id: {m.id})\n")
    print(f"{m.descricao}\n")
    print(f"Tom padrão: {m.tom_padrao}\n")
    print("## Informações que o usuário deve fornecer  (* = obrigatória)")
    for c in m.campos:
        marca = " *" if c.obrigatorio else ""
        extra = []
        if c.opcoes:
            extra.append("opções: " + " | ".join(c.opcoes))
        if c.padrao:
            extra.append(f"padrão: {c.padrao}")
        if c.ajuda:
            extra.append(c.ajuda)
        sufixo = f"  ({'; '.join(extra)})" if extra else ""
        print(f"- {c.rotulo}{marca}{sufixo}")
    print("\n## Estrutura esperada")
    for i, secao in enumerate(m.estrutura, 1):
        print(f"{i}. {secao}")
    print("\n## Instruções específicas")
    print(m.instrucoes.strip())


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("modelo", nargs="?", help="id do modelo (ex.: oficio, pdi)")
    parser.add_argument("--listar", action="store_true", help="lista os modelos disponíveis")
    args = parser.parse_args()
    if args.listar or not args.modelo:
        listar()
    else:
        try:
            guia(args.modelo)
        except KeyError as exc:
            sys.exit(str(exc))


if __name__ == "__main__":
    main()
