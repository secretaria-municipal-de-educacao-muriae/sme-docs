"""Regressão do preset Muriaé (tarefas 1.4 e 2.2).

    python tests/check_regression.py [--docx caminho] [--out pasta]

Verifica sobre o banco real:
- 31 descritores, 868 questões, 655 com gabarito (647 do Word + 8 à mão),
  627 sem pendência, 211 sem gabarito, defeitos estruturais por categoria;
- validação cruzada: 864+ alternativas A (contagem independente) == questões;
- paridade de imagens por descritor: fragmentos de imagem == <img> no HTML;
- equivalência de perfil: preset em código == profiles/banco-muriae.json,
  questão por questão (equivale a "gera o mesmo PDF" do 1.4, pois o HTML
  montado é determinístico e o PDF sai do mesmo motor).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from smedocs import pipeline  # noqa: E402
from smedocs.diagnose import diagnose_blocks, diagnose_questions  # noqa: E402
from smedocs.extract import extract  # noqa: E402
from smedocs.models import Descriptor  # noqa: E402
from smedocs.profile import PRESET_MURIAE, IngestionProfile  # noqa: E402
from smedocs.render import render_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [
    ROOT / "reference" / "APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx",
    ROOT / "APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx",
]

EXPECTED = {
    "descriptors": 31,
    "questions": 868,
    "with_key": 655,  # 647 do Word + 8 da sobreposição manual
    "from_overlay": 8,
    "clean": 627,  # 619 + 8 resolvidas à mão
    "no_answer": 213,  # 211 sem marcação + 2 com marcação dupla (answer é None)
    "pending": {
        "sem gabarito": 211,
        "letras fora de sequencia": 26,
        "apenas 2 alternativas": 13,
        "apenas 3 alternativas": 12,
        "letras repetidas": 5,
        "2 alternativas marcadas": 2,
        "apenas 1 alternativas": 3,
        "enunciado vazio": 1,
    },
}

IMG_RE = re.compile(r"<img\b")


def _images(descriptors: list[Descriptor]) -> int:
    n = 0
    for d in descriptors:
        n += sum(1 for f in d.intro if f.kind == "image")
        for q in d.questions:
            n += q.image_count
    return n


def main() -> int:
    docx = Path(sys.argv[sys.argv.index("--docx") + 1]) if "--docx" in sys.argv else None
    docx = docx or next((p for p in CANDIDATES if p.exists()), None)
    if docx is None:
        print("banco .docx não encontrado (reference/ ou raiz do repo)")
        return 2
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "out"

    failures: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"  [{'OK' if ok else 'FALHA'}] {label}: {got} (esperado {want})")
        if not ok:
            failures.append(label)

    print(f"banco: {docx.name}")
    # use_word=True reaproveita o eqcache do Word (manifest por nome|tamanho|mtime);
    # sem ele, a rasterização GDI das 539 WMF leva dezenas de minutos.
    descriptors, _, word_used = pipeline.load(docx, out, use_word=True)
    print(f"  [info] fórmulas pelo Word: {word_used}")
    stats = pipeline.summarize(descriptors)
    questions = [q for d in descriptors for q in d.questions]

    check("descritores", len(descriptors), EXPECTED["descriptors"])
    check("questões", stats.questions, EXPECTED["questions"])
    check("com gabarito", stats.with_key, EXPECTED["with_key"])
    check("preenchidas à mão", stats.from_overlay, EXPECTED["from_overlay"])
    check("sem pendência", stats.clean, EXPECTED["clean"])
    check(
        "sem resposta única",
        sum(1 for q in questions if not q.answer),
        EXPECTED["no_answer"],
    )
    for key, want in EXPECTED["pending"].items():
        got = sum(1 for q in questions for p in q.needs_review if p.split(":")[0] == key)
        check(f"pendência [{key}]", got, want)

    blocks, archive = extract(docx)
    archive.close()
    diag = diagnose_questions(diagnose_blocks(blocks), descriptors)
    check("alternativas A (independente)", diag.first_count, 866)
    check("questões com A", diag.questions_with_first, 866)
    check("questões sem A (degeneradas)", diag.no_first_ids, ["D28-Q049", "D28-Q075"])
    check("validação cruzada A == questões-com-A", diag.cross_ok, True)

    # Paridade de imagens por descritor: modelo vs HTML montado.
    html_dir = out / "regression"
    mismatches = 0
    for d in descriptors:
        html = render_html([d], html_dir, legenda=f"Descritor {d.number}",
                           filename=f"regression-{d.number}.html")
        imgs_html = len(IMG_RE.findall(html.read_text(encoding="utf-8")))
        imgs_model = _images([d])
        if imgs_html != imgs_model:
            print(f"  [FALHA] imagens D{d.number}: modelo={imgs_model} html={imgs_html}")
            mismatches += 1
    print(f"  [{'OK' if not mismatches else 'FALHA'}] paridade de imagens "
          f"em {len(descriptors)} descritores ({_images(descriptors)} imagens)")
    if mismatches:
        failures.append("paridade de imagens")

    # Equivalência preset código vs JSON (tarefa 1.4).
    from_json = IngestionProfile.from_json(ROOT / "profiles" / "banco-muriae.json")
    check(
        "JSON == preset em código",
        from_json.model_dump() == PRESET_MURIAE.model_dump(),
        True,
    )
    other, _, _ = pipeline.load(docx, out, use_word=True, profile=from_json)
    same = [d.model_dump() for d in descriptors] == [d.model_dump() for d in other]
    check("segmentação JSON == preset", same, True)

    print("REGRESSÃO OK" if not failures else f"REGRESSÃO FALHOU: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
