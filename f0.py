"""Gera a apostila de um descritor (ou de alguns) a partir do banco de questoes.

Ainda e script puro: sem Electron, sem banco, sem API.

    python f0.py            # descritor 1
    python f0.py 10         # descritor 10
    python f0.py 1 2 10     # varios no mesmo PDF

Na primeira execucao o Word e chamado uma vez para renderizar as 547 formulas de
matematica; o resultado fica em out/eqcache e as execucoes seguintes reaproveitam.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from smedocs import wordmath  # noqa: E402
from smedocs.extract import extract  # noqa: E402
from smedocs.render import print_pdf, render_html  # noqa: E402
from smedocs.segment import Media, segment  # noqa: E402

ROOT = Path(__file__).parent
DOCX = ROOT / "reference" / "APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx"
OUT = ROOT / "out"


def main() -> None:
    wanted = {int(a) for a in sys.argv[1:]} or {1}
    label = ", ".join(str(n) for n in sorted(wanted))
    print(f"descritores: {label}")

    equations: dict = {}
    eq_dir = OUT / "eqcache"
    if wordmath.is_available():
        t = time.time()
        equations = wordmath.render_equations(DOCX, eq_dir)
        print(f"  formulas pelo Word: {len(equations)} ({time.time() - t:.1f}s)")
    else:
        print("  Word nao encontrado — formulas pelo GDI, com risco de corrupcao")

    t = time.time()
    blocks, z = extract(DOCX)
    print(f"  {len(blocks)} blocos em {time.time() - t:.1f}s")

    ctx = Media(assets_dir=OUT / "assets", eq_dir=eq_dir, equations=equations)
    t = time.time()
    descriptors = segment(blocks, z, ctx, only=wanted)
    print(f"  segmentado em {time.time() - t:.1f}s")

    questions = [q for d in descriptors for q in d.questions]
    every = [f for q in questions for f in q.stem] + [
        f for q in questions for a in q.alternatives for f in a.fragments
    ]
    inline = [f for f in every if f.kind == "image" and f.inline]
    from_word = sum(1 for f in every if f.kind == "image" and f.asset.startswith("eq-"))

    with_key = [q for q in questions if q.answer]
    clean = [q for q in questions if not q.needs_review]
    percent = len(with_key) * 100 // max(len(questions), 1)

    print(f"\n  questoes .......... {len(questions)}")
    print(f"  gabarito automatico {len(with_key)} ({percent}%)")
    print(f"  sem pendencia ..... {len(clean)}")
    print(f"  formulas inline ... {len(inline)}  (pelo Word: {from_word})")

    pendencias: dict[str, int] = {}
    for q in questions:
        for p in q.needs_review:
            pendencias[p.split(":")[0]] = pendencias.get(p.split(":")[0], 0) + 1
    if pendencias:
        print("\n  pendencias de revisao:")
        for k, v in sorted(pendencias.items(), key=lambda kv: -kv[1]):
            print(f"    {v:4}  {k}")
        for q in questions:
            if q.needs_review:
                print(f"      {q.id}  {'; '.join(q.needs_review)}")

    slug = "-".join(str(n) for n in sorted(wanted))
    html = render_html(
        descriptors,
        OUT,
        subtitulo="Matemática — 6º ao 9º Ano",
        legenda=f"Descritor {label}" if len(wanted) == 1 else f"Descritores {label}",
        filename=f"descritor-{slug}.html",
    )
    pdf = print_pdf(html, OUT / f"descritor-{slug}.pdf")
    print(f"\n  {pdf}  ({pdf.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
