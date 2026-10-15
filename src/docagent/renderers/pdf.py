"""Exportação para PDF com ReportLab."""

from __future__ import annotations

import platform
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Bloco, Documento, Organizacao
from .tema import (
    CINZA,
    FUNDO_DESTAQUE,
    LATAO,
    MARINHO,
    TEXTO,
    agrupar_assinaturas,
    larguras_colunas,
    normalizar_tabela,
    segmentos,
)

C_MARINHO = colors.HexColor(f"#{MARINHO}")
C_LATAO = colors.HexColor(f"#{LATAO}")
C_TEXTO = colors.HexColor(f"#{TEXTO}")
C_CINZA = colors.HexColor(f"#{CINZA}")
C_FUNDO = colors.HexColor(f"#{FUNDO_DESTAQUE}")

MARGEM = 2.2 * cm
ALTURA_CABECALHO = 3.0 * cm

# Fontes TrueType procuradas no sistema (suportam acentos e símbolos Unicode).
_CANDIDATAS = {
    "Linux": [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ),
    ],
    "Windows": [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ],
    "Darwin": [
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ],
}


@lru_cache(maxsize=1)
def _fontes() -> tuple[str, str, bool]:
    """Retorna (regular, negrito, unicode). Usa Helvetica se nada for encontrado."""
    for regular, negrito in _CANDIDATAS.get(platform.system(), []):
        if Path(regular).exists() and Path(negrito).exists():
            pdfmetrics.registerFont(TTFont("DocAgent", regular))
            pdfmetrics.registerFont(TTFont("DocAgent-Bold", negrito))
            pdfmetrics.registerFontFamily(
                "DocAgent",
                normal="DocAgent",
                bold="DocAgent-Bold",
                italic="DocAgent",
                boldItalic="DocAgent-Bold",
            )
            return "DocAgent", "DocAgent-Bold", True
    return "Helvetica", "Helvetica-Bold", False


_SUBSTITUICOES = {
    "→": "->",
    "←": "<-",
    "≥": ">=",
    "≤": "<=",
    "✓": "OK",
    "✔": "OK",
    "✗": "x",
    "≈": "~",
    "−": "-",
}


def _seguro(texto: str) -> str:
    """Com Helvetica (cp1252), troca caracteres que não seriam exibidos."""
    if _fontes()[2]:
        return texto
    for de, para in _SUBSTITUICOES.items():
        texto = texto.replace(de, para)
    return texto.encode("cp1252", "replace").decode("cp1252")


def _rich(texto: str) -> str:
    """Converte **negrito** para a marcação do ReportLab, escapando o resto."""
    partes = []
    for trecho, negrito in segmentos(_seguro(texto)):
        seguro = escape(trecho).replace("\n", "<br/>")
        partes.append(f"<b>{seguro}</b>" if negrito else seguro)
    return "".join(partes)


