"""Recupera a estrutura que o Word nao tem.

O documento de origem tem 9.654 paragrafos e nenhum heading: tudo esta marcado como
estilo Normal. A estrutura existe so no padrao do texto. Ver CLAUDE.md.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .extract import GABARITO_COLORS, Block, ImageRun, TextRun
from .media import convert
from .models import Alternative, Descriptor, Fragment, Question


@dataclass
class Media:
    """Onde as imagens saem e de onde vem os recortes de formula feitos pelo Word."""

    assets_dir: Path
    eq_dir: Path | None = None
    equations: dict = field(default_factory=dict)

# Quatro formatos convivem no mesmo arquivo: "Descritor 1:", "D2:", "D3 -", "D8 –".
RE_DESCRIPTOR = re.compile(r"^\s*(?:DESCRITOR\s*|D\s*)(\d{1,2})\s*[:\-–—.]\s*(.*)", re.I)
# Fileira de asteriscos entre questoes. Comprimento varia de 18 a 50 caracteres.
RE_SEPARATOR = re.compile(r"^\*{3,}$")
# Duas formas de alternativa convivem: "A)" e "(A)".
RE_ALTERNATIVE = re.compile(r"^\s*\(?([A-Ea-e])[\)\.]\s*(.*)", re.S)
# Origem da questao, prefixo do enunciado: "(PROEB).", "(Saresp 2007)."
RE_SOURCE = re.compile(r"^\s*\(([^)]{2,40})\)\s*\.\s*(.*)", re.S)
RE_ACTIVITIES = re.compile(r"^\s*ATIVIDADES?\s+DOS?\s+DESCRITOR", re.I)
# Aberturas fixas do texto pedagogico que antecede as questoes de cada descritor.
RE_PEDAGOGICAL = re.compile(
    r"(Com este descritor|"
    r"Que (?:atividades|sugest[oõ]es) podem ser dadas|"
    r"A habilidade de o aluno|"
    r"Detalhamento\s*:|"
    r"Orienta[cç][oõ]es\s*:)",
    re.I,
)


def _is_separator(block: Block) -> bool:
    t = block.text.strip()
    return bool(t) and bool(RE_SEPARATOR.match(t))


# Sobras de tipografia do original: parenteses que ficaram vazios depois que o glifo
# decorativo saiu, e espacos duplicados por quebras de run.
RE_EMPTY_PARENS = re.compile(r"\(\s*\)")
RE_EXTRA_SPACE = re.compile(r"[ \t]{2,}")


def _clean(text: str) -> str:
    return RE_EXTRA_SPACE.sub(" ", RE_EMPTY_PARENS.sub("", text))


def _fragments(block: Block, z: zipfile.ZipFile, ctx: "Media") -> list[Fragment]:
    # Uma formula que divide o paragrafo com texto e inline; sozinha no paragrafo, e
    # formula de bloco. Esse e o sinal do proprio documento, e vale mais que qualquer
    # limite de altura: "sen(60°) = √3/2" no meio de uma frase e alto por causa da
    # fracao, mas continua sendo inline.
    inline_context = bool(block.text.strip())
    out: list[Fragment] = []
    for run in block.runs:
        if isinstance(run, TextRun):
            red = (run.color or "").upper() in GABARITO_COLORS
            # So funde runs de mesma cor: a fronteira do vermelho e o que identifica
            # a alternativa correta quando varias dividem o mesmo paragrafo.
            if out and out[-1].kind == "text" and out[-1].red == red:
                out[-1].text += run.text
            else:
                out.append(Fragment(kind="text", text=run.text, red=red))
        elif isinstance(run, ImageRun):
            asset = convert(
                z,
                run.part,
                run.width_pt,
                run.height_pt,
                run.is_ole,
                ctx.assets_dir,
                equations=ctx.equations,
                eq_dir=ctx.eq_dir,
            )
            out.append(
                Fragment(
                    kind="image",
                    asset=asset.filename,
                    width_pt=asset.width_pt,
                    height_pt=asset.height_pt,
                    inline=asset.inline and inline_context,
                )
            )
    for f in out:
        f.align = block.align
        if f.kind == "text":
            f.text = _clean(f.text)
    return out


# Alternativa comecando em qualquer ponto do texto, nao so no inicio do paragrafo.
RE_INLINE_ALTERNATIVE = re.compile(r"(?<![\w,])\(?([A-Ea-e])\)\s")


def _packed_letters(text: str) -> list[str]:
    """Letras de alternativa encontradas dentro de um mesmo paragrafo."""
    return [m.group(1).upper() for m in RE_INLINE_ALTERNATIVE.finditer(text)]


def _is_packed(text: str) -> bool:
    """Varias alternativas alinhadas por tabulacao num paragrafo so.

    Acontece quando as opcoes sao curtas ou sao imagens de formula. Sem tratar, a linha
    inteira virava a alternativa A, e o conteudo das outras aparecia como o texto "(B)".

    Bastam duas letras, desde que consecutivas: metade dos casos e um par "(A) (B)"
    seguido de outro paragrafo "(C) (D)".
    """
    letters = _packed_letters(text)
    if len(letters) < 2:
        return False
    first = ord(letters[0])
    return letters == [chr(first + i) for i in range(len(letters))]


def _split_packed(fragments: list[Fragment]) -> list[tuple[str, list[Fragment], bool]]:
    """Reparte os fragmentos de um paragrafo empacotado, um item por alternativa.

    O corte e no nivel do fragmento para nao perder as imagens: numa alternativa como
    "(A) <formula> (B) <formula>", cada imagem tem que ficar com a letra que a precede.

    O terceiro valor diz se o proprio rotulo estava em vermelho. Nesses paragrafos a
    marca de gabarito costuma cair sobre o "(C)" e nao sobre o conteudo, entao o rotulo
    e descartado do texto mas a cor dele tem que sobreviver.
    """
    groups: list[tuple[str, list[Fragment], bool]] = []

    for fragment in fragments:
        if fragment.kind != "text":
            if groups:
                groups[-1][1].append(fragment)
            continue

        cursor = 0
        for match in RE_INLINE_ALTERNATIVE.finditer(fragment.text):
            before = fragment.text[cursor : match.start()]
            if before.strip() and groups:
                groups[-1][1].append(fragment.model_copy(update={"text": before}))
            groups.append((match.group(1).upper(), [], fragment.red))
            cursor = match.end()

        tail = fragment.text[cursor:]
        if tail.strip() and groups:
            groups[-1][1].append(fragment.model_copy(update={"text": tail}))

    return groups


def _strip_alternative_label(fragments: list[Fragment]) -> list[Fragment]:
    """Remove o rotulo "A)" do inicio da alternativa.

    Nao da para olhar so o primeiro fragmento: o Word quebra o rotulo em runs — " (" e
    "C) " chegam separados, e quando a cor do gabarito cai sobre ele a fronteira de cor
    forca a quebra. O rotulo e removido percorrendo o fluxo de texto inteiro.
    """
    joined = "".join(f.text for f in fragments if f.kind == "text")
    m = RE_ALTERNATIVE.match(joined)
    if not m:
        return fragments

    remaining = m.start(2)
    out: list[Fragment] = []
    for f in fragments:
        if f.kind != "text" or remaining <= 0:
            out.append(f)
        elif len(f.text) <= remaining:
            remaining -= len(f.text)
        else:
            out.append(f.model_copy(update={"text": f.text[remaining:]}))
            remaining = 0
    return out


def _strip_source(fragments: list[Fragment]) -> tuple[str | None, list[Fragment]]:
    if not fragments or fragments[0].kind != "text":
        return None, fragments
    m = RE_SOURCE.match(fragments[0].text)
    if not m:
        return None, fragments
    rest = fragments[0].model_copy(update={"text": m.group(2)})
    return m.group(1).strip(), [rest] + fragments[1:]


def _build_question(
    blocks: list[Block], descriptor: int, seq: int, z, ctx: "Media"
) -> Question | None:
    """Monta uma questao a partir dos blocos entre dois cortes."""
    stem: list[Fragment] = []
    alternatives: list[Alternative] = []
    current: Alternative | None = None

    for block in blocks:
        text = block.text.strip()
        if not text and not block.images:
            continue
        if _is_separator(block) or RE_ACTIVITIES.match(text):
            continue

        m = RE_ALTERNATIVE.match(block.text) if text else None
        if m and _is_packed(text):
            # Quatro alternativas num paragrafo so, alinhadas por tabulacao.
            for letter, frags, label_red in _split_packed(_fragments(block, z, ctx)):
                current = Alternative(
                    letter=letter,
                    fragments=frags,
                    correct=label_red or any(f.red for f in frags),
                )
                alternatives.append(current)
        elif m:
            letter = m.group(1)
            frags = _strip_alternative_label(_fragments(block, z, ctx))
            current = Alternative(
                letter=letter, fragments=frags, correct=block.has_gabarito_color
            )
            alternatives.append(current)
        elif current is not None:
            # Continuacao da ultima alternativa (quebra de linha no meio dela).
            current.fragments.extend(_fragments(block, z, ctx))
        else:
            if stem:
                stem.append(Fragment(kind="break"))
            stem.extend(_fragments(block, z, ctx))

    if not alternatives:
        return None

    source, stem = _strip_source(stem)
    q = Question(
        id=f"D{descriptor:02d}-Q{seq:03d}",
        descriptor=descriptor,
        source=source,
        stem=stem,
        alternatives=alternatives,
    )
    q.needs_review = q.validate_shape()
    return q


def _split_block_at(block: Block, offset: int) -> tuple[Block, Block]:
    """Reparte um bloco num deslocamento do texto, preservando runs e imagens."""
    head, tail = Block(index=block.index, align=block.align), Block(
        index=block.index, align=block.align
    )
    seen = 0
    for run in block.runs:
        if not isinstance(run, TextRun):
            (head if seen < offset else tail).runs.append(run)
            continue
        end = seen + len(run.text)
        if end <= offset:
            head.runs.append(run)
        elif seen >= offset:
            tail.runs.append(run)
        else:
            cut = offset - seen
            head.runs.append(TextRun(run.text[:cut], run.bold, run.italic, run.color))
            tail.runs.append(TextRun(run.text[cut:], run.bold, run.italic, run.color))
        seen = end
    return head, tail


def _detach_glued_alternatives(blocks: list[Block]) -> list[Block]:
    """Solta a alternativa que ficou colada no fim do enunciado.

    O acervo tem casos como:

        "...Mario esta na posicao de qual numero inteiro? A) −3."
        "B) −2."
        "C) +2."

    A alternativa A esta dentro do paragrafo do enunciado. Sem soltar, a questao perde
    a letra A, o corte por reinicio em A nao dispara, e ela se funde com a questao
    anterior — o padrao "ABCDBCD" que aparecia no relatorio de pendencias.

    A confirmacao vem do bloco seguinte: so separa se ele comeca com a letra seguinte.
    """
    out: list[Block] = []
    for i, block in enumerate(blocks):
        text = block.text
        if text.strip() and not RE_ALTERNATIVE.match(text):
            following = next(
                (b.text.strip() for b in blocks[i + 1 :] if b.text.strip() or b.images),
                "",
            )
            for match in RE_INLINE_ALTERNATIVE.finditer(text):
                letter = match.group(1).upper()
                nxt = RE_ALTERNATIVE.match(following)
                if (
                    match.start() > 0
                    and nxt
                    and nxt.group(1).upper() == chr(ord(letter) + 1)
                ):
                    head, tail = _split_block_at(block, match.start())
                    out.extend([head, tail])
                    break
            else:
                out.append(block)
            continue
        out.append(block)
    return out


def _split_questions(blocks: list[Block]) -> list[list[Block]]:
    """Corta em questoes usando as duas regras juntas.

    Nenhuma funciona sozinha. So o separador produz 765 questoes, e alguns blocos
    ficam com ate 19 alternativas marcadas, porque o autor esqueceu os asteriscos.
    Separador mais reinicio da letra em A produz 864, que bate exatamente com as
    864 alternativas A contadas de forma independente.
    """
    groups: list[list[Block]] = []
    current: list[Block] = []
    last_letter: str | None = None

    for block in blocks:
        if _is_separator(block):
            if current:
                groups.append(current)
            current, last_letter = [], None
            continue

        m = RE_ALTERNATIVE.match(block.text) if block.text.strip() else None
        if m:
            letter = m.group(1).upper()
            if letter == "A" and last_letter is not None:
                # Os blocos depois da ultima alternativa da questao anterior sao o
                # enunciado desta, nao rodape daquela. Sem isso o enunciado cola na
                # questao errada e a nova nasce vazia.
                cut = 1 + max(
                    (
                        i
                        for i, b in enumerate(current)
                        if b.text.strip() and RE_ALTERNATIVE.match(b.text)
                    ),
                    default=len(current) - 1,
                )
                groups.append(current[:cut])
                current = current[cut:]
            last_letter = letter
        current.append(block)

    if current:
        groups.append(current)
    return [g for g in groups if g]


def segment(
    blocks: list[Block],
    z: zipfile.ZipFile,
    ctx: Media,
    only: set[int] | None = None,
) -> list[Descriptor]:
    """Devolve os descritores com suas questoes. `only` limita a numeros especificos."""
    # Corta o documento nos cabecalhos de descritor.
    starts: list[tuple[int, int, str]] = []
    for i, block in enumerate(blocks):
        m = RE_DESCRIPTOR.match(block.text.strip())
        if m and len(block.text.strip()) > 12:
            starts.append((i, int(m.group(1)), m.group(2).strip()))

    descriptors: list[Descriptor] = []
    for pos, (start, number, title) in enumerate(starts):
        if only is not None and number not in only:
            continue
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(blocks)
        body = blocks[start + 1 : end]

        # O texto pedagogico vai ate onde as questoes comecam. Tres pistas, e vale a
        # primeira que aparecer: o marcador "ATIVIDADES DO DESCRITOR N" (existe em 30
        # dos 31 descritores), a primeira fileira de asteriscos, ou a primeira
        # alternativa. A terceira e indispensavel: o descritor 1 nao tem marcador e sua
        # primeira questao vem antes do primeiro separador, entao sem ela a questao
        # inteira era absorvida pela caixa de introducao.
        def _first(pred) -> int:
            return next((i for i, b in enumerate(body) if pred(b)), len(body))

        by_marker = min(
            _first(lambda b: RE_ACTIVITIES.match(b.text.strip())),
            _first(_is_separator),
        )
        by_alternative = _first(
            lambda b: b.text.strip() and RE_ALTERNATIVE.match(b.text)
        )
        split_at = min(by_marker, by_alternative)

        # Quando so a alternativa marcou o limite, ela esta tarde demais: o enunciado
        # da questao ficou para tras, dentro da introducao. Recua ate logo depois da
        # ultima frase do texto pedagogico, que sempre usa uma destas aberturas.
        if by_alternative < by_marker:
            last_pedagogical = max(
                (
                    i
                    for i, b in enumerate(body[:split_at])
                    if RE_PEDAGOGICAL.search(b.text)
                ),
                default=None,
            )
            if last_pedagogical is not None:
                split_at = last_pedagogical + 1
        intro_blocks, question_blocks = body[:split_at], body[split_at:]

        intro: list[Fragment] = []
        for b in intro_blocks:
            if b.text.strip() or b.images:
                intro.extend(_fragments(b, z, ctx))
                intro.append(Fragment(kind="text", text="\n"))

        questions = []
        for seq, group in enumerate(_split_questions(_detach_glued_alternatives(question_blocks)), start=1):
            q = _build_question(group, number, seq, z, ctx)
            if q:
                questions.append(q)

        descriptors.append(
            Descriptor(number=number, title=title, intro=intro, questions=questions)
        )

    return descriptors
