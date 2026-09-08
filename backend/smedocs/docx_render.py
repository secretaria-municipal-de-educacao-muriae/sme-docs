"""Saida em .docx, para quando o material ainda precisa de ajuste manual.

O PDF e o entregavel final e reproduz o template. Este modulo produz a versao de
trabalho: mesmo conteudo, aberto para edicao no Word.

A diferenca que importa e que aqui tudo sai com **estilo nomeado**, nao com formatacao
direta. Para mudar o corpo do texto da apostila inteira basta editar o estilo "SME
Enunciado" uma vez, em vez de selecionar 800 paragrafos.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from . import docx_fonts
from .models import Descriptor, Fragment

# Mesmos tokens do template. Ver CLAUDE.md.
AZUL = RGBColor(0x1B, 0x56, 0xC4)
AZUL_ESCURO = RGBColor(0x12, 0x3E, 0x8F)
VERMELHO = RGBColor(0xE6, 0x39, 0x46)
VERDE = RGBColor(0x3F, 0xA3, 0x4D)
AMARELO = RGBColor(0xF4, 0xC4, 0x30)
TEXTO = RGBColor(0x23, 0x23, 0x23)
TEXTO_SUAVE = RGBColor(0x5B, 0x5B, 0x5B)

FUNDO_NEUTRO = "F5F5F3"
FUNDO_CORRETA = "EAF7EC"
FUNDO_CHIP = "1B56C4"
FUNDO_ORIGEM = "EFEFEC"

# As duas familias do template. Nao ha fallback aqui de proposito: elas vao embutidas
# no proprio .docx por docx_fonts, entao existem em qualquer maquina que abrir.
FONTE_TITULO = "Baloo 2"
FONTE_CORPO = "Nunito"


def _shade_run(run, fill: str) -> None:
    """Fundo colorido atras do texto. E o que faz o numero da questao virar balao."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    run._r.get_or_add_rPr().append(shd)


def _regua(document: Document, capa: bool = False):
    """A regua de quatro cores, assinatura visual do template."""
    paragraph = document.add_paragraph(style="SME Regua Capa" if capa else "SME Regua")
    for cor, forma in (
        (AZUL, "▬▬"), (AMARELO, "■"), (VERMELHO, "●"),
        (VERDE, "▬▬"), (AMARELO, "■"), (AZUL, "●"),
    ):
        run = paragraph.add_run(forma + " ")
        run.font.color.rgb = cor
        run.font.size = Pt(11)
    return paragraph


