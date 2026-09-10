# SMEDocs

Converte documentos Word desorganizados enviados pelo setor pedagógico em material
diagramado — provas, apostilas, relatórios e material didático.

Secretaria Municipal de Educação de Muriaé.

## Situação

Fase F0 concluída: script Python que lê o banco de questões em `.docx` e gera a
apostila de um descritor em PDF, com a diagramação do template oficial.

Ainda **não** existe interface. Electron, banco de dados e API estão planejados nas
fases seguintes — ver [PLANO.md](PLANO.md).

```
31 descritores · 868 questões · 647 com gabarito automático (74%)
619 questões sem nenhuma pendência · 539 fórmulas de matemática renderizadas
```

Existe também um segundo formato, a **apostila de educação infantil**: A4 deitado, uma
página por atividade, 21 modelos de página. Ver
[Apostila de educação infantil](#apostila-de-educação-infantil).

## Requisitos

- Windows (o pipeline usa GDI e automação COM do Word)
- Python 3.13
- Microsoft Word — renderiza as fórmulas de matemática com fidelidade
- Google Chrome ou Microsoft Edge — imprime o PDF

```bash
pip install pydantic jinja2 pillow pywin32 pymupdf typer rich python-docx
```

As fontes do template (Baloo 2 e Nunito, licença OFL) ficam em
`backend/smedocs/fonts/`. Nada é baixado em tempo de execução — o programa roda offline.

A apostila infantil usa **Neo Sans Std**, que é licenciada da Monotype e por isso **não
está versionada**. Coloque os `.otf` em `backend/smedocs/fonts/` e rode uma vez:

```bash
python -m smedocs.fonts_otf2ttf     # gera os .ttf que o renderizador usa
```

## Uso

Os documentos de origem não estão versionados. Coloque-os em `reference/`:

```
reference/
  APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx
```

Depois:

```bash
python smedocs.py dev                   # painel que fica aberto, recarrega sozinho
python smedocs.py                       # modo interativo, pergunta o que gerar
python smedocs.py listar                # tabela de todos os descritores
python smedocs.py gerar 10              # descritor 10 em PDF
python smedocs.py gerar 10 -f docx      # em DOCX
python smedocs.py gerar 10 -f pdf -f docx
python smedocs.py gerar --tudo
python smedocs.py gerar 10 --sem-gabarito   # versão do aluno
python smedocs.py conferir 10           # só o relatório, sem gerar arquivo
python smedocs.py analisar outro.docx   # inspeciona um .docx qualquer
python smedocs.py pendencias -n 20      # exporta questões sem gabarito
python smedocs.py gabarito respostas.json   # importa as respostas
```

### O painel `dev`

`python smedocs.py dev` abre um painel que fica aberto num terminal ao lado, no espírito
de um `npm run dev`: mostra o tamanho do acervo, a lista do que falta fazer e a situação
de cada descritor.

Ele vigia a pasta `reference/`. **Solte um `.docx` novo lá e a tela recarrega sozinha**,
passando a analisar o arquivo mais recente. Para inspecionar um arquivo fora dessa pasta
sem mexer em nada, use `analisar`; com `--copiar` ele entra em `reference/` no fim.

Sem argumento, entra no modo interativo. Com argumento, roda e sai — o que serve para
script. `-q` suprime a barra de progresso e imprime só os caminhos gerados;
`listar -f json` devolve JSON.

A saída vai para `out/descritor-<n>.pdf` e `out/descritor-<n>.docx`.

### O gabarito das questões que o Word não marcou

219 das 868 questões não têm marcação vermelha nenhuma no documento de origem. O
gabarito delas simplesmente não existe no arquivo.

Como não há orçamento de API, o programa **não adivinha nada em tempo de execução**. O
ciclo é outro:

```bash
python smedocs.py pendencias -n 20      # escreve out/pendencias.md e out/pendencias.json
# uma sessão do Claude Code (ou uma pessoa) resolve o lote lendo o .md
python smedocs.py gabarito out/pendencias.json
```

O `.md` traz enunciado, alternativas e o caminho de cada figura, para quem responde
poder abrir a imagem. O `.json` é o molde a preencher. O resultado entra em
`gabarito/respostas.json`, **versionado junto com o código** — o trabalho é feito uma vez
e vale para sempre.

A sobreposição nunca contradiz o documento: ela só preenche onde não havia marcação.

### Os dois formatos

O **PDF** é o entregável: reproduz o template, impresso pelo mesmo motor que o gerou.

O **DOCX** é a versão de trabalho, para quando o material ainda precisa de ajuste
manual. Sai com **estilos nomeados do Word** — para mudar o corpo do texto da apostila
inteira basta editar o estilo `SME Enunciado` uma vez, em vez de selecionar 800
parágrafos. As fontes do template vão embutidas dentro do arquivo, então ele abre igual
em qualquer máquina, sem instalar nada.

Na primeira execução o Word é chamado uma vez para renderizar as 547 fórmulas; leva
cerca de 12 segundos e fica em cache. As execuções seguintes levam menos de 1 segundo.

## Apostila de educação infantil

Formato diferente do banco de questões: **A4 deitado** (1123×794px), fonte Neo Sans Std,
uma página por atividade. O motor de impressão é o mesmo.

```bash
python smedocs.py modelos                              # catálogo dos 21 modelos
python smedocs.py apostila planos/2periodo-1semestre.json
python smedocs.py svg out/apostila-infantil.pdf        # um SVG por página
python smedocs.py svg out/apostila-infantil.pdf --curvas   # texto vira contorno
```

`modelos` gera uma folha de contato com os 21 modelos preenchidos com conteúdo de
exemplo — é o que se olha para escolher.

### Os 21 modelos

O catálogo fica em `backend/smedocs/modelos_infantil.json`. Dez modelos vieram dos PNG
de referência da apostila do fundamental e onze das 40 páginas que o setor pedagógico
enviou. Nenhum foi criado por precaução: cada um cobre pelo menos uma página real.

| | |
| --- | --- |
| M01 · M13 | recorte e colagem — tiras de palavra, cartões com figura e legenda |
| M02 | biografia com foto e faixa de onda |
| M03 · M04 · M19 | tabela de ilustrar, grade de contagem de letras, pictograma |
| M05 · M20 | situação-problema, montar palavras com sílabas |
| M06 | obra em moldura — uma ou duas telas |
| M07 · M15 | cartão de comparação de palavras, lista de palavras |
| M08 · M17 | fotos circulares com personagem, fileira de imagens com rótulo |
| M09 · M21 | texto em duas colunas, texto com ilustração de meia página |
| M10 · M11 | abertura com balão, poema e cantiga |
| M12 · M14 | caça-pares, blocos de texto espalhados |
| M16 · M18 | receita, orientação ao professor |

Cada modelo carrega, além dos slots, três campos que só existem para a etapa de escolha:

- `quando_usar` — em que situação aquele modelo é o certo
- `sinais` — expressões que costumam aparecer no enunciado ("recorte e cole", "quem sou
  eu", "pinte os quadrinhos")
- `capacidade` — quanto conteúdo cabe antes de estourar a página

### Do PDF da professora à apostila

Mesma lógica do gabarito: **nada é adivinhado em tempo de execução.** A escolha do
modelo para cada atividade acontece numa sessão do Claude Code, lendo o PDF e casando
cada página com um modelo pelo `quando_usar` e pelos `sinais`. O resultado é um plano em
JSON, versionado; o programa só renderiza.

```json
[
  { "modelo": "M11", "dados": { "titulo": "ATIVIDADE 42", "estrofes": [...] } },
  { "modelo": "M05", "dados": { "titulo": "ATIVIDADE 28", "problemas": [...] } }
]
```

`planos/2periodo-1semestre.json` traz as 40 páginas do 1º semestre já mapeadas. Cada
página registra `_origem` (de que página do PDF veio) e `_porque` (por que aquele
modelo), para conferir a leitura sem abrir os dois arquivos lado a lado.

A distribuição diz bastante sobre o material: **7 das 40 páginas são poema** — foi a
maior lacuna dos modelos herdados do fundamental.

### Saída vetorial

O PDF já é vetor e abre direto no Illustrator. `svg` existe para quem prefere editar no
Figma, no Inkscape ou no navegador; ele usa o `pymupdf`, que o projeto já carrega para
as fórmulas.

Toda a arte — ilustrações, fotos, cenários — entra como **slot de borda tracejada**. Ela
some sozinha quando o arquivo chega: basta passar o caminho no campo correspondente.

### As medidas não foram estimadas

A página ocupa 860×613px dentro dos PNG de referência, com 8px de sombra em volta. Tudo
foi convertido para a escala de 1123px de largura. Daí saíram os números que valem para
todos os modelos:

```
margem esquerda do texto  86px      coluna de texto até x=1081
título e enunciado        25px      (caixa alta medida 18,3px ÷ 0,743)
entrelinha do enunciado   39px
fólio                     54×46px, 38px da borda, 18px da base
```

Depois o PDF gerado foi medido pelo mesmo método e corrigido até bater. Os números de
cada modelo estão nos comentários de `static/infantil.css`.

Uma ressalva medida e não resolvida: o título laranja da referência sai de 8% a 16% mais
estreito que o Neo Sans Std Bold na mesma altura de caixa alta. O original usou uma
variante condensada que não está na pasta. Se ela aparecer, é trocar um `@font-face` — o
resto do layout não muda.

## Como funciona

```
                                                        ┌─> .pdf   Jinja2 + Chromium
.docx ──> extract ──> media ──> segment ──> validate ───┤
          │           │         │           │           └─> .docx  python-docx
          │           │         │           └ Pydantic
          │           │         └ descritores, questões, alternativas, gabarito
          │           └ WMF/OLE via Word, PNG e JPG direto
          └ percorre word/document.xml na ordem do documento
```

| Módulo                            | Papel                                                  |
| ---------------------------------- | ------------------------------------------------------ |
| `backend/smedocs/extract.py`     | Lê o`.docx` para uma representação intermediária |
| `backend/smedocs/wordmath.py`    | Renderiza as fórmulas OLE usando o Word               |
| `backend/smedocs/media.py`       | Normaliza imagens para PNG                             |
| `backend/smedocs/segment.py`     | Recupera a estrutura que o Word não tem               |
| `backend/smedocs/models.py`      | Contratos e validação em Pydantic                    |
| `backend/smedocs/render.py`      | Monta o HTML e imprime o PDF                           |
| `backend/smedocs/docx_render.py` | Monta o DOCX com estilos nomeados                      |
| `backend/smedocs/docx_fonts.py`  | Embute Baloo 2 e Nunito dentro do DOCX                 |
| `backend/smedocs/pipeline.py`    | Orquestra do .docx aos arquivos de saída              |
| `backend/smedocs/cli.py`         | Interface de linha de comando                          |
| `backend/smedocs/answers.py`     | Gabarito preenchido à mão, por fora do documento       |
| `backend/smedocs/review.py`      | Pacote de revisão: exporta pendências, importa respostas |
| `backend/smedocs/modelos_infantil.json` | Catálogo dos 21 modelos da apostila infantil     |
| `backend/smedocs/templates/infantil.html.j2` | Uma macro Jinja2 por modelo de página       |
| `backend/smedocs/fonts_otf2ttf.py` | Converte o Neo Sans de OTF para TTF                  |

## Três decisões que não são óbvias

**A docling não é usada para `.docx`.** Ela converte o arquivo em 15 segundos, mas o
backend DOCX dela não percorre `w:object` nem `v:imagedata` e descarta em silêncio as
539 fórmulas de matemática, deixando 369 parágrafos com buraco no meio da frase. Por
isso o extrator é próprio.

**As fórmulas são renderizadas pelo Word, não pelo Windows.** O `.docx` guarda uma
prévia em WMF de cada fórmula, e rasterizar essa prévia com o GDI empilha os glifos de
toda fórmula que tenha parênteses. O Word desenha a partir do objeto OLE e acerta.

**As fontes da apostila infantil são TTF, não OTF.** O Chrome embute fonte OTF no PDF
como fonte **Type3**, que não carrega o nome da família: o texto sai marcado como
`Type3 (5 0 R)`, o Illustrator abre sem reconhecer a fonte e o SVG exportado perde o
nome. A mesma página com TTF sai como Type0/TrueType com o nome certo
(`BAAAAA+NeoSansStdBold`). Daí `fonts_otf2ttf.py`.

Os detalhes das três, com as medições, estão em [CLAUDE.md](CLAUDE.md).
