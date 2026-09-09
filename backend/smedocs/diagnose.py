"""Diagnóstico de ingestão: contagens por regra de parsing.

Diz, para um `.docx` qualquer e um perfil, quantos blocos casaram cada regra
(separador, descritor, seção, alternativas A–E, cor de gabarito) e cruza o nº de
alternativas A com o nº de questões segmentadas — a validação que prova que a
segmentação está correta no banco Muriaé (864 A == 864 questões).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import Block
from .models import Descriptor
from .profile import PRESET_MURIAE, IngestionProfile


@dataclass
class Diagnosis:
    profile_name: str
    first_letter: str = "A"
    separators: int = 0
    descriptor_hits: list[int] = field(default_factory=list)
    sections: int = 0
    alternatives: dict[str, int] = field(default_factory=dict)
    red_blocks: int = 0
    red_alternatives: int = 0
    questions: int = 0
    questions_with_first: int = 0
    no_first_ids: list[str] = field(default_factory=list)
    with_key: int = 0
    pending: dict[str, int] = field(default_factory=dict)

    @property
    def first_count(self) -> int:
        return self.alternatives.get(self.first_letter, 0)

    @property
    def cross_ok(self) -> bool:
        """Cada bloco-A virou exatamente uma alternativa-A em uma questão.

        Comparar com o total de questões dá falso alarme: questões degeneradas
        sem a primeira letra existem (ex. D28-Q049, só a alternativa C) e já
        caem em `needs_review`. O gate preciso é blocos-A == questões-com-A.
        """
        return bool(self.questions) and self.first_count == self.questions_with_first


def diagnose_blocks(
    blocks: list[Block], profile: IngestionProfile | None = None
) -> Diagnosis:
    """Conta os casamentos de cada regra sobre os blocos crus do `extract`."""
    from .segment import detach_glued

    profile = profile or PRESET_MURIAE
    colors = profile.color_set
    diag = Diagnosis(profile_name=profile.name, first_letter=profile.first_letter)

    separator = profile.compiled("separator_regex")
    descriptor = profile.compiled("descriptor_regex")
    section = profile.compiled("section_regex")
    alternative = profile.compiled("alternative_regex")

    for block in blocks:
        text = block.text.strip()
        if text and separator.match(text):
            diag.separators += 1
        if text:
            m = descriptor.match(text)
            if m and len(text) > profile.descriptor_min_text_len:
                try:
                    diag.descriptor_hits.append(int(m.group(1)))
                except (IndexError, ValueError):
                    pass
            if section.match(text):
                diag.sections += 1
        if block.has_gabarito_color_in(colors):
            diag.red_blocks += 1

    # As alternativas contam-se nos blocos DEPOIS do descolamento: a letra A às
    # vezes vem colada no fim do enunciado ("...inteiro? A) −3."), e sem soltar
    # a contagem independente fica em 864 contra 868 questões segmentadas.
    for block in detach_glued(blocks, profile):
        m = alternative.match(block.text)
        if m:
            letter = m.group(1).upper()
            diag.alternatives[letter] = diag.alternatives.get(letter, 0) + 1
            if block.has_gabarito_color_in(colors):
                diag.red_alternatives += 1

    return diag


def diagnose_questions(
    diag: Diagnosis, descriptors: list[Descriptor]
) -> Diagnosis:
    """Completa o diagnóstico com o resultado da segmentação."""
    questions = [q for d in descriptors for q in d.questions]
    diag.questions = len(questions)
    diag.questions_with_first = sum(
        1
        for q in questions
        if any(a.letter == diag.first_letter for a in q.alternatives)
    )
    diag.no_first_ids = [
        q.id
        for q in questions
        if not any(a.letter == diag.first_letter for a in q.alternatives)
    ]
    diag.with_key = sum(1 for q in questions if q.answer)
    for question in questions:
        for problem in question.needs_review:
            key = problem.split(":")[0]
            diag.pending[key] = diag.pending.get(key, 0) + 1
    return diag
