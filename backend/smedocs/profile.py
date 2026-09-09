"""Perfil de ingestão parametrizado.

Troca as constantes `RE_*` / `GABARITO_COLORS` fixas em `segment.py`/`extract.py`
por um `IngestionProfile` (Pydantic) validável e versionável em `profiles/*.json`.

O preset `PRESET_MURIAE` reproduz byte a byte os valores fixos antigos, então
rodar sem `--perfil` mantém a saída (31 descritores, 868 questões, 647 gabaritos).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

# Campos de regex do perfil, na ordem declarada no modelo.
REGEX_FIELDS = (
    "separator_regex",
    "descriptor_regex",
    "section_regex",
    "pedagogical_regex",
    "alternative_regex",
    "alternative_inline_regex",
    "source_regex",
    "dingbat_regex",
    "empty_parens_regex",
    "extra_space_regex",
)

# Flags que o código antigo usava em cada padrão. Mantidas aqui para que o
# preset compile exatamente como os `re.compile` originais.
_REGEX_FLAGS: dict[str, int] = {
    "separator_regex": 0,
    "descriptor_regex": re.IGNORECASE,
    "section_regex": re.IGNORECASE,
    "pedagogical_regex": re.IGNORECASE,
    "alternative_regex": re.DOTALL,
    "alternative_inline_regex": 0,
    "source_regex": re.DOTALL,
    "dingbat_regex": 0,
    "empty_parens_regex": 0,
    "extra_space_regex": 0,
}


class IngestionProfile(BaseModel):
    """Regras de parsing de um `.docx` pedagógico.

    14 campos: nome + 10 padrões regex + cores de gabarito + letras de
    alternativa + tamanho mínimo do cabeçalho de descritor.
    """

    name: str = Field(min_length=1)
    separator_regex: str = Field(min_length=1)
    descriptor_regex: str = Field(min_length=1)
    section_regex: str = Field(min_length=1)
    pedagogical_regex: str = Field(min_length=1)
    alternative_regex: str = Field(min_length=1)
    alternative_inline_regex: str = Field(min_length=1)
    source_regex: str = Field(min_length=1)
    dingbat_regex: str = Field(min_length=1)
    empty_parens_regex: str = Field(min_length=1)
    extra_space_regex: str = Field(min_length=1)
    gabarito_colors: list[str] = Field(min_length=1)
    alternative_letters: str = Field(min_length=2)
    descriptor_min_text_len: int = Field(default=12, ge=1)

    # Metadados opcionais, fora da contagem dos 14 campos.
    description: str = ""

    @field_validator("gabarito_colors")
    @classmethod
    def _upper_colors(cls, v: list[str]) -> list[str]:
        return [c.strip().upper() for c in v]

    @field_validator("alternative_letters")
    @classmethod
    def _upper_letters(cls, v: str) -> str:
        v = v.strip().upper()
        if len(set(v)) != len(v):
            raise ValueError(f"letras de alternativa repetidas: {v!r}")
        return v

    def validate_regexes(self) -> None:
        """Compila os 10 padrões com as flags históricas.

        Raises:
            ValueError: com o nome do campo quando um padrão é inválido.
        """
        for field in REGEX_FIELDS:
            pattern = getattr(self, field)
            try:
                re.compile(pattern, _REGEX_FLAGS[field])
            except re.error as e:
                raise ValueError(f"perfil inválido no campo {field}: {e}") from e

    def compiled(self, field: str) -> "re.Pattern[str]":
        """Devolve um padrão compilado com as flags históricas."""
        return re.compile(getattr(self, field), _REGEX_FLAGS[field])

    @property
    def color_set(self) -> set[str]:
        return set(self.gabarito_colors)

    @property
    def first_letter(self) -> str:
        return self.alternative_letters[0]

    def expected_sequence(self, n: int) -> list[str]:
        return list(self.alternative_letters[:n])

    @classmethod
    def from_json(cls, path: str | Path) -> "IngestionProfile":
        """Carrega e valida um perfil de `profiles/*.json`."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        profile = cls.model_validate(data)
        profile.validate_regexes()
        return profile

    def to_json(self, path: str | Path) -> Path:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(self.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return dest


PRESET_MURIAE = IngestionProfile(
    name="banco-muriae",
    description=(
        "Banco de questões de Muriaé: separador de asteriscos, cabeçalhos "
        "Descritor/D, alternativas A)/ (A), origem entre parênteses, gabarito "
        "em vermelho FF0000/EE0000."
    ),
    separator_regex=r"^\*{3,}$",
    descriptor_regex=r"^\s*(?:DESCRITOR\s*|D\s*)(\d{1,2})\s*[:\-–—.]\s*(.*)",
    section_regex=r"^\s*ATIVIDADES?\s+DOS?\s+DESCRITOR",
    pedagogical_regex=(
        r"(Com este descritor|"
        r"Que (?:atividades|sugest[oõ]es) podem ser dadas|"
        r"A habilidade de o aluno|"
        r"Detalhamento\s*:|"
        r"Orienta[cç][oõ]es\s*:)"
    ),
    alternative_regex=r"^\s*\(?([A-Ea-e])[\)\.]\s*(.*)",
    alternative_inline_regex=r"(?<![\w,])\(?([A-Ea-e])\)\s",
    source_regex=r"^\s*\(([^)]{2,40})\)\s*\.\s*(.*)",
    dingbat_regex=r"[☺☻]+",
    empty_parens_regex=r"\(\s*\)",
    extra_space_regex=r"[ \t]{2,}",
    gabarito_colors=["FF0000", "EE0000"],
    alternative_letters="ABCDE",
    descriptor_min_text_len=12,
)