def _estilos() -> dict[str, ParagraphStyle]:
    regular, negrito, _ = _fontes()
    base = ParagraphStyle("base", fontName=regular, fontSize=10.5, leading=15, textColor=C_TEXTO)
    return {
        "corpo": ParagraphStyle("corpo", parent=base, alignment=TA_JUSTIFY, spaceAfter=7),
        "titulo": ParagraphStyle(
            "titulo",
            parent=base,
            fontName=negrito,
            fontSize=19,
            leading=24,
            textColor=C_MARINHO,
            spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle("subtitulo", parent=base, textColor=C_CINZA, spaceAfter=8),
        "meta": ParagraphStyle("meta", parent=base, spaceAfter=1),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName=negrito,
            fontSize=12.5,
            leading=17,
            textColor=C_MARINHO,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "item": ParagraphStyle("item", parent=base, spaceAfter=2),
        "celula": ParagraphStyle("celula", parent=base, fontSize=9, leading=12),
        "celula_cab": ParagraphStyle(
            "celula_cab", parent=base, fontName=negrito, fontSize=9, leading=12, textColor=colors.white
        ),
        "destaque": ParagraphStyle("destaque", parent=base),
        "assin_nome": ParagraphStyle(
            "assin_nome", parent=base, fontName=negrito, alignment=TA_CENTER, spaceAfter=0
        ),
        "assin_cargo": ParagraphStyle("assin_cargo", parent=base, alignment=TA_CENTER, textColor=C_CINZA),
    }


class _CanvasNumerado(rl_canvas.Canvas):
    """Canvas que escreve 'Página X de Y' no rodapé (exige duas passagens)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas: list[dict] = []

    def showPage(self):  # noqa: N802 (API do ReportLab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont(_fontes()[0], 8)
            self.setFillColor(C_CINZA)
            self.drawRightString(A4[0] - MARGEM, 1.2 * cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _desenhar_cabecalho(org: Organizacao):
    regular, negrito, _ = _fontes()

    def desenhar(c: rl_canvas.Canvas, _doc) -> None:
        if not (org.nome or org.logo):
            return
        c.saveState()
        topo = A4[1] - 1.2 * cm
        x = MARGEM
        if org.logo:
            try:
                img = ImageReader(BytesIO(org.logo))
                largura, altura = img.getSize()
                h = 1.3 * cm
                w = h * largura / altura
                c.drawImage(img, x, topo - h, width=w, height=h, mask="auto")
                x += w + 0.4 * cm
            except Exception:  # imagem inválida: segue sem logo
                pass
        c.setFillColor(C_MARINHO)
        c.setFont(negrito, 11.5)
        c.drawString(x, topo - 0.45 * cm, _seguro(org.nome))
        c.setFont(regular, 7.5)
        c.setFillColor(C_CINZA)
        for i, linha in enumerate(org.linhas_cabecalho()[:3]):
            c.drawString(x, topo - 0.85 * cm - i * 0.32 * cm, _seguro(linha))
        c.setStrokeColor(C_LATAO)
        c.setLineWidth(0.8)
        y = A4[1] - ALTURA_CABECALHO + 0.1 * cm
        c.line(MARGEM, y, A4[0] - MARGEM, y)
        c.restoreState()

    return desenhar


def _tabela(b: Bloco, est: dict, largura: float) -> Table | None:
    colunas = b.colunas
    linhas = normalizar_tabela(colunas, b.linhas)
    n = len(colunas) or (len(linhas[0]) if linhas else 0)
    if n == 0:
        return None
    dados = []
    if colunas:
        dados.append([Paragraph(_rich(c), est["celula_cab"]) for c in colunas])
    dados += [[Paragraph(_rich(c), est["celula"]) for c in linha] for linha in linhas]
    regular, negrito, _ = _fontes()

    def medir(texto: str, em_negrito: bool) -> float:
        return pdfmetrics.stringWidth(_seguro(texto), negrito if em_negrito else regular, 9)

    larguras = larguras_colunas(colunas, linhas, largura, medir, padding=13)
    t = Table(dados, colWidths=larguras, repeatRows=1 if colunas else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if colunas:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), C_MARINHO))
    inicio = 1 if colunas else 0
    for i in range(inicio, len(dados)):
        if (i - inicio) % 2:
            estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F4F6")))
    t.setStyle(TableStyle(estilo))
    return t


def _assinaturas(blocos: list[Bloco], est: dict, largura: float) -> KeepTogether:
    """Assinaturas lado a lado, duas por linha."""
    linha_estilo = ParagraphStyle("linha", parent=est["assin_nome"], fontName=_fontes()[0])

    def celula(b: Bloco) -> list:
        partes = [Paragraph("_" * 38, linha_estilo), Paragraph(_rich(b.texto), est["assin_nome"])]
        if b.itens and b.itens[0]:
            partes.append(Paragraph(_rich(b.itens[0]), est["assin_cargo"]))
        return partes

    colunas = 1 if len(blocos) == 1 else 2
    linhas = [[celula(b) for b in blocos[i : i + colunas]] for i in range(0, len(blocos), colunas)]
    if len(linhas[-1]) < colunas:
        linhas[-1].append("")
    t = Table(linhas, colWidths=[largura / colunas] * colunas)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 30)]))
    return KeepTogether([Spacer(1, 12), t])


def para_pdf(doc: Documento, org: Organizacao | None = None) -> bytes:
    org = org or Organizacao()
    est = _estilos()
    buffer = BytesIO()
    tem_cabecalho = bool(org.nome or org.logo)
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGEM,
        rightMargin=MARGEM,
        topMargin=(ALTURA_CABECALHO + 0.6 * cm) if tem_cabecalho else MARGEM,
        bottomMargin=2 * cm,
        title=doc.titulo,
        author=org.nome or "DocAgent",
    )
    largura = A4[0] - 2 * MARGEM
    h: list = [Paragraph(_rich(doc.titulo), est["titulo"])]
    h.append(
        Table(
            [[""]], colWidths=[largura], rowHeights=[2], style=[("LINEBELOW", (0, 0), (-1, -1), 1.5, C_LATAO)]
        )
    )
    h.append(Spacer(1, 6))
    if doc.subtitulo:
        h.append(Paragraph(_rich(doc.subtitulo), est["subtitulo"]))
    for m in doc.metadados:
        h.append(
            Paragraph(
                f'<font color="#{MARINHO}"><b>{escape(_seguro(m.rotulo))}:</b></font> {_rich(m.valor)}',
                est["meta"],
            )
        )
    if doc.metadados:
        h.append(Spacer(1, 10))

    for b in agrupar_assinaturas(doc.blocos):
        if isinstance(b, list):
            h.append(_assinaturas(b, est, largura))
        elif b.tipo == "titulo":
            h.append(Paragraph(_rich(b.texto), est["h2"]))
        elif b.tipo == "paragrafo":
            for parte in [x for x in b.texto.split("\n") if x.strip()]:
                h.append(Paragraph(_rich(parte), est["corpo"]))
        elif b.tipo in ("lista", "lista_numerada"):
            numerada = b.tipo == "lista_numerada"
            h.append(
                ListFlowable(
                    [ListItem(Paragraph(_rich(i), est["item"]), leftIndent=16) for i in b.itens],
                    bulletType="1" if numerada else "bullet",
                    start=None if numerada else "•",
                    bulletColor=C_LATAO,
                    bulletFontName=_fontes()[1],
                    bulletFontSize=9,
                    leftIndent=16,
                )
            )
            h.append(Spacer(1, 6))
        elif b.tipo == "tabela":
            t = _tabela(b, est, largura)
            if t is not None:
                h += [t, Spacer(1, 10)]
        elif b.tipo == "destaque":
            caixa = Table([[Paragraph(_rich(b.texto), est["destaque"])]], colWidths=[largura])
            caixa.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), C_FUNDO),
                        ("LINEBEFORE", (0, 0), (0, -1), 3, C_LATAO),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            h += [caixa, Spacer(1, 10)]

    desenhar = _desenhar_cabecalho(org)
    pdf.build(h, onFirstPage=desenhar, onLaterPages=desenhar, canvasmaker=_CanvasNumerado)
    return buffer.getvalue()
