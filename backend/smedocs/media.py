"""Normalizacao de midia: tudo vira PNG utilizavel pelo navegador.

WMF nao renderiza em navegador. As 539 formulas de matematica do acervo sao WMF,
geradas pelo Microsoft Equation 3.0.

Duas fontes de pixel, nesta ordem de preferencia:

1. **Word** (`wordmath.py`), quando disponivel. Fiel, porque o Word desenha a partir do
   objeto OLE. Obrigatorio para as formulas com parenteses.
2. **GDI via Pillow**, como reserva. Funciona para a maioria, mas corrompe entre 8% e
   17% das formulas — as que tem parenteses. Ver CLAUDE.md.

Windows apenas.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

# WMF e vetorial. Rasterizar acima do alvo de impressao e deixar o CSS reduzir mantem
# a formula nitida. Mas o WMF traz o tamanho em pontos, e as figuras grandes deste
# acervo chegam a 500pt: a 600 DPI isso vira uma imagem de 93 megapixels, que estoura
# o limite do Pillow e leva minutos. O DPI se adapta ao tamanho declarado.
WMF_TARGET_DPI = 600
WMF_MAX_PIXELS = 1600
# Guarda de seguranca: acima disso e formula de bloco mesmo com texto ao lado.
INLINE_MAX_HEIGHT_PT = 60.0


def _wmf_dpi(width_pt: float, height_pt: float) -> int:
    largest_pt = max(width_pt, height_pt, 1.0)
    dpi = min(WMF_TARGET_DPI, int(WMF_MAX_PIXELS / (largest_pt / 72)))
    return max(dpi, 150)


@dataclass
class Asset:
    """Uma imagem ja convertida e pronta para o HTML."""

    filename: str
    width_pt: float
    height_pt: float
    is_ole: bool
    inline: bool
    source: str = "gdi"


def _trim(img: Image.Image) -> tuple[Image.Image, float, float]:
    """Corta a borda branca. Devolve a imagem e a fracao de largura/altura mantida.

    O Equation 3.0 gera WMF com muita margem em volta da formula. Sem cortar, a
    formula fica pequena no meio de um retangulo vazio e desalinha a linha de texto.
    """
    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg)
    bbox = diff.getbbox()
    if not bbox:
        return img, 1.0, 1.0
    w, h = img.size
    cropped = img.crop(bbox)
    return cropped, cropped.width / w, cropped.height / h


def _from_word(
    part: str, width_pt: float, equations: dict, eq_dir: Path, out_dir: Path
) -> Asset | None:
    """Usa o recorte que o Word produziu, quando existe para esta parte."""
    entry = equations.get(Path(part).name)
    if not entry:
        return None
    source = Path(eq_dir) / entry["png"]
    if not source.exists():
        return None

    dest = out_dir / f"eq-{Path(part).stem}.png"
    if not dest.exists():
        shutil.copy(source, dest)

    # O Word desenha a formula no tamanho natural do objeto; o docx a coloca reduzida
    # na linha. A largura declarada no docx manda, e a altura segue a proporcao do
    # recorte do Word — que e justo, sem a margem vazia que o WMF carrega.
    aspect = entry["width_pt"] / entry["height_pt"] if entry["height_pt"] else 1.0
    final_w = width_pt or entry["width_pt"]
    final_h = final_w / aspect if aspect else entry["height_pt"]

    return Asset(
        filename=dest.name,
        width_pt=round(final_w, 2),
        height_pt=round(final_h, 2),
        is_ole=True,
        inline=final_h <= INLINE_MAX_HEIGHT_PT,
        source="word",
    )


def convert(
    z: zipfile.ZipFile,
    part: str,
    width_pt: float,
    height_pt: float,
    is_ole: bool,
    out_dir: Path,
    equations: dict | None = None,
    eq_dir: Path | None = None,
    use_cache: bool = True,
) -> Asset:
    """Converte uma parte de midia do docx para PNG em out_dir.

    O cache é por digest do conteúdo (`<sha>.png` + `<sha>.dim`); `use_cache=False`
    (flag `--sem-cache`) reconverte mesmo com o PNG já em disco.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if is_ole and equations and eq_dir:
        asset = _from_word(part, width_pt, equations, eq_dir, out_dir)
        if asset:
            return asset

    data = z.read(part)
    digest = hashlib.sha1(data).hexdigest()[:12]
    filename = f"{digest}.png"
    dest = out_dir / filename
    dims = out_dir / f"{digest}.dim"

    if use_cache and dest.exists() and dims.exists():
        w_pt, h_pt = (float(x) for x in dims.read_text().split())
    else:
        img = Image.open(io.BytesIO(data))
        if part.lower().endswith(".wmf"):
            img.load(dpi=_wmf_dpi(width_pt, height_pt))
        img, fw, fh = _trim(img)
        # O corte muda o tamanho util, entao o tamanho declarado no docx encolhe junto.
        w_pt, h_pt = width_pt * fw, height_pt * fh
        img.convert("RGB").save(dest, "PNG", optimize=True)
        dims.write_text(f"{w_pt} {h_pt}")

    return Asset(
        filename=filename,
        width_pt=round(w_pt, 2),
        height_pt=round(h_pt, 2),
        is_ole=is_ole,
        inline=is_ole and h_pt <= INLINE_MAX_HEIGHT_PT,
        source="gdi",
    )
