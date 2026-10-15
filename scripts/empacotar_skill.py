"""Monta a skill do DocAgent para uso dentro do Claude.

Junta `skill/docagent/` (SKILL.md, scripts e referências) com o pacote
`src/docagent` (modelos YAML e exportadores) — o código é o mesmo do app, sem
duplicação — e gera `dist/docagent.zip`, pronto para enviar em
Personalizar → Skills no Claude.

Uso:  python scripts/empacotar_skill.py
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "skill" / "docagent"
PACOTE = RAIZ / "src" / "docagent"
DIST = RAIZ / "dist"

sys.path.insert(0, str(RAIZ / "src"))
from docagent.prompts import SISTEMA  # noqa: E402

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc")


def validar_frontmatter(skill_md: Path) -> None:
    texto = skill_md.read_text("utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        raise SystemExit("SKILL.md sem frontmatter YAML")
    campos = dict(linha.split(":", 1) for linha in m.group(1).splitlines() if ":" in linha)
    nome, descricao = campos.get("name", "").strip(), campos.get("description", "").strip()
    if nome != ORIGEM.name or len(nome) > 64:
        raise SystemExit(f"'name' deve ser '{ORIGEM.name}' (até 64 caracteres)")
    if not descricao or len(descricao) > 200:
        raise SystemExit(f"'description' deve ter até 200 caracteres (tem {len(descricao)})")


def montar(destino_base: Path = DIST) -> Path:
    """Monta a pasta da skill e devolve o caminho do ZIP gerado."""
    validar_frontmatter(ORIGEM / "SKILL.md")
    pasta = destino_base / ORIGEM.name
    if pasta.exists():
        shutil.rmtree(pasta)
    shutil.copytree(ORIGEM, pasta, ignore=IGNORAR)
    shutil.copytree(PACOTE, pasta / "scripts" / "docagent", ignore=IGNORAR)
    (pasta / "referencias" / "regras_de_redacao.md").write_text(
        "# Regras de redação do DocAgent\n\n"
        "Mesmas regras usadas pelo agente no aplicativo (src/docagent/prompts.py).\n\n" + SISTEMA,
        encoding="utf-8",
    )

    arquivo_zip = destino_base / f"{ORIGEM.name}.zip"
    with zipfile.ZipFile(arquivo_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for caminho in sorted(pasta.rglob("*")):
            if caminho.is_file():
                z.write(caminho, caminho.relative_to(destino_base))
    return arquivo_zip


if __name__ == "__main__":
    zip_gerado = montar()
    with zipfile.ZipFile(zip_gerado) as z:
        print(f"{zip_gerado.relative_to(RAIZ)}: {len(z.namelist())} arquivos")
