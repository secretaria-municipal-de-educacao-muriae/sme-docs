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
import shutil
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from . import answers, pipeline, render, review
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
        "com gabarito",
        f"[bold]{stats.with_key}[/] [dim]({stats.key_percent}%)[/]",
    )
    if stats.from_overlay:
        body.add_row("[dim]dos quais à mão[/]", f"[dim]{stats.from_overlay}[/]")
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
    # Uma linha por descritor: o titulo quebrado em duas dobra a altura da tabela e
    # o painel do `dev` deixa de caber na tela.
    table.add_column("descritor", no_wrap=True, overflow="ellipsis", max_width=52)
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
            descriptor.title.rstrip(" ,;.-"),
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



REFERENCE_DIR = ROOT / "reference"


@app.command("analisar")
def analisar(
    arquivo: Path = typer.Argument(..., help="Um .docx qualquer para inspecionar."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de trabalho."),
    copiar: bool = typer.Option(
        False, "--copiar", help="Copia o arquivo para reference/ ao terminar."
    ),
) -> None:
    """Lê um .docx novo e diz o que dá para aproveitar dele."""
    if not arquivo.exists():
        console.print(f"[{VERMELHO}]Não encontrei:[/] {arquivo}")
        raise typer.Exit(1)

    _banner()
    console.print(f"  [dim]{arquivo}  ({arquivo.stat().st_size / 1_000_000:.1f} MB)[/]\n")
    descriptors = _catalog(arquivo, out)

    if not descriptors:
        console.print(
            f"  [{VERMELHO}]Nenhum descritor reconhecido.[/]\n"
            "  O leitor procura cabeçalhos como [bold]Descritor 1:[/], [bold]D2:[/] ou\n"
            "  [bold]D3 -[/]. Se este documento usa outro padrão, ele precisa de uma\n"
            "  regra nova em segment.py.\n"
        )
        raise typer.Exit(1)

    console.print(_catalog_table(descriptors))
    total = sum(len(d.questions) for d in descriptors)
    sem_gabarito = sum(1 for d in descriptors for q in d.questions if not q.answer)
    console.print(
        f"\n  [dim]{len(descriptors)} descritores · {total} questões · "
        f"{sem_gabarito} sem gabarito[/]\n"
    )

    if copiar:
        REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
        destino = REFERENCE_DIR / arquivo.name
        if destino.resolve() != arquivo.resolve():
            shutil.copy(arquivo, destino)
        console.print(f"  [{VERDE}]✓[/] copiado para {destino}\n")


@app.command("pendencias")
def pendencias(
    limite: int = typer.Option(0, "--limite", "-n", help="Quantas por lote. 0 = todas."),
    docx: Path = typer.Option(None, "--docx", help="Arquivo .docx de origem."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de saída."),
) -> None:
    """Exporta as questões sem gabarito para revisão fora do app."""
    source = _resolve(docx)
    _banner()
    descriptors = _catalog(source, out)
    faltando = answers.pending(descriptors)

    if not faltando:
        console.print(f"  [{VERDE}]Nenhuma pendência. Todas as questões têm gabarito.[/]\n")
        return

    markdown, molde, quantidade = review.export(
        descriptors, faltando, out, out / "assets", limite or None
    )
    console.print(
        f"  [bold]{quantidade}[/] questões neste lote, de {len(faltando)} pendentes\n"
    )
    console.print(f"  [{VERDE}]✓[/] {markdown}   [dim]leia este[/]")
    console.print(f"  [{VERDE}]✓[/] {molde}   [dim]preencha este[/]\n")
    console.print("  [dim]Depois:[/] [bold]smedocs gabarito out/pendencias.json[/]\n")


@app.command("modelos")
def modelos(
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de saída."),
    pdf: bool = typer.Option(True, "--pdf/--sem-pdf", help="Imprimir o PDF também."),
) -> None:
    """Gera o catálogo de modelos de página da apostila de educação infantil."""
    _banner()
    paginas = render.catalogo_infantil()
    html = render.render_infantil(paginas, out)
    console.print(f"  [bold]{len(paginas)}[/] modelos")
    console.print(f"  [{VERDE}]✓[/] {html}")
    if pdf:
        destino = render.print_pdf(html, out / "modelos-infantil.pdf")
        console.print(f"  [{VERDE}]✓[/] {destino}")
    console.print()


@app.command("apostila")
def apostila(
    plano: Path = typer.Argument(..., help="JSON com as páginas escolhidas."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de saída."),
    pdf: bool = typer.Option(True, "--pdf/--sem-pdf", help="Imprimir o PDF também."),
) -> None:
    """Monta a apostila infantil a partir de um plano de páginas.

    O plano é uma lista de {"modelo": "M05", "dados": {...}} — os campos de `dados`
    são os `slots` do modelo em modelos_infantil.json. A escolha do modelo para cada
    atividade é feita fora daqui, numa sessão do Claude Code lendo o PDF da professora;
    em tempo de execução nada é adivinhado.
    """
    if not plano.exists():
        console.print(f"[{VERMELHO}]Não encontrei:[/] {plano}")
        raise typer.Exit(1)

    _banner()
    paginas = json.loads(plano.read_text(encoding="utf-8"))
    if isinstance(paginas, dict):
        paginas = paginas["paginas"]

    conhecidos = {m["modelo"] for m in render.catalogo_infantil()}
    for i, pagina in enumerate(paginas, 1):
        if pagina.get("modelo") not in conhecidos:
            console.print(
                f"[{VERMELHO}]Página {i}:[/] modelo {pagina.get('modelo')!r} não existe. "
                f"Use um destes: {', '.join(sorted(conhecidos))}"
            )
            raise typer.Exit(1)

    html = render.render_infantil(
        paginas, out, ficha=False, filename="apostila-infantil.html",
        titulo_arquivo="Apostila — Educação Infantil",
    )
    console.print(f"  [bold]{len(paginas)}[/] páginas")
    console.print(f"  [{VERDE}]✓[/] {html}")
    if pdf:
        console.print(f"  [{VERDE}]✓[/] {render.print_pdf(html, out / 'apostila-infantil.pdf')}")
    console.print()


@app.command("svg")
def svg(
    pdf: Path = typer.Argument(None, help="PDF de origem. Padrão: out/modelos-infantil.pdf"),
    out: Path = typer.Option(None, "--out", help="Pasta de saída. Padrão: <pdf>/svg"),
    curvas: bool = typer.Option(
        False, "--curvas", help="Converter o texto em contorno (não fica mais editável)."
    ),
) -> None:
    """Exporta cada página do PDF como SVG vetorial.

    O PDF já é vetor e abre direto no Illustrator; isto serve para editar no Figma,
    no Inkscape ou no navegador.
    """
    origem = pdf or (DEFAULT_OUT / "modelos-infantil.pdf")
    if not origem.exists():
        console.print(f"[{VERMELHO}]Não encontrei:[/] {origem}")
        raise typer.Exit(1)

    _banner()
    arquivos = render.export_svg(origem, out or origem.parent / "svg", curvas)
    console.print(f"  [bold]{len(arquivos)}[/] páginas em SVG")
    console.print(f"  [{VERDE}]✓[/] {arquivos[0].parent}")
    if not curvas:
        console.print("  [dim]texto continua editável; use --curvas para virar contorno[/]")
    console.print()


@app.command("gabarito")
def gabarito(
    arquivo: Path = typer.Argument(..., help="JSON com as respostas preenchidas."),
    origem: str = typer.Option("claude-code", "--origem", help="Quem respondeu."),
    nota: str = typer.Option("", "--nota", help="Observação guardada junto."),
) -> None:
    """Importa respostas preenchidas para o gabarito do projeto."""
    if not arquivo.exists():
        console.print(f"[{VERMELHO}]Não encontrei:[/] {arquivo}")
        raise typer.Exit(1)

    _banner()
    sheet = answers.AnswerSheet.load()
    antes = len(sheet.entries)
    novas = sheet.merge(review.read_submission(arquivo), source=origem, note=nota)
    destino = sheet.save()

    console.print(f"  [{VERDE}]+{novas}[/] respostas novas")
    console.print(f"  [dim]{antes} antes · {len(sheet.entries)} agora[/]")
    console.print(f"  [{VERDE}]✓[/] {destino}\n")


def _dev_screen(source: Path, out: Path) -> Layout:
    descriptors = pipeline.load(source, out)[0]
    stats = pipeline.summarize(descriptors)
    faltando = answers.pending(descriptors)

    cabecalho = Table.grid(padding=(0, 2))
    cabecalho.add_column()
    cabecalho.add_row(
        Text("  SMEDocs  ", style=f"bold white on {AZUL}")
        + Text(f"  {source.name}", style="dim")
        + Text(f"  ·  {source.stat().st_size / 1_000_000:.1f} MB", style="dim")
    )

    acervo = Table.grid(padding=(0, 3))
    acervo.add_column(justify="right", style="dim")
    acervo.add_column()
    acervo.add_row("descritores", f"[bold]{len(descriptors)}[/]")
    acervo.add_row("questões", f"[bold]{stats.questions}[/]")
    acervo.add_row(
        "com gabarito", f"[{VERDE}]{stats.with_key}[/] [dim]({stats.key_percent}%)[/]"
    )
    if stats.from_overlay:
        acervo.add_row("preenchidas à mão", f"[dim]{stats.from_overlay}[/]")
    acervo.add_row("fórmulas", f"[dim]{stats.formulas}[/]")

    afazeres = Table.grid(padding=(0, 2))
    afazeres.add_column(justify="right")
    afazeres.add_column()
    if faltando:
        afazeres.add_row(
            f"[{VERMELHO}]{len(faltando)}[/]",
            "sem gabarito   [dim]smedocs pendencias -n 20[/]",
        )
    estruturais = {k: v for k, v in stats.pending.items() if k != "sem gabarito"}
    for chave, quantidade in sorted(estruturais.items(), key=lambda kv: -kv[1]):
        afazeres.add_row(f"[yellow]{quantidade}[/]", f"[dim]{chave}[/]")
    if not faltando and not estruturais:
        afazeres.add_row(f"[{VERDE}]✓[/]", "nada pendente")

    layout = Layout()
    layout.split_column(
        Layout(cabecalho, size=2),
        Layout(Panel(acervo, title="acervo", border_style=AZUL, title_align="left"), size=9),
        Layout(
            Panel(afazeres, title="a fazer", border_style="yellow", title_align="left"),
            size=9,
        ),
        Layout(
            Panel(
                _catalog_table(descriptors),
                title="descritores",
                border_style="dim",
                title_align="left",
            )
        ),
        Layout(
            Text(
                "  vigiando reference/ — solte um .docx lá e a tela recarrega"
                "      Ctrl+C para sair",
                style="dim",
            ),
            size=2,
        ),
    )
    return layout


def _watch_signature(folder: Path) -> tuple:
    if not folder.is_dir():
        return ()
    return tuple(
        sorted(
            (f.name, f.stat().st_mtime_ns, f.stat().st_size)
            for f in folder.glob("*.docx")
            if not f.name.startswith("~$")
        )
    )


@app.command("dev")
def dev(
    docx: Path = typer.Option(None, "--docx", help="Arquivo .docx de origem."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Pasta de trabalho."),
    intervalo: float = typer.Option(1.0, "--intervalo", help="Segundos entre checagens."),
) -> None:
    """Painel que fica aberto mostrando o que falta, e recarrega sozinho.

    Deixe rodando num terminal ao lado. Solte um .docx novo em reference/ e ele passa a
    analisar o mais recente.
    """
    source = _resolve(docx)
    assinatura = _watch_signature(REFERENCE_DIR)

    with Live(
        _dev_screen(source, out), console=console, screen=True, refresh_per_second=4
    ) as live:
        try:
            while True:
                time.sleep(intervalo)
                atual = _watch_signature(REFERENCE_DIR)
                if atual == assinatura:
                    continue
                assinatura = atual
                if docx is None and atual:
                    source = max(
                        (REFERENCE_DIR / nome for nome, _, _ in atual),
                        key=lambda f: f.stat().st_mtime,
                    )
                live.update(_dev_screen(source, out))
        except KeyboardInterrupt:
            pass
    console.print("\n  [dim]até mais[/]\n")

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
