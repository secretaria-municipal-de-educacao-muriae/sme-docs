"""Orquestracao: do .docx aos arquivos de saida.

Camada fina entre a CLI e os modulos do pipeline. Existe para que a CLI de hoje e a
API de amanha chamem exatamente o mesmo caminho.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import answers, wordmath
from .docx_render import render_docx
from .extract import extract
from .models import Descriptor
from .render import print_pdf, render_html
from .segment import Media, segment


@dataclass
class Stats:
    questions: int = 0
    with_key: int = 0
    from_overlay: int = 0
    clean: int = 0
    formulas: int = 0
    formulas_from_word: int = 0
    images: int = 0
    pending: dict[str, int] = field(default_factory=dict)

    @property
    def key_percent(self) -> int:
        return self.with_key * 100 // self.questions if self.questions else 0

    @property
    def clean_percent(self) -> int:
        return self.clean * 100 // self.questions if self.questions else 0


@dataclass
class Result:
    descriptors: list[Descriptor]
    stats: Stats
    outputs: list[Path] = field(default_factory=list)
    elapsed: float = 0.0
    word_used: bool = False


def summarize(descriptors: list[Descriptor]) -> Stats:
    questions = [q for d in descriptors for q in d.questions]
    fragments = [f for q in questions for f in q.stem] + [
        f for q in questions for a in q.alternatives for f in a.fragments
    ]
    images = [f for f in fragments if f.kind == "image"]

    stats = Stats(
        questions=len(questions),
        with_key=sum(1 for q in questions if q.answer),
        from_overlay=sum(
            1 for q in questions for a in q.alternatives if a.correct and a.from_overlay
        ),
        clean=sum(1 for q in questions if not q.needs_review),
        formulas=sum(1 for f in images if f.inline),
        formulas_from_word=sum(1 for f in images if (f.asset or "").startswith("eq-")),
        images=len(images),
    )
    for question in questions:
        for problem in question.needs_review:
            key = problem.split(":")[0]
            stats.pending[key] = stats.pending.get(key, 0) + 1
    return stats


def load(
    docx: Path | list[Path],
    out_dir: Path,
    only: set[int] | None = None,
    use_word: bool = True,
    on_step=None,
) -> tuple[list[Descriptor], Media, bool]:
    """Le um ou mais documentos e devolve os descritores pedidos, mesclados.

    Com mais de um arquivo, descritores do mesmo numero se combinam: as questoes do
    segundo arquivo continuam a numeracao das do primeiro. Um numero de descritor que
    so existe no segundo arquivo — o caso do cliente mandando o 31 que falta no acervo
    principal — vira descritor novo, sem precisar colar dentro do .docx grande.
    """

    def step(message: str) -> None:
        if on_step:
            on_step(message)

    sources = docx if isinstance(docx, (list, tuple)) else [docx]
    multi = len(sources) > 1
    assets_dir = out_dir / "assets"
    word_used = False
    merged: dict[int, Descriptor] = {}

    for source in sources:
        eq_dir = out_dir / "eqcache" / source.stem if multi else out_dir / "eqcache"
        equations: dict = {}
        if use_word and wordmath.is_available():
            step(f"renderizando fórmulas pelo Word ({source.name})" if multi else "renderizando fórmulas pelo Word")
            equations = wordmath.render_equations(source, eq_dir)
            word_used = True

        step(f"lendo {source.name}" if multi else "lendo o documento")
        blocks, archive = extract(source)

        step("recuperando a estrutura")
        ctx = Media(
            assets_dir=assets_dir,
            eq_dir=eq_dir,
            equations=equations,
            source_tag=f"{source.stem}-" if multi else "",
        )
        for descriptor in segment(blocks, archive, ctx, only=only):
            base = merged.get(descriptor.number)
            if base is None:
                merged[descriptor.number] = descriptor
                continue
            # Mesmo numero de descritor em dois arquivos: as questoes do segundo
            # continuam a sequencia do primeiro em vez de colidir no id.
            start = len(base.questions) + 1
            for i, question in enumerate(descriptor.questions, start=start):
                question.id = f"D{descriptor.number:02d}-Q{i:03d}"
            base.questions.extend(descriptor.questions)

    descriptors = [merged[n] for n in sorted(merged)]

    # O gabarito preenchido a mao entra por cima, so onde o documento nao marcou nada.
    answers.apply(descriptors, answers.AnswerSheet.load())
    return descriptors, Media(assets_dir=assets_dir), word_used


def build(
    docx: Path | list[Path],
    out_dir: Path,
    only: set[int] | None = None,
    formats: tuple[str, ...] = ("pdf",),
    use_word: bool = True,
    show_key: bool = True,
    subtitulo: str = "Matemática — 6º ao 9º Ano",
    on_step=None,
) -> Result:
    started = time.time()
    descriptors, ctx, word_used = load(docx, out_dir, only, use_word, on_step)

    numbers = sorted(d.number for d in descriptors)
    slug = "-".join(str(n) for n in numbers) or "vazio"
    label = ", ".join(str(n) for n in numbers)
    legenda = f"Descritor {label}" if len(numbers) == 1 else f"Descritores {label}"

    outputs: list[Path] = []

    if "pdf" in formats:
        if on_step:
            on_step("montando o HTML")
        html = render_html(
            descriptors,
            out_dir,
            subtitulo=subtitulo,
            legenda=legenda,
            mostrar_gabarito=show_key,
            filename=f"descritor-{slug}.html",
        )
        if on_step:
            on_step("imprimindo o PDF")
        outputs.append(print_pdf(html, out_dir / f"descritor-{slug}.pdf"))

    if "docx" in formats:
        if on_step:
            on_step("montando o DOCX")
        outputs.append(
            render_docx(
                descriptors,
                out_dir / f"descritor-{slug}.docx",
                ctx.assets_dir,
                subtitulo=subtitulo,
                legenda=legenda,
                mostrar_gabarito=show_key,
            )
        )

    return Result(
        descriptors=descriptors,
        stats=summarize(descriptors),
        outputs=outputs,
        elapsed=time.time() - started,
        word_used=word_used,
    )
