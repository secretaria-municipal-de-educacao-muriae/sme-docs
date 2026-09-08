"""Montagem do HTML e impressao do PDF.

O PDF de referencia foi gerado pelo Chromium ("producer: Skia/PDF m152"). O mesmo
motor e usado aqui, entao o resultado bate com o modelo. Na versao final quem imprime
e o proprio Electron, que ja embute esse motor; aqui o Chrome instalado faz o papel.
"""

from __future__ import annotations

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
    fontes_online: bool = True,
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
