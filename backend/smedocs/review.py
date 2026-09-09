"""Pacote de revisão: leva as questões sem gabarito para fora e traz as respostas.

Sem orçamento de API, o app não resolve questão nenhuma sozinho. O que ele faz é
preparar o trabalho e receber o resultado:

    smedocs pendencias --limite 20      escreve out/pendencias.md e out/pendencias.json
    (uma sessão do Claude Code, ou uma pessoa, resolve o lote)
    smedocs gabarito respostas.json     traz de volta para gabarito/respostas.json

O markdown é o que a sessão lê: traz enunciado, alternativas e o caminho das figuras,
para que quem responde possa abrir a imagem. O JSON é o molde a preencher — vem com as
letras em branco justamente para ser devolvido preenchido.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Descriptor, Question


def _plain(fragments) -> str:
    out = []
    for fragment in fragments:
        if fragment.kind == "text":
            out.append(fragment.text)
        elif fragment.kind == "image":
            out.append(" [figura] " if not fragment.inline else " [fórmula] ")
    return " ".join("".join(out).split())


def _images(question: Question) -> list[str]:
    everything = list(question.stem) + [
        f for a in question.alternatives for f in a.fragments
    ]
    return [f.asset for f in everything if f.kind == "image" and f.asset]


def export(
    descriptors: list[Descriptor],
    pending: list[Question],
    out_dir: Path,
    assets_dir: Path,
    limit: int | None = None,
) -> tuple[Path, Path, int]:
    """Escreve o pacote. Devolve (markdown, json, quantidade)."""
    titles = {d.number: d.title for d in descriptors}
    batch = pending[:limit] if limit else pending
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Questões sem gabarito",
        "",
        f"{len(batch)} de {len(pending)} pendentes neste lote.",
        "",
        "O documento de origem não marcou a alternativa correta em vermelho nestas "
        "questões. Resolva cada uma e devolva as letras em `pendencias.json`, no campo "
        "`letra`. Deixe em branco o que não der para decidir — em branco é melhor que "
        "chute, porque o material vai para a mão de professor.",
        "",
        "As figuras estão em `assets/`, no caminho indicado em cada questão.",
        "",
        "---",
        "",
    ]

    molde: dict[str, str] = {}
    for question in batch:
        molde[question.id] = ""
        lines.append(f"## {question.id}")
        lines.append("")
        lines.append(
            f"Descritor {question.descriptor} — {titles.get(question.descriptor, '')}"
        )
        if question.source:
            lines.append(f"Origem: {question.source}")
        lines.append("")
        lines.append(_plain(question.stem) or "_(enunciado só com figura)_")
        lines.append("")
        for alternative in question.alternatives:
            texto = _plain(alternative.fragments) or "_(só imagem)_"
            lines.append(f"- **{alternative.letter})** {texto}")
        figuras = _images(question)
        if figuras:
            lines.append("")
            for nome in figuras:
                lines.append(f"  figura: `{(assets_dir / nome).as_posix()}`")
        lines.append("")

    markdown = out_dir / "pendencias.md"
    markdown.write_text("\n".join(lines), encoding="utf-8")

    molde_path = out_dir / "pendencias.json"
    molde_path.write_text(
        json.dumps(
            {
                "_leia_me": (
                    "Preencha 'letra' com A, B, C, D ou E. Deixe vazio o que não der "
                    "para decidir. Depois: smedocs gabarito out/pendencias.json"
                ),
                "respostas": molde,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return markdown, molde_path, len(batch)


def read_submission(path: Path) -> dict[str, str]:
    """Lê um arquivo de respostas. Aceita o molde ou um mapa simples id -> letra."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "respostas" in raw:
        raw = raw["respostas"]
    return {
        str(key): str(value).strip().upper()
        for key, value in raw.items()
        if str(value).strip()
    }