def _shade(paragraph, fill: str) -> None:
    """Fundo colorido de paragrafo. Nao ha API no python-docx, so o XML."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    paragraph._p.get_or_add_pPr().append(shd)


def _build_styles(document: Document) -> None:
    titulo_font, corpo_font = FONTE_TITULO, FONTE_CORPO

    normal = document.styles["Normal"]
    normal.font.name = corpo_font
    normal.font.size = Pt(11)
    normal.font.color.rgb = TEXTO
    normal.paragraph_format.line_spacing = 1.35

    def add(name: str, size: float, *, font=None, color=None, bold=False,
            space_before=0, space_after=6, italic=False, align=None,
            line_spacing=1.35):
        style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = document.styles["Normal"]
        style.font.name = font or corpo_font
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.italic = italic
        style.font.color.rgb = color or TEXTO
        fmt = style.paragraph_format
        fmt.space_before = Pt(space_before)
        fmt.space_after = Pt(space_after)
        # Baloo 2 tem metrica alta: sem entrelinha explicita o titulo abre um vao
        # enorme entre as linhas e nao lembra em nada o PDF.
        fmt.line_spacing = line_spacing
        if align is not None:
            fmt.alignment = align
        return style

    add("SME Sobretitulo", 12, font=titulo_font, color=VERMELHO, bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8, line_spacing=Pt(15))
    add("SME Capa Titulo", 34, font=titulo_font, color=AZUL_ESCURO, bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10, line_spacing=Pt(38))
    add("SME Capa Subtitulo", 15, font=titulo_font, bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, line_spacing=Pt(19))
    add("SME Capa Legenda", 11, color=TEXTO_SUAVE,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)

    add("SME Chip", 9, font=titulo_font, color=AZUL, bold=True, space_after=2)
    add("SME Descritor", 18, font=titulo_font, color=AZUL_ESCURO, bold=True,
        space_after=8, line_spacing=Pt(22))
    add("SME Secao", 14, font=titulo_font, color=AZUL_ESCURO, bold=True,
        space_before=14, space_after=6, line_spacing=Pt(17))

    intro = add("SME Intro", 10, space_after=4)
    intro.paragraph_format.left_indent = Mm(4)
    intro.paragraph_format.right_indent = Mm(4)

    enunciado = add("SME Enunciado", 11, space_after=4,
                    align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    enunciado.paragraph_format.left_indent = Mm(8)

    numero = add("SME Questao Numero", 11, font=titulo_font, color=AZUL, bold=True,
                 space_before=10, space_after=2)

    origem = add("SME Origem", 8, color=TEXTO_SUAVE, bold=True, space_after=2)
    origem.paragraph_format.left_indent = Mm(8)

    credito = add("SME Credito", 8, color=TEXTO_SUAVE, space_after=6,
                  align=WD_ALIGN_PARAGRAPH.RIGHT)
    credito.paragraph_format.left_indent = Mm(8)

    figura = add("SME Figura", 11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)

    alt = add("SME Alternativa", 11, space_after=1)
    alt.paragraph_format.left_indent = Mm(12)

    correta = add("SME Alternativa Correta", 11, space_after=1)
    correta.paragraph_format.left_indent = Mm(12)

    add("SME Pendencia", 8, color=VERMELHO, bold=True, space_after=4)
    add("SME Regua", 11, space_after=10, line_spacing=Pt(12))
    add("SME Regua Capa", 11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24,
        space_before=24, line_spacing=Pt(12))
    add("SME Espaco", 11, space_after=0)

    # Silencia o aviso do linter sobre variaveis nao usadas; elas existem pelo efeito.
    del numero, figura, correta, credito, origem


def _page_setup(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Mm(14))


def _emit(paragraph, fragments: list[Fragment], assets_dir: Path) -> None:
    """Escreve texto e imagens de um paragrafo, na ordem original."""
    for fragment in fragments:
        if fragment.kind == "text":
            if fragment.text:
                paragraph.add_run(fragment.text)
        elif fragment.kind == "image" and fragment.asset:
            path = assets_dir / fragment.asset
            if not path.exists():
                continue
            run = paragraph.add_run()
            try:
                run.add_picture(str(path), height=Pt(fragment.height_pt))
            except Exception:
                continue


def _emit_figure(document: Document, fragment: Fragment, assets_dir: Path) -> None:
    path = assets_dir / (fragment.asset or "")
    if not path.exists():
        return
    paragraph = document.add_paragraph(style="SME Figura")
    run = paragraph.add_run()
    # A largura util da pagina e 210mm menos as duas margens de 14mm.
    largura = min(fragment.width_pt, 182 * 72 / 25.4)
    try:
        run.add_picture(str(path), width=Pt(largura))
    except Exception:
        pass


def render_docx(
    descriptors: list[Descriptor],
    out_path: Path,
    assets_dir: Path,
    titulo: str = "Banco de Questões por Descritor",
    sobretitulo: str = "Recomposição das Aprendizagens",
    subtitulo: str = "Matemática — 6º ao 9º Ano",
    legenda: str = "",
    mostrar_gabarito: bool = True,
) -> Path:
    document = Document()
    _page_setup(document)
    _build_styles(document)

    for _ in range(6):
        document.add_paragraph(style="SME Espaco")
    _regua(document, capa=True)
    document.add_paragraph(sobretitulo.upper(), style="SME Sobretitulo")
    document.add_paragraph(titulo, style="SME Capa Titulo")
    document.add_paragraph(subtitulo, style="SME Capa Subtitulo")
    if legenda:
        document.add_paragraph(legenda, style="SME Capa Legenda")
    _regua(document, capa=True)
    document.add_page_break()

    for position, descriptor in enumerate(descriptors):
        if position:
            document.add_page_break()

        chip = document.add_paragraph(style="SME Chip")
        marca = chip.add_run(f"  DESCRITOR {descriptor.number}  ")
        marca.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade_run(marca, FUNDO_CHIP)
        document.add_paragraph(descriptor.title, style="SME Descritor")
        _regua(document)

        intro_paragraphs: list[list[Fragment]] = [[]]
        for fragment in descriptor.intro:
            if fragment.kind == "text" and fragment.text == "\n":
                intro_paragraphs.append([])
            else:
                intro_paragraphs[-1].append(fragment)
        for group in intro_paragraphs:
            if not any(f.text.strip() or f.kind == "image" for f in group):
                continue
            paragraph = document.add_paragraph(style="SME Intro")
            _emit(paragraph, group, assets_dir)
            _shade(paragraph, FUNDO_NEUTRO)

        document.add_paragraph(
            f"Atividades do descritor {descriptor.number}", style="SME Secao"
        )

        for index, question in enumerate(descriptor.questions, start=1):
            # Numero e origem dividem a mesma linha: em duas, cada questao gastava um
            # paragrafo a mais e a apostila crescia varias paginas sem ganhar nada.
            cabecalho = document.add_paragraph(style="SME Questao Numero")
            balao = cabecalho.add_run(f" {index} ")
            balao.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _shade_run(balao, FUNDO_CHIP)
            if question.source:
                cabecalho.add_run("  ")
                origem = cabecalho.add_run(f" {question.source.upper()} ")
                origem.bold = False
                origem.font.size = Pt(8)
                origem.font.color.rgb = TEXTO_SUAVE
                _shade_run(origem, FUNDO_ORIGEM)

            for group in question.stem_paragraphs:
                only_figure = all(f.kind == "image" and not f.inline for f in group)
                if only_figure:
                    for fragment in group:
                        _emit_figure(document, fragment, assets_dir)
                    continue
                style = (
                    "SME Credito" if group[0].align == "right" else "SME Enunciado"
                )
                paragraph = document.add_paragraph(style=style)
                _emit(paragraph, group, assets_dir)

            for alternative in question.alternatives:
                style = (
                    "SME Alternativa Correta"
                    if alternative.correct and mostrar_gabarito
                    else "SME Alternativa"
                )
                paragraph = document.add_paragraph(style=style)
                rotulo = paragraph.add_run(f"{alternative.letter}) ")
                rotulo.bold = True
                rotulo.font.color.rgb = (
                    VERDE if alternative.correct and mostrar_gabarito else AZUL_ESCURO
                )
                _emit(paragraph, alternative.fragments, assets_dir)
                if alternative.correct and mostrar_gabarito:
                    paragraph.add_run("  ✓").font.color.rgb = VERDE
                    _shade(paragraph, FUNDO_CORRETA)

            if mostrar_gabarito and question.needs_review:
                document.add_paragraph(
                    "revisar: " + "; ".join(question.needs_review),
                    style="SME Pendencia",
                )

    if mostrar_gabarito:
        document.add_page_break()
        chip = document.add_paragraph(style="SME Chip")
        marca = chip.add_run("  GABARITO  ")
        marca.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade_run(marca, FUNDO_CHIP)
        document.add_paragraph("Folha de respostas", style="SME Descritor")
        _regua(document)
        for descriptor in descriptors:
            document.add_paragraph(
                f"Descritor {descriptor.number}", style="SME Secao"
            )
            answers = [q.answer or "?" for q in descriptor.questions]
            columns = 8
            rows = -(-len(answers) // columns)
            table = document.add_table(rows=rows, cols=columns)
            table.style = "Table Grid"
            for i, answer in enumerate(answers):
                cell = table.cell(i // columns, i % columns)
                cell.text = f"{i + 1}. {answer}"
                cell.paragraphs[0].runs[0].font.size = Pt(9)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(out_path))
    # Sem isto o Word substitui Baloo 2 e Nunito e o arquivo nao tem nada a ver com
    # o PDF. As fontes viajam dentro do proprio .docx.
    docx_fonts.embed(out_path)
    return out_path
