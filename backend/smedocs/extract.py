"""Leitura de .docx para a representacao intermediaria (IR).

Percorre word/document.xml na ordem do documento e emite blocos tipados.

Nao usa docling de proposito: o backend DOCX da docling nao percorre w:object nem
v:imagedata, entao descarta as 539 formulas WMF deste acervo. Ver CLAUDE.md.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "o": "urn:schemas-microsoft-com:office:office",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{%s}" % NS["w"]
A = "{%s}" % NS["a"]
WP = "{%s}" % NS["wp"]
V = "{%s}" % NS["v"]
R = "{%s}" % NS["r"]

EMU_PER_PT = 12700
# Glifo Wingdings usado como marca decorativa no original, 162 ocorrencias. Sai como
# "(☻☻)" no meio das frases. Nao confundir com −, √, ×, ≥, ≤ e •, que sao conteudo.
RE_DINGBAT = re.compile(r"[☺☻]+")
# Cor de fonte que marca a alternativa correta no acervo. Duas tonalidades em uso.
GABARITO_COLORS = {"FF0000", "EE0000"}


@dataclass
class TextRun:
    text: str
    bold: bool = False
    italic: bool = False
    color: str | None = None
    kind: str = "text"


@dataclass
class ImageRun:
    rel_id: str
    part: str
    width_pt: float
    height_pt: float
    is_ole: bool = False
    kind: str = "image"


@dataclass
class Block:
    index: int
    align: str | None = None
    runs: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs if isinstance(r, TextRun))

    @property
    def images(self) -> list[ImageRun]:
        return [r for r in self.runs if isinstance(r, ImageRun)]

    @property
    def has_gabarito_color(self) -> bool:
        """Algum run com texto real esta na cor de gabarito."""
        return any(
            isinstance(r, TextRun)
            and r.text.strip()
            and (r.color or "").upper() in GABARITO_COLORS
            for r in self.runs
        )

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "align": self.align,
            "runs": [asdict(r) for r in self.runs],
        }


def _style_dim(style: str, prop: str) -> float:
    """Extrai width/height do atributo style do VML, sempre em pontos."""
    m = re.search(rf"{prop}:\s*([\d.]+)pt", style or "")
    return float(m.group(1)) if m else 0.0


def _relationships(z: zipfile.ZipFile) -> dict[str, str]:
    root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    out = {}
    for rel in root:
        target = rel.get("Target", "")
        if target.startswith("/"):
            target = target[1:]
        elif not target.startswith("word/"):
            target = "word/" + target
        out[rel.get("Id")] = target
    return out


def _run_props(run: ET.Element) -> tuple[bool, bool, str | None]:
    rpr = run.find(W + "rPr")
    if rpr is None:
        return False, False, None
    bold = rpr.find(W + "b") is not None
    italic = rpr.find(W + "i") is not None
    color_el = rpr.find(W + "color")
    color = color_el.get(W + "val") if color_el is not None else None
    return bold, italic, color


def _drawing_image(node: ET.Element, rels: dict) -> ImageRun | None:
    extent = node.find(".//" + WP + "extent")
    blip = node.find(".//" + A + "blip")
    if blip is None:
        return None
    rel_id = blip.get(R + "embed")
    if rel_id not in rels:
        return None
    cx = int(extent.get("cx", 0)) if extent is not None else 0
    cy = int(extent.get("cy", 0)) if extent is not None else 0
    return ImageRun(
        rel_id=rel_id,
        part=rels[rel_id],
        width_pt=cx / EMU_PER_PT,
        height_pt=cy / EMU_PER_PT,
    )


def _ole_image(node: ET.Element, rels: dict) -> ImageRun | None:
    """A formula de matematica: OLE Equation 3.0 renderizado como WMF via VML."""
    shape = node.find(V + "shape")
    if shape is None:
        return None
    imagedata = shape.find(V + "imagedata")
    if imagedata is None:
        return None
    rel_id = imagedata.get(R + "id")
    if rel_id not in rels:
        return None
    style = shape.get("style", "")
    return ImageRun(
        rel_id=rel_id,
        part=rels[rel_id],
        width_pt=_style_dim(style, "width"),
        height_pt=_style_dim(style, "height"),
        is_ole=True,
    )


def _walk_run(run: ET.Element, rels: dict) -> list:
    """Percorre um w:r emitindo texto e imagens na ordem em que aparecem."""
    bold, italic, color = _run_props(run)
    out = []
    buffer = []

    def flush():
        if buffer:
            text = RE_DINGBAT.sub("", "".join(buffer))
            if text:
                out.append(TextRun(text, bold, italic, color))
            buffer.clear()

    for child in run:
        tag = child.tag
        if tag == W + "t":
            buffer.append(child.text or "")
        elif tag in (W + "tab",):
            buffer.append(" ")
        elif tag in (W + "br", W + "cr"):
            buffer.append(" ")
        elif tag == W + "drawing":
            flush()
            img = _drawing_image(child, rels)
            if img:
                out.append(img)
        elif tag == W + "object":
            flush()
            img = _ole_image(child, rels)
            if img:
                out.append(img)
        elif tag == W + "pict":
            flush()
            img = _ole_image(child, rels)
            if img:
                out.append(img)
    flush()
    return out


def extract(docx_path: str | Path) -> tuple[list[Block], zipfile.ZipFile]:
    """Devolve os blocos na ordem do documento e o zip aberto, para ler as midias."""
    z = zipfile.ZipFile(docx_path)
    rels = _relationships(z)
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")

    blocks: list[Block] = []
    for i, p in enumerate(body.iter(W + "p")):
        ppr = p.find(W + "pPr")
        align = None
        if ppr is not None:
            jc = ppr.find(W + "jc")
            if jc is not None:
                align = jc.get(W + "val")

        block = Block(index=i, align=align)
        # w:object pode estar solto no paragrafo, fora de um w:r
        for child in p:
            if child.tag == W + "r":
                block.runs.extend(_walk_run(child, rels))
            elif child.tag in (W + "object", W + "pict"):
                img = _ole_image(child, rels)
                if img:
                    block.runs.append(img)
            elif child.tag == W + "hyperlink":
                for sub in child.findall(W + "r"):
                    block.runs.extend(_walk_run(sub, rels))
        blocks.append(block)

    return blocks, z
