"""Renderizacao fiel das formulas de matematica usando o proprio Word.

Por que existe: as formulas sao objetos OLE do Equation 3.0, e o docx guarda junto uma
previa em WMF. Rasterizar essa previa com o GDI corrompe toda formula que tenha
parenteses — os glifos se empilham. Medido em F0: entre 8% e 17% do acervo. Nao e
questao de resolucao; a corrupcao e identica de 72 a 1200 DPI. Ver CLAUDE.md.

O Word desenha a partir do OLE, nao da previa, e acerta. A estrategia:

1. montar um docx auxiliar com uma formula por pagina, na ordem do documento
2. o Word exporta esse docx em PDF (COM, ExportAsFixedFormat)
3. cada pagina vira um PNG recortado no traco da formula

A pagina N corresponde a formula N por construcao, entao nao ha adivinhacao de
posicao. O resultado fica em cache e so e refeito quando o docx de origem muda.

Requer Microsoft Word instalado. Sem ele, media.py cai de volta para o GDI.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

W = "{%s}" % NS["w"]
R = "{%s}" % NS["r"]
V = "{%s}" % NS["v"]
O = "{%s}" % NS["o"]

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="wmf" ContentType="image/x-wmf"/>
<Default Extension="emf" ContentType="image/x-emf"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

REL_TYPE = {
    "image": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    "oleObject": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
}

# Margem estreita e pagina larga: cada formula cabe inteira numa pagina, sem quebrar.
SECTION = (
    '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
    '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"'
    ' w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>'
)


def _source_key(docx_path: Path) -> str:
    stat = docx_path.stat()
    return hashlib.sha1(
        f"{docx_path.name}|{stat.st_size}|{int(stat.st_mtime)}".encode()
    ).hexdigest()[:16]


def collect_objects(z: zipfile.ZipFile) -> list[dict]:
    """Todos os w:object do documento, na ordem, com as partes que cada um usa."""
    rels = {}
    for rel in ET.fromstring(z.read("word/_rels/document.xml.rels")):
        target = rel.get("Target", "")
        rels[rel.get("Id")] = target if target.startswith("word/") else "word/" + target

    root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for node in root.iter(W + "object"):
        shape = node.find(V + "shape")
        ole = node.find(O + "OLEObject")
        if shape is None:
            continue
        imagedata = shape.find(V + "imagedata")
        if imagedata is None:
            continue
        image_rel = imagedata.get(R + "id")
        if image_rel not in rels:
            continue
        out.append(
            {
                "node": node,
                "image_part": rels[image_rel],
                "ole_part": rels.get(ole.get(R + "id")) if ole is not None else None,
                "prog_id": ole.get("ProgID") if ole is not None else None,
            }
        )
    return out


def build_probe_docx(src: Path, dest: Path) -> list[str]:
    """Gera o docx auxiliar. Devolve o nome da parte de imagem de cada pagina, em ordem."""
    z = zipfile.ZipFile(src)
    objects = collect_objects(z)

    body_parts: list[str] = []
    relationships: list[str] = []
    payload: dict[str, str] = {}
    order: list[str] = []

    for i, item in enumerate(objects):
        node = item["node"]
        shape = node.find(V + "shape")
        imagedata = shape.find(V + "imagedata")
        ole = node.find(O + "OLEObject")

        image_id = f"rId{i * 2 + 100}"
        imagedata.set(R + "id", image_id)
        image_name = Path(item["image_part"]).name
        payload[f"word/media/{image_name}"] = item["image_part"]
        relationships.append(
            f'<Relationship Id="{image_id}" Type="{REL_TYPE["image"]}"'
            f' Target="media/{image_name}"/>'
        )

        if item["ole_part"] and ole is not None:
            ole_id = f"rId{i * 2 + 101}"
            ole.set(R + "id", ole_id)
            ole_name = Path(item["ole_part"]).name
            payload[f"word/embeddings/{ole_name}"] = item["ole_part"]
            relationships.append(
                f'<Relationship Id="{ole_id}" Type="{REL_TYPE["oleObject"]}"'
                f' Target="embeddings/{ole_name}"/>'
            )

        obj_xml = ET.tostring(node, encoding="unicode")
        brk = "" if i == len(objects) - 1 else '<w:r><w:br w:type="page"/></w:r>'
        body_parts.append(f"<w:p><w:r>{obj_xml}</w:r>{brk}</w:p>")
        order.append(image_name)

    declarations = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {declarations}><w:body>"
        + "".join(body_parts)
        + SECTION
        + "</w:body></w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(relationships)
        + "</Relationships>"
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("[Content_Types].xml", CONTENT_TYPES)
        out.writestr("_rels/.rels", ROOT_RELS)
        out.writestr("word/document.xml", document)
        out.writestr("word/_rels/document.xml.rels", rels_xml)
        for name, source in payload.items():
            out.writestr(name, z.read(source))
    return order


def export_pdf(docx_path: Path, pdf_path: Path) -> Path:
    """Word converte o docx auxiliar em PDF. wdExportFormatPDF = 17."""
    import win32com.client as win32

    app = win32.gencache.EnsureDispatch("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    doc = app.Documents.Open(str(docx_path.resolve()), ReadOnly=True, AddToRecentFiles=False)
    try:
        doc.ExportAsFixedFormat(str(pdf_path.resolve()), 17, False, 0)
    finally:
        doc.Close(False)
        app.Quit()
    return pdf_path


def slice_pdf(pdf_path: Path, order: list[str], out_dir: Path, dpi: int = 600) -> dict:
    """Recorta cada pagina no traco da formula e salva um PNG por parte de origem."""
    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    produced: dict[str, dict] = {}

    for index, image_name in enumerate(order):
        if index >= doc.page_count:
            break
        page = doc[index]

        # O traco da formula sao glifos mais os riscos de fracao e radical. A uniao
        # dos dois da a caixa exata, sem varrer pixel.
        #
        # Tem que ser no nivel do span, nao do bloco: o bloco de texto do PDF ocupa a
        # largura do paragrafo inteiro, entao usa-lo deixava sobra a direita e a
        # proporcao saia ate 6x mais larga que a formula. Com a proporcao errada, a
        # formula era colocada minuscula no HTML.
        box = None

        def grow(rect) -> None:
            nonlocal box
            rect = pymupdf.Rect(rect)
            if rect.is_empty:
                return
            box = rect if box is None else box | rect

        # Espacos em branco contam como span e ficam longe da formula — o marcador de
        # paragrafo aparece a 165pt do traco. Incluir esses spans esticava a caixa em
        # ate 8x e a formula acabava minuscula na pagina.
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if span["text"].strip():
                        grow(span["bbox"])
        for drawing in page.get_drawings():
            grow(drawing["rect"])
        if box is None or box.is_empty:
            continue

        box = (box + (-1, -1, 1, 1)) & page.rect
        pixmap = page.get_pixmap(dpi=dpi, clip=box, alpha=False)
        target = out_dir / f"{Path(image_name).stem}.png"
        pixmap.save(target)
        produced[image_name] = {
            "png": target.name,
            "width_pt": round(box.width, 3),
            "height_pt": round(box.height, 3),
        }

    doc.close()
    return produced


def render_equations(
    src_docx: Path, cache_dir: Path, dpi: int = 600, force: bool = False
) -> dict:
    """Ponto de entrada. Devolve {nome_wmf: {png, width_pt, height_pt}}, com cache.

    O cache é invalidado por nome|tamanho|mtime do docx de origem; `force=True`
    (flag `--sem-cache`) ignora o manifesto e renderiza de novo.
    """
    cache_dir = Path(cache_dir)
    manifest_path = cache_dir / "manifest.json"
    key = _source_key(Path(src_docx))

    if not force and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("key") == key:
            return manifest["items"]

    work = cache_dir / "_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    probe = work / "equations.docx"
    order = build_probe_docx(Path(src_docx), probe)
    pdf = export_pdf(probe, work / "equations.pdf")
    items = slice_pdf(pdf, order, cache_dir, dpi=dpi)

    manifest_path.write_text(
        json.dumps({"key": key, "items": items}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    shutil.rmtree(work, ignore_errors=True)
    return items


def is_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    try:
        import winreg

        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application")
        return True
    except OSError:
        return False
