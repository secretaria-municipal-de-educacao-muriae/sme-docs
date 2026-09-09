"""Contratos de dados. Equivalente do Zod: define a forma e reclama quando foge dela."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Fragment(BaseModel):
    """Pedaco de conteudo dentro de um enunciado ou alternativa.

    `kind` tambem aceita "break", que marca fim de paragrafo dentro do enunciado.
    `red` carrega a cor de gabarito do run de origem: quando quatro alternativas vem
    empacotadas num paragrafo so, a marcacao vermelha do bloco inteiro nao diz qual
    delas e a certa, e so a cor por fragmento resolve.
    """

    kind: str  # "text" | "image" | "break"
    text: str = ""
    asset: str | None = None
    width_pt: float = 0
    height_pt: float = 0
    inline: bool = False
    red: bool = False
    align: str | None = None


class Alternative(BaseModel):
    letter: str
    fragments: list[Fragment] = Field(default_factory=list)
    correct: bool = False
    # Marcada pelo gabarito preenchido a mao, nao pela cor vermelha do documento.
    from_overlay: bool = False

    @field_validator("letter")
    @classmethod
    def upper_single(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 1 or v not in "ABCDE":
            raise ValueError(f"letra de alternativa invalida: {v!r}")
        return v

    @property
    def text(self) -> str:
        return "".join(f.text for f in self.fragments)


class Question(BaseModel):
    id: str
    descriptor: int
    source: str | None = None
    stem: list[Fragment] = Field(default_factory=list)
    alternatives: list[Alternative] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)

    @property
    def answer(self) -> str | None:
        marked = [a.letter for a in self.alternatives if a.correct]
        return marked[0] if len(marked) == 1 else None

    @property
    def stem_paragraphs(self) -> list[list[Fragment]]:
        """Enunciado dividido nos paragrafos originais do Word.

        Sem isso, um titulo de secao encostado na pergunta sai grudado, do tipo
        "...TRIANGULO RETANGULOPara se deslocar de sua casa...".
        """
        out: list[list[Fragment]] = [[]]
        for f in self.stem:
            if f.kind == "break":
                out.append([])
            else:
                out[-1].append(f)
        return [p for p in out if any(x.text.strip() or x.kind == "image" for x in p)]

    @property
    def image_count(self) -> int:
        n = sum(1 for f in self.stem if f.kind == "image")
        return n + sum(
            1 for a in self.alternatives for f in a.fragments if f.kind == "image"
        )

    def validate_shape(self) -> list[str]:
        """Regras duras. O que falhar vai para revisao humana, nunca para o chute."""
        problems = []
        if not "".join(f.text for f in self.stem).strip() and not any(
            f.kind == "image" for f in self.stem
        ):
            problems.append("enunciado vazio")
        letters = [a.letter for a in self.alternatives]
        if len(letters) < 4:
            problems.append(f"apenas {len(letters)} alternativas")
        if len(set(letters)) != len(letters):
            problems.append("letras repetidas")
        expected = [chr(ord("A") + i) for i in range(len(letters))]
        if letters != expected:
            problems.append(f"letras fora de sequencia: {''.join(letters)}")
        marked = sum(1 for a in self.alternatives if a.correct)
        if marked == 0:
            problems.append("sem gabarito")
        elif marked > 1:
            problems.append(f"{marked} alternativas marcadas")
        return problems


class Descriptor(BaseModel):
    number: int
    title: str
    intro: list[Fragment] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
