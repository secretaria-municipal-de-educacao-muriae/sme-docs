"""Embute as fontes do template dentro do .docx.

Baloo 2 e Nunito vêm do Google Fonts e não estão instaladas nas máquinas do setor.
Sem elas, o Word substitui por conta própria e o documento não tem nada a ver com o
PDF. Instalar fonte em cada máquina seria trabalho recorrente, então o arquivo carrega
as suas: o Word abre igual em qualquer lugar.

O formato exige que cada fonte seja ofuscada — os primeiros 32 bytes vão em XOR com uma
chave derivada de um GUID, conforme ECMA-376 parte 1, seção 15.2.13. É isso que o
`.odttf` é: um TTF com a cabeça embaralhada.
"""

from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from pathlib import Path

FONTS_DIR = Path(__file__).parent / "fonts"

# Cada família com os arquivos que preenchem os quatro encaixes do Word.
FAMILIES: dict[str, dict[str, str]] = {
    "Nunito": {
        "embedRegular": "Nunito-Regular.ttf",
        "embedBold": "Nunito-Bold.ttf",
        "embedItalic": "Nunito-Italic.ttf",
    },
    "Baloo 2": {
        "embedRegular": "Baloo2-Bold.ttf",
        "embedBold": "Baloo2-Bold.ttf",
    },
}

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
FONT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
ODTTF_TYPE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"


def _obfuscate(data: bytes, guid: str) -> bytes:
    """Embaralha os 32 primeiros bytes com a chave do GUID, aplicada duas vezes."""
    digits = guid.strip("{}").replace("-", "")
    key = bytes.fromhex(digits)[::-1]
    head = bytearray(data[:32])
    for i in range(len(head)):
        head[i] ^= key[i % 16]
    return bytes(head) + data[32:]


def _font_table(xml: str, plan: list[tuple[str, str, str, str]]) -> str:
    """Declara as fontes embutidas em word/fontTable.xml."""
    by_family: dict[str, list[tuple[str, str, str]]] = {}
    for family, slot, rel_id, key in plan:
        by_family.setdefault(family, []).append((slot, rel_id, key))

    for family, entries in by_family.items():
        embeds = "".join(
            f'<w:{slot} r:id="{rel_id}" w:fontKey="{key}"/>'
            for slot, rel_id, key in entries
        )
        # A família pode já existir na tabela; os elementos de embutir vão no fim dela.
        pattern = re.compile(
            rf'(<w:font w:name="{re.escape(family)}">)(.*?)(</w:font>)', re.S
        )
        if pattern.search(xml):
            xml = pattern.sub(rf"\1\2{embeds}\3", xml, count=1)
        else:
            xml = xml.replace(
                "</w:fonts>", f'<w:font w:name="{family}">{embeds}</w:font></w:fonts>'
            )

    if f'xmlns:r="{R}"' not in xml:
        xml = xml.replace("<w:fonts ", f'<w:fonts xmlns:r="{R}" ', 1)
    return xml


def embed(docx_path: Path, fonts_dir: Path | None = None) -> Path:
    """Reescreve o .docx com as fontes embutidas. Devolve o mesmo caminho."""
    source = Path(fonts_dir or FONTS_DIR)
    available = {
        family: {slot: source / name for slot, name in slots.items() if (source / name).exists()}
        for family, slots in FAMILIES.items()
    }
    available = {f: s for f, s in available.items() if s}
    if not available:
        return docx_path

    original = zipfile.ZipFile(docx_path)
    parts = {name: original.read(name) for name in original.namelist()}
    original.close()

    plan: list[tuple[str, str, str, str]] = []
    payload: dict[str, bytes] = {}
    rels: list[str] = []

    index = 0
    for family, slots in available.items():
        for slot, path in slots.items():
            index += 1
            guid = "{%s}" % str(uuid.uuid4()).upper()
            rel_id = f"rIdFont{index}"
            part = f"word/fonts/font{index}.odttf"
            payload[part] = _obfuscate(path.read_bytes(), guid)
            rels.append(
                f'<Relationship Id="{rel_id}" Type="{FONT_REL}"'
                f' Target="fonts/font{index}.odttf"/>'
            )
            plan.append((family, slot, rel_id, guid))

    content_types = parts["[Content_Types].xml"].decode("utf-8")
    if "obfuscatedFont" not in content_types:
        content_types = content_types.replace(
            "<Types ",
            "<Types ",
        ).replace(
            "</Types>",
            f'<Default Extension="odttf" ContentType="{ODTTF_TYPE}"/></Types>',
        )
    parts["[Content_Types].xml"] = content_types.encode("utf-8")

    parts["word/fontTable.xml"] = _font_table(
        parts["word/fontTable.xml"].decode("utf-8"), plan
    ).encode("utf-8")

    parts["word/_rels/fontTable.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    ).encode("utf-8")

    settings = parts["word/settings.xml"].decode("utf-8")
    if "embedTrueTypeFonts" not in settings:
        # Posição pelo esquema: depois de w:zoom e antes de w:proofState.
        flags = "<w:embedTrueTypeFonts/><w:saveSubsetFonts w:val=\"false\"/>"
        if "<w:proofState" in settings:
            settings = settings.replace("<w:proofState", flags + "<w:proofState", 1)
        else:
            settings = settings.replace("</w:settings>", flags + "</w:settings>")
    parts["word/settings.xml"] = settings.encode("utf-8")

    parts.update(payload)

    temporary = docx_path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in parts.items():
            out.writestr(name, data)
    shutil.move(str(temporary), str(docx_path))
    return docx_path
