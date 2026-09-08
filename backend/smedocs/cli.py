"""Interface de linha de comando do SMEDocs.

Sem argumento, entra no modo interativo e pergunta o que gerar. Com argumento, roda
direto e sai — o que serve para script e para automacao.

    smedocs                     modo interativo
    smedocs listar              tabela dos descritores
    smedocs gerar 10            descritor 10 em PDF
    smedocs gerar 10 -f docx    so DOCX
    smedocs gerar --tudo        todos os descritores
    smedocs conferir 10         so o relatorio, sem gerar arquivo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from . import pipeline
from .models import Descriptor

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCX = ROOT / "reference" / "APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx"
DEFAULT_OUT = ROOT / "out"

console = Console()
app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    help="Converte o banco de questões em apostila diagramada.",
)

AZUL = "#1b56c4"
VERDE = "#3fa34d"
VERMELHO = "#e63946"


def _resolve(docx: Path | None) -> Path:
    path = docx or DEFAULT_DOCX
    if not path.exists():
        console.print(
            f"[{VERMELHO}]Documento não encontrado:[/] {path}\n"
            f"Coloque o .docx em [bold]reference/[/] ou passe [bold]--docx[/]."
        )
        raise typer.Exit(1)
    return path


def _banner() -> None:
    console.print()
    console.print(
        Text("  SMEDocs  ", style=f"bold white on {AZUL}")
        + Text("  banco de questões → apostila diagramada", style="dim")
    )
    console.print()


def _stats_panel(result: pipeline.Result) -> Panel:
    stats = result.stats
    body = Table.grid(padding=(0, 2))
    body.add_column(justify="right", style="dim")
    body.add_column()

    body.add_row("questões", f"[bold]{stats.questions}[/]")
    body.add_row(
        "gabarito automático",
        f"[bold]{stats.with_key}[/] [dim]({stats.key_percent}%)[/]",
    )
    body.add_row(
        "sem pendência",
        f"[{VERDE}]{stats.clean}[/] [dim]({stats.clean_percent}%)[/]",
    )
    body.add_row("imagens", f"{stats.images}")
    if stats.formulas:
        origem = "pelo Word" if result.word_used else "[yellow]pelo GDI[/]"
        body.add_row("fórmulas inline", f"{stats.formulas} [dim]{origem}[/]")

    if stats.pending:
        body.add_row("", "")
        for key, count in sorted(stats.pending.items(), key=lambda kv: -kv[1]):
            body.add_row(f"[{VERMELHO}]{count}[/]", f"[dim]{key}[/]")

    return Panel(body, title="resultado", border_style=AZUL, title_align="left")


def _report(result: pipeline.Result) -> None:
    console.print(_stats_panel(result))
    for path in result.outputs:
        size = path.stat().st_size / 1_000_000
        console.print(f"  [{VERDE}]✓[/] {path}  [dim]({size:.1f} MB)[/]")
    console.print(f"  [dim]{result.elapsed:.1f}s[/]")
    console.print()


def _run(
    docx: Path,
    numbers: set[int] | None,
    formats: tuple[str, ...],
    show_key: bool,
    out: Path,
    quiet: bool,
    use_word: bool,
) -> pipeline.Result:
    if quiet:
        return pipeline.build(
            docx, out, numbers, formats, use_word=use_word, show_key=show_key
        )
    with Progress(
        SpinnerColumn(style=AZUL),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("preparando", total=None)
        return pipeline.build(
            docx,
            out,
            numbers,
            formats,
            use_word=use_word,
            show_key=show_key,
            on_step=lambda message: progress.update(task, description=message),
        )


def _catalog(docx: Path, out: Path) -> list[Descriptor]:
    with Progress(
        SpinnerColumn(style=AZUL),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("lendo o documento", total=None)
        descriptors, _, _ = pipeline.load(
            docx, out, None, True, lambda m: progress.update(task, description=m)
        )
    return descriptors


def _catalog_table(descriptors: list[Descriptor]) -> Table:
    table = Table(box=None, pad_edge=False, header_style="dim")
    table.add_column("#", justify="right", style=AZUL)
    table.add_column("descritor")
    table.add_column("questões", justify="right")
    table.add_column("gabarito", justify="right")
    table.add_column("pendências", justify="right")

    for descriptor in descriptors:
        total = len(descriptor.questions)
        with_key = sum(1 for q in descriptor.questions if q.answer)
        pending = sum(1 for q in descriptor.questions if q.needs_review)
        percent = with_key * 100 // total if total else 0
        cor = VERDE if percent == 100 else ("yellow" if percent >= 70 else VERMELHO)
        table.add_row(
            str(descriptor.number),
            Text(descriptor.title, overflow="ellipsis", no_wrap=True)[:62],
            str(total),
            f"[{cor}]{percent}%[/]",
            f"[dim]—[/]" if not pending else f"[{VERMELHO}]{pending}[/]",
        )
    return table


@app.command("listar")
def listar(
    docx: Path = typer.Option(None, "--docx", help="Arquivo .docx de origem."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de trabalho."),
    formato: str = typer.Option("tabela", "-f", "--formato", help="tabela | json"),
) -> None:
    """Mostra todos os descritores do documento com sua situação."""
    source = _resolve(docx)
    descriptors = _catalog(source, out)

    if formato == "json":
        payload = [
            {
                "numero": d.number,
                "titulo": d.title,
                "questoes": len(d.questions),
                "com_gabarito": sum(1 for q in d.questions if q.answer),
                "pendencias": sum(1 for q in d.questions if q.needs_review),
            }
            for d in descriptors
        ]
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    _banner()
    console.print(_catalog_table(descriptors))
    total = sum(len(d.questions) for d in descriptors)
    console.print(f"\n  [dim]{len(descriptors)} descritores · {total} questões[/]\n")


@app.command("gerar")
def gerar(
    descritores: list[int] = typer.Argument(None, help="Números dos descritores."),
    tudo: bool = typer.Option(False, "--tudo", help="Todos os descritores."),
    formato: list[str] = typer.Option(
        ["pdf"], "-f", "--formato", help="pdf, docx. Repita para os dois."
    ),
    sem_gabarito: bool = typer.Option(
        False, "--sem-gabarito", help="Versão do aluno, sem as respostas."
    ),
    docx: Path = typer.Option(None, "--docx", help="Arquivo .docx de origem."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de saída."),
    sem_word: bool = typer.Option(
        False, "--sem-word", help="Não usar o Word para as fórmulas."
    ),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Sem barra de progresso."),
) -> None:
    """Gera a apostila de um ou mais descritores."""
    source = _resolve(docx)
    if not descritores and not tudo:
        console.print(
            f"[{VERMELHO}]Diga quais descritores.[/] "
            f"Exemplo: [bold]smedocs gerar 10[/] ou [bold]smedocs gerar --tudo[/]"
        )
        raise typer.Exit(1)

    invalid = [f for f in formato if f not in ("pdf", "docx")]
    if invalid:
        console.print(f"[{VERMELHO}]Formato desconhecido:[/] {', '.join(invalid)}")
        raise typer.Exit(1)

    if not quiet:
        _banner()

    result = _run(
        source,
        None if tudo else set(descritores),
        tuple(formato),
        not sem_gabarito,
        out,
        quiet,
        not sem_word,
    )

    if quiet:
        for path in result.outputs:
            print(path)
        return
    _report(result)


@app.command("conferir")
def conferir(
    descritores: list[int] = typer.Argument(None, help="Números dos descritores."),
    docx: Path = typer.Option(None, "--docx", help="Arquivo .docx de origem."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de trabalho."),
) -> None:
    """Relatório das pendências, sem gerar arquivo nenhum."""
    source = _resolve(docx)
    _banner()
    result = _run(
        source, set(descritores) if descritores else None, (), True, out, False, True
    )
    console.print(_stats_panel(result))

    problems = [
        q
        for d in result.descriptors
        for q in d.questions
        if q.needs_review and "sem gabarito" not in q.needs_review
    ]
    if problems:
        table = Table(box=None, header_style="dim", pad_edge=False)
        table.add_column("questão", style=AZUL)
        table.add_column("problema")
        table.add_column("enunciado", overflow="ellipsis", no_wrap=True)
        for question in problems[:40]:
            stem = "".join(f.text for f in question.stem).strip()
            table.add_row(
                question.id, "; ".join(question.needs_review), stem[:58] or "—"
            )
        console.print()
        console.print(table)
        if len(problems) > 40:
            console.print(f"  [dim]e mais {len(problems) - 40}[/]")
    console.print()


def _interactive() -> None:
    """Modo padrão: pergunta o que fazer."""
    source = _resolve(None)
    _banner()
    descriptors = _catalog(source, DEFAULT_OUT)
    console.print(_catalog_table(descriptors))

    numbers = {d.number for d in descriptors}
    console.print()
    escolha = typer.prompt(
        "  Qual descritor? (número, vários separados por espaço, ou 'tudo')",
        default="1",
    ).strip()

    if escolha.lower() in ("tudo", "todos", "all"):
        chosen = None
    else:
        try:
            chosen = {int(x) for x in escolha.split()}
        except ValueError:
            console.print(f"  [{VERMELHO}]Não entendi.[/]")
            raise typer.Exit(1)
        desconhecidos = chosen - numbers
        if desconhecidos:
            console.print(
                f"  [{VERMELHO}]Não existe:[/] "
                f"{', '.join(str(n) for n in sorted(desconhecidos))}"
            )
            raise typer.Exit(1)

    formato = typer.prompt(
        "  Formato? (pdf, docx, ambos)", default="pdf"
    ).strip().lower()
    formats = ("pdf", "docx") if formato in ("ambos", "os dois") else (formato,)
    if any(f not in ("pdf", "docx") for f in formats):
        console.print(f"  [{VERMELHO}]Formato desconhecido.[/]")
        raise typer.Exit(1)

    console.print()
    _report(_run(source, chosen, formats, True, DEFAULT_OUT, False, True))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _interactive()


def run() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n  [dim]cancelado[/]\n")
        sys.exit(130)


if __name__ == "__main__":
    run()
