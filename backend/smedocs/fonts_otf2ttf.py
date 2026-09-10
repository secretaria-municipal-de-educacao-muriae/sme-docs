"""Converte as OTF do Neo Sans em TTF.

Motivo, medido: o Chrome headless embute fonte OTF (contornos CFF) no PDF como
fonte Type3. Type3 nao carrega o nome da familia — o texto sai marcado como
"Type3 (4 0 R)". Isso estraga tres coisas de uma vez: o SVG exportado perde o
nome da fonte, o texto do PDF nao e mais pesquisavel de forma confiavel e o
Illustrator abre o arquivo sem reconhecer a familia.

A mesma pagina com fonte TTF sai como Type0/TrueType com o nome certo
("BAAAAA+Nunito-Bold"). Entao a saida vetorial depende de TTF, nao de OTF.

Uso:
    python -m smedocs.fonts_otf2ttf
"""

from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
# Tolerancia da conversao de curva cubica para quadratica, em unidades de em.
# 1/1000 do em fica bem abaixo do que a impressao resolve.
TOLERANCIA = 1.0


def converter(origem: Path, destino: Path) -> Path:
    otf = TTFont(origem)
    upem = otf["head"].unitsPerEm
    glyph_set = otf.getGlyphSet()
    ordem = otf.getGlyphOrder()

    glifos = {}
    for nome in ordem:
        pen = TTGlyphPen(glyph_set)
        glyph_set[nome].draw(Cu2QuPen(pen, TOLERANCIA * upem / 1000))
        glifos[nome] = pen.glyph()

    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(ordem)
    fb.setupCharacterMap(otf.getBestCmap())
    fb.setupGlyf(glifos)
    fb.setupHorizontalMetrics({n: otf["hmtx"][n] for n in ordem})
    fb.setupHorizontalHeader(
        ascent=otf["hhea"].ascent,
        descent=otf["hhea"].descent,
        lineGap=otf["hhea"].lineGap,
    )
    fb.setupNameTable({r.nameID: r.toUnicode() for r in otf["name"].names if r.platformID == 3})
    fb.setupOS2(
        sTypoAscender=otf["OS/2"].sTypoAscender,
        sTypoDescender=otf["OS/2"].sTypoDescender,
        sTypoLineGap=otf["OS/2"].sTypoLineGap,
        usWinAscent=otf["OS/2"].usWinAscent,
        usWinDescent=otf["OS/2"].usWinDescent,
        sCapHeight=otf["OS/2"].sCapHeight,
        sxHeight=getattr(otf["OS/2"], "sxHeight", 0),
        fsSelection=otf["OS/2"].fsSelection,
        usWeightClass=otf["OS/2"].usWeightClass,
        achVendID=otf["OS/2"].achVendID,
    )
    fb.setupPost()
    fb.save(destino)
    return destino


def main() -> None:
    for otf in sorted(FONTS.glob("NeoSansStd-*.otf")):
        ttf = otf.with_suffix(".ttf")
        converter(otf, ttf)
        print(f"{otf.name} -> {ttf.name}  ({ttf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
