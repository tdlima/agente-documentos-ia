"""Identidade visual compartilhada pelos exportadores e utilitários de texto."""

from __future__ import annotations

import re

# Paleta "Marinho & Latão"
MARINHO = "1F2A44"
LATAO = "B08D57"
TEXTO = "222222"
CINZA = "6B7280"
FUNDO_DESTAQUE = "F5EFE4"

_NEGRITO = re.compile(r"\*\*(.+?)\*\*")


def segmentos(texto: str) -> list[tuple[str, bool]]:
    """Divide um texto com **negrito** em trechos (texto, é_negrito)."""
    partes: list[tuple[str, bool]] = []
    pos = 0
    for m in _NEGRITO.finditer(texto):
        if m.start() > pos:
            partes.append((texto[pos : m.start()], False))
        partes.append((m.group(1), True))
        pos = m.end()
    if pos < len(texto):
        partes.append((texto[pos:], False))
    return partes or [("", False)]


def sem_marcacao(texto: str) -> str:
    return _NEGRITO.sub(r"\1", texto)


_MOEDA = re.compile(r"(R\$|US\$|€)\s+(?=[\d−-])")


def nao_quebrar(texto: str) -> str:
    """Impede a quebra de linha entre o símbolo da moeda e o valor (R$ 1.000)."""
    return _MOEDA.sub(lambda m: m.group(1) + "\u00a0", texto)


def normalizar_tabela(colunas: list[str], linhas: list[list[str]]) -> list[list[str]]:
    """Garante que todas as linhas tenham o mesmo número de células do cabeçalho."""
    n = len(colunas) or max((len(linha) for linha in linhas), default=0)
    return [[nao_quebrar(c) for c in (list(linha) + [""] * n)[:n]] for linha in linhas]


def larguras_colunas(
    colunas: list[str],
    linhas: list[list[str]],
    total: float,
    medir,
    padding: float,
) -> list[float]:
    """Calcula larguras absolutas de colunas de tabela.

    - A largura *preferida* é proporcional ao tamanho médio do conteúdo.
    - A largura *mínima* garante que a maior palavra de cada coluna caiba
      sem ser quebrada no meio. `medir(texto, negrito)` devolve a largura
      do texto na unidade de `total`.
    """
    n = len(colunas) or max((len(linha) for linha in linhas), default=0)
    if n == 0:
        return []
    preferidas, minimos = [], []
    for i in range(n):
        cab = colunas[i] if i < len(colunas) else ""
        celulas = [linha[i] for linha in linhas if i < len(linha)]
        media = sum(len(c) for c in celulas) / len(celulas) if celulas else 0
        preferidas.append(min(max(len(cab), media), 45) + 3)
        palavras = [(p, True) for p in cab.split(" ")] + [(p, False) for c in celulas for p in c.split(" ")]
        minimos.append(max((medir(p, b) for p, b in palavras), default=0) + padding)

    if sum(minimos) >= total:  # conteúdo muito largo: divide proporcionalmente aos mínimos
        return [total * m / sum(minimos) for m in minimos]

    soma = sum(preferidas)
    larguras = [total * p / soma for p in preferidas]
    # garante os mínimos, tirando espaço das colunas que têm folga
    for _ in range(n):
        deficit = sum(m - w for w, m in zip(larguras, minimos) if w < m)
        if deficit <= 1e-6:
            break
        folga = {i: w - m for i, (w, m) in enumerate(zip(larguras, minimos)) if w > m}
        total_folga = sum(folga.values())
        larguras = [max(w, m) for w, m in zip(larguras, minimos)]
        for i, f in folga.items():
            larguras[i] -= deficit * f / total_folga
    return larguras


def agrupar_assinaturas(blocos):
    """Agrupa assinaturas consecutivas (para exibi-las lado a lado, 2 por linha).

    Produz itens que são um `Bloco` comum ou uma lista de blocos 'assinatura'.
    """
    grupo = []
    for b in blocos:
        if b.tipo == "assinatura":
            grupo.append(b)
            continue
        if grupo:
            yield grupo
            grupo = []
        yield b
    if grupo:
        yield grupo
