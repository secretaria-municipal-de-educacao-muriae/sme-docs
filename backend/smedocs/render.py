"""Montagem do HTML e impressao do PDF.

O PDF de referencia foi gerado pelo Chromium ("producer: Skia/PDF m152"). O mesmo
motor e usado aqui, entao o resultado bate com o modelo. Na versao final quem imprime
e o proprio Electron, que ja embute esse motor; aqui o Chrome instalado faz o papel.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import Descriptor, Fragment

HERE = Path(__file__).parent
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    local = os.environ.get("LOCALAPPDATA", "")
    candidate = Path(local) / "Google/Chrome/Application/chrome.exe"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("Chrome ou Edge nao encontrado para imprimir o PDF")


def _split_paragraphs(fragments: list[Fragment]) -> list[list[Fragment]]:
    """A intro vem como fluxo unico com \\n de separacao; vira lista de paragrafos."""
    out: list[list[Fragment]] = [[]]
    for f in fragments:
        if f.kind == "text" and f.text == "\n":
            out.append([])
        else:
            out[-1].append(f)
    return [p for p in out if any(f.text.strip() or f.kind == "image" for f in p)]


def render_html(
    descriptors: list[Descriptor],
    out_dir: Path,
    titulo: str = "Banco de Questões por Descritor",
    sobretitulo: str = "Recomposição das Aprendizagens",
    subtitulo: str = "Matemática — 6º ao 9º Ano",
    legenda: str = "",
    mostrar_gabarito: bool = True,
    fontes_online: bool = False,
    filename: str = "apostila.html",
) -> Path:
    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("apostila.html.j2")

    view = []
    for d in descriptors:
        item = d.model_dump()
        item["intro_paragrafos"] = _split_paragraphs(d.intro)
        item["questions"] = d.questions
        view.append(item)

    html = template.render(
        descritores=view,
        titulo=titulo,
        sobretitulo=sobretitulo,
        subtitulo=subtitulo,
        legenda=legenda,
        mostrar_gabarito=mostrar_gabarito,
        fontes_online=fontes_online,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "static" / "styles.css", out_dir / "styles.css")
    # As fontes viajam com o projeto: o PDF nao pode depender da rede para ficar igual
    # ao template, e as maquinas do setor nem sempre tem saida para a internet.
    fonts_source = HERE / "fonts"
    if fonts_source.is_dir():
        shutil.copytree(fonts_source, out_dir / "fonts", dirs_exist_ok=True)
    path = out_dir / filename
    path.write_text(html, encoding="utf-8")
    return path


def print_pdf(html_path: Path, pdf_path: Path, timeout: int = 300) -> Path:
    """Imprime via Chrome headless. Mesmo caminho que o Electron usara depois."""
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                find_chrome(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=20000",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}",
                html_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    return pdf_path


def render_infantil(
    paginas: list[dict],
    out_dir: Path,
    ficha: bool = True,
    filename: str = "modelos-infantil.html",
    titulo_arquivo: str = "Modelos — Apostila Educação Infantil",
) -> Path:
    """Monta as paginas da apostila infantil (A4 deitado).

    `paginas` e uma lista de {"modelo": "M03", "nome": ..., "quando_usar": ..., "dados": {...}}.
    Com `ficha` ligada sai o catalogo de modelos, com a legenda de cada um acima da
    pagina; ela some na impressao. Desligada sai a apostila limpa.
    """
    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("infantil.html.j2").render(
        paginas=paginas, ficha=ficha, titulo_arquivo=titulo_arquivo
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "static" / "infantil.css", out_dir / "infantil.css")
    shutil.copytree(HERE / "static" / "infantil", out_dir / "infantil", dirs_exist_ok=True)
    shutil.copytree(HERE / "fonts", out_dir / "fonts", dirs_exist_ok=True)
    path = out_dir / filename
    path.write_text(html, encoding="utf-8")
    return path


def catalogo_infantil() -> list[dict]:
    """Le modelos_infantil.json e devolve uma pagina por modelo, com o conteudo de exemplo."""
    dados = json.loads((HERE / "modelos_infantil.json").read_text(encoding="utf-8"))
    return [
        {
            "modelo": m["id"],
            "nome": m["nome"],
            "quando_usar": m["quando_usar"],
            "dados": m["demo"],
        }
        for m in dados["modelos"]
    ]


def export_svg(pdf_path: Path, out_dir: Path, texto_em_curvas: bool = False) -> list[Path]:
    """Escreve um SVG por pagina do PDF. Um arquivo por pagina, vetor de verdade.

    O PDF do Chrome ja e vetorial e o Illustrator abre ele direto; o SVG existe para
    quem prefere editar no Figma, no Inkscape ou dentro do proprio navegador.

    Com `texto_em_curvas` o texto vira contorno: fica identico em qualquer maquina,
    mas deixa de ser texto editavel. Sem isso, o SVG guarda o nome da fonte — e por
    isso as faces do projeto sao .ttf e nao .otf (ver fonts_otf2ttf.py).
    """
    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    destino = []
    with pymupdf.open(pdf_path) as doc:
        for numero, pagina in enumerate(doc, 1):
            svg = pagina.get_svg_image(text_as_path=texto_em_curvas)
            caminho = out_dir / f"{pdf_path.stem}-{numero:02d}.svg"
            caminho.write_text(svg, encoding="utf-8")
            destino.append(caminho)
    return destino
