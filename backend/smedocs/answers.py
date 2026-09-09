"""Gabarito preenchido à mão, por fora do documento de origem.

219 das 868 questões não têm nenhuma marcação vermelha no `.docx`. O gabarito delas
não existe no arquivo — não é falha de leitura, é ausência na origem.

Como não há orçamento de API, o app não adivinha nada em tempo de execução. O caminho é
outro: `smedocs pendencias` exporta as questões sem resposta num pacote de revisão, uma
sessão do Claude Code (ou uma pessoa) resolve o lote, e `smedocs gabarito` traz o
resultado de volta. O arquivo fica versionado junto com o código, então o trabalho é
feito uma vez e vale para sempre.

A sobreposição nunca contradiz o documento: só preenche o que estava vazio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Descriptor

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "gabarito" / "respostas.json"


@dataclass
class Answer:
    letter: str
    source: str = "claude-code"
    note: str = ""
    when: str = ""


class AnswerSheet:
    """Mapa de id da questão para a letra correta."""

    def __init__(self, entries: dict[str, Answer] | None = None) -> None:
        self.entries: dict[str, Answer] = entries or {}

    @classmethod
    def load(cls, path: Path | None = None) -> "AnswerSheet":
        path = Path(path or DEFAULT_PATH)
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            {
                key: Answer(
                    letter=value["letra"],
                    source=value.get("origem", "claude-code"),
                    note=value.get("nota", ""),
                    when=value.get("quando", ""),
                )
                for key, value in raw.get("respostas", {}).items()
            }
        )

    def save(self, path: Path | None = None) -> Path:
        path = Path(path or DEFAULT_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_leia_me": (
                "Gabarito preenchido por fora do .docx, para as questões que não têm "
                "marcação vermelha na origem. Gerado e consumido por smedocs."
            ),
            "respostas": {
                key: {
                    "letra": answer.letter,
                    "origem": answer.source,
                    "nota": answer.note,
                    "quando": answer.when,
                }
                for key, answer in sorted(self.entries.items())
            },
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return path

    def merge(self, other: dict[str, str], source: str = "claude-code", note: str = "") -> int:
        """Acrescenta respostas novas. Devolve quantas entraram."""
        today = date.today().isoformat()
        added = 0
        for key, letter in other.items():
            letter = (letter or "").strip().upper()
            if letter not in "ABCDE" or len(letter) != 1:
                continue
            if key in self.entries:
                continue
            self.entries[key] = Answer(letter, source, note, today)
            added += 1
        return added


def apply(descriptors: list[Descriptor], sheet: AnswerSheet) -> int:
    """Marca as alternativas indicadas pela sobreposição. Devolve quantas aplicou."""
    applied = 0
    for descriptor in descriptors:
        for question in descriptor.questions:
            answer = sheet.entries.get(question.id)
            if not answer:
                continue
            # Nunca sobrescreve o documento: só age onde a origem não marcou nada.
            if any(a.correct for a in question.alternatives):
                continue
            for alternative in question.alternatives:
                if alternative.letter == answer.letter:
                    alternative.correct = True
                    alternative.from_overlay = True
                    applied += 1
                    break
            question.needs_review = question.validate_shape()
    return applied


def pending(descriptors: list[Descriptor]) -> list:
    """Questões que continuam sem gabarito depois da sobreposição."""
    return [
        question
        for descriptor in descriptors
        for question in descriptor.questions
        if not question.answer and len(question.alternatives) >= 2
    ]
