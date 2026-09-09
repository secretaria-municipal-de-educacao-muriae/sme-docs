# SMEDocs

Aplicativo desktop que converte documentos Word desorganizados enviados pelo setor
pedagógico em material diagramado (provas, apostilas, relatórios, material didático).

Backend Python + FastAPI. Frontend Electron. Windows apenas.

## Contexto do negócio

O setor pedagógico manda `.docx` com frequência alta e sem padronização. Hoje a
diagramação é manual. O objetivo é reduzir isso a: subir o Word, conferir, exportar PDF.

O acervo de questões extraído é reutilizável — não é descartado após gerar o PDF. Uma
questão extraída hoje deve poder ser filtrada por descritor, ano e origem para montar
uma prova amanhã.

## Restrições que moldam a arquitetura

- **Sem orçamento de API.** Não existe chave da Anthropic API disponível. Nada no
  runtime do aplicativo pode depender de chamada a LLM. Todo o parsing é determinístico.
  Quando houver ambiguidade, o app abre uma tela de revisão humana em vez de adivinhar.
  Assistência de IA acontece apenas offline, dentro de sessões do Claude Code, em lote.
- **Alvo Windows.** Aceitável depender de recursos nativos do Windows (renderização de
  WMF via GDI, COM do Word). Isso trava o backend fora do Windows — decisão consciente.
- **Distribuição para máquinas sem Python.** Empacotamento via PyInstaller + electron-builder.
  Qualquer dependência pesada precisa justificar o tamanho do instalador.

## Documentos de referência

Ficam em `reference/`. São a fonte da verdade sobre o formato de entrada e de saída.

| Arquivo | Papel |
|---|---|
| `APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx` | Entrada real, pior caso. 20 MB, 188 páginas |
| `Apostila de recomposição de aprendizagem (1).pdf` | Saída desejada, 46 páginas |
| `modelo-claude-apostila.zip` | Fonte do template acima, gerado pelo Claude Design |

## O que já foi apurado sobre o DOCX de entrada

Análise feita direto sobre `word/document.xml`. Números conferidos, não estimados.

- 9.654 parágrafos, dos quais 9.667 runs usam estilo `Normal` e 6 usam `ListParagraph`.
  **Não existe nenhum heading.** Toda a estrutura precisa ser inferida do texto.
- Separador de questão: linha contendo apenas asteriscos, comprimento variável
  (18 a 50 caracteres). 834 ocorrências. Regex: `^\*{3,}$` após strip.
- **O separador não é confiável sozinho.** Segmentar só por ele produz 765 blocos.
  Segmentar por separador **mais** reinício da letra da alternativa em `A` produz
  **864 questões** — número que bate exatamente com as 864 alternativas `A` contadas
  independentemente. Use as duas regras juntas.
- Cabeçalho de descritor aparece em quatro formatos no mesmo arquivo:
  `Descritor 1:` / `D2:` / `D3 -` / `D8 –` (en dash). São 31 descritores, numerados
  1 a 30 mais 32 — o 31 não existe apesar do título do arquivo.
- Marcador secundário de seção: `ATIVIDADES DO DESCRITOR N`, 30 ocorrências, com um
  `ATIVIDADES DOS DESCRITOR 6` (erro de digitação no original).
- Origem da questão vem como prefixo do enunciado entre parênteses seguido de ponto:
  `(PROEB).`, `(Saresp 2007).`, `(Enem 2011).`, `(Prova Brasil).`. Mais frequentes:
  Prova Brasil 44, Saresp 2007 36, GAVE 26, PROEB 21.
- Alternativas aceitam duas formas: `A)` e `(A)`. Contagem: A 864, B 810, C 823,
  D 809, E 17.

### Gabarito

**A alternativa correta está marcada em vermelho no próprio Word.** Duas cores em uso:
`FF0000` e `EE0000`. Ambas contam.

Cobertura medida pelo pipeline sobre as 868 questões que ele extrai hoje:

- 647 (74%) têm gabarito automático
- 219 (25%) não têm nenhuma marcação — precisam de revisão humana
- 619 questões saem sem nenhuma pendência

As 62 restantes têm defeito estrutural (letras fora de sequência 26, só 2 alternativas
13, só 3 alternativas 12, letras repetidas 5, 2 marcações 2, só 1 alternativa 3,
enunciado vazio 1). Amostradas, são em boa parte defeitos do próprio original.

Existe também um punhado de `Resp. B` escrito literalmente no texto. Raro (1 bloco),
não vale construir regra dedicada, mas o revisor humano vai encontrar.

Cuidado: nem todo parágrafo vermelho é alternativa. Enunciados inteiros aparecem em
vermelho em alguns pontos. Filtre por "parágrafo vermelho **que casa com o padrão de
alternativa**".

### Fórmulas de matemática — o ponto crítico

O documento tem 547 objetos OLE do Microsoft Equation 3.0, renderizados como 539
imagens WMF. São fórmulas inline, no meio de frases.

**A docling descarta todas elas silenciosamente.** Testado: `convert()` roda em 15s e
retorna `pictures = 820`, que corresponde apenas aos 825 PNG. As WMF somem. O estrago
aparece em 369 parágrafos, que ficam com buraco no meio da frase:

```
Word original:  (C) a medida do segmento M̄S̄ é o dobro da medida do lado MA.
Docling:        (C) a medida segmento    é o dobro da medida do lado MA.
```

A FAQ da docling afirma que WMF funciona no Windows, mas o backend DOCX não percorre
`w:object` nem `v:imagedata`, então a limitação vale mesmo no Windows.

**Por isso o extrator de `.docx` é próprio, não docling.** A docling fica como backend
para PDF, PPTX, HTML e imagem.

WMF é renderizável: `PIL.Image.open()` seguido de `.load(dpi=N)` funciona nativo no
Windows via GDI.

**Mas a rasterização via GDI corrompe parte das fórmulas.** Medido em F0 sobre uma
amostra aleatória de 12 equações: 10 perfeitas, 1 destruída, 1 com colisão leve — algo
entre 8% e 17%. A falha atinge apenas fórmulas com **parênteses**: o Equation 3.0
desenha `(` e `)` com uma fonte esticada por `lfWidth`/`lfHeight`, e o GDI erra o avanço
dos glifos, empilhando `(`, `6`, `0`, `°`, `)` uns sobre os outros. Frações, radicais,
chaves e sistemas saem corretos.

Não é problema de escala: testado em 72, 96, 144, 200, 300, 450, 720 e 1200 DPI, a
corrupção é idêntica em todos. Não adianta mexer no DPI.

**A solução está em `wordmath.py` e funciona.** O Word desenha a partir do OLE, não da
prévia, e acerta. A ponte:

1. monta um docx auxiliar com uma fórmula por página, na ordem do documento
2. o Word exporta esse docx em PDF (`ExportAsFixedFormat`, `FileFormat=17`)
3. cada página vira um PNG recortado no traço

Página N corresponde à fórmula N por construção — não há adivinhação de posição. Custo
medido: 547 páginas em 7,6s de Word, 5s de recorte, ~12s no total. Fica em cache,
invalidado por nome/tamanho/mtime do docx de origem. 539 fórmulas renderizadas.

Dois detalhes que custaram tempo e não podem ser perdidos:

- **O recorte tem que ser no nível do span, não do bloco.** O bloco de texto do PDF
  ocupa a largura do parágrafo inteiro. Usá-lo dava proporção 6× mais larga que a
  fórmula, e ela entrava minúscula no HTML.
- **Spans de espaço em branco contam.** O marcador de parágrafo aparece a 165pt do
  traço; incluí-lo esticava a caixa em até 8×. Filtre `span["text"].strip()`.

Caminhos descartados:

- **A exportação para HTML filtrado do Word não serve.** `SaveAs2(FileFormat=10)` roda
  em 24s e produz 1384 `<img>`, mapeados por nome (`image273.wmf` vira `image273.png`,
  o que resolveria a correspondência de graça), mas os PNG saem a 96 DPI e recortados
  — só a faixa superior dos glifos. Ele rasteriza a mesma prévia WMF quebrada.
- LibreOffice renderiza Equation 3.0 corretamente, mas não está instalado e pesaria no
  instalador.

Não tente converter para MathML ou LaTeX pela via fácil: Equation 3.0 é OLE binário
(MTEF), não OMML. Rasterizar é a saída prática. Dívida técnica registrada: o resultado
não é acessível a leitor de tela nem refluível.

Composição dos 547 objetos OLE: 542 `Equation.3`, 2 `Equation.DSMT4` (MathType) e 3
`CorelPhotoPaint.Image.7`. Os três últimos são fotos, não fórmulas, e caem no GDI.

### Escala e posição da fórmula

O Word desenha a fórmula no tamanho natural do objeto; o docx a coloca reduzida na
linha. A regra que funciona: **largura declarada no docx manda, altura sai da proporção
do recorte do Word.** Confere — para `image273` dá 66,75 ÷ 3,91 = 17,1pt contra os
18,75pt declarados.

Inline ou bloco **não se decide por altura**. O sinal certo é se a fórmula divide o
parágrafo com texto: `sen(60°) = √3/2` no meio de uma frase é alto por causa da fração
mas continua inline. Ver `inline_context` em `segment.py`.

### Armadilhas de segmentação já resolvidas

Todas medidas sobre o documento inteiro. Não reintroduzir.

- **42 blocos trazem várias alternativas num parágrafo só**, alinhadas por tabulação:
  `(A) <fórmula>  (B) <fórmula>  (C) ...`. Sem tratar, a linha inteira virava a
  alternativa A e o conteúdo das outras saía como o texto literal `"(B)"`. Bastam duas
  letras consecutivas para caracterizar o caso — metade é um par `(A) (B)` seguido de
  outro parágrafo `(C) (D)`.
- **Nesses parágrafos a marca vermelha cai sobre o rótulo**, não sobre o conteúdo. O
  rótulo é descartado do texto, então a cor dele precisa ser preservada antes.
- **O rótulo chega partido entre runs.** `" ("` e `"C) "` vêm separados, e a fronteira
  de cor do gabarito força a quebra. Remover o rótulo olhando só o primeiro fragmento
  quebra com `AttributeError`; percorra o fluxo de texto inteiro.
- **A alternativa A às vezes está colada no fim do enunciado**: `"...qual número
  inteiro? A) −3."`. Sem soltar, a questão perde a letra A, o corte por reinício em A
  não dispara, e ela se funde com a anterior — o padrão `ABCDBCD`. A confirmação segura
  é o bloco seguinte começar com a letra seguinte.
- **O enunciado precisa manter as quebras de parágrafo do Word.** Sem isso um título de
  seção encosta na pergunta: `"...TRIÂNGULO RETANGULOPara se deslocar de sua casa..."`.

### Outros achados de F0

- O `☻` (U+263B) aparece 162 vezes como marca decorativa em Wingdings e precisa ser
  removido, junto com os parênteses vazios que sobram. Já tratado em `extract.py` e
  `segment.py`. **Não confundir com `−`, `√`, `×`, `≥`, `≤` e `•`, que são conteúdo.**
- O descritor 1 não tem o marcador `ATIVIDADES DO DESCRITOR` e sua primeira questão
  vem antes do primeiro separador. Cortar a introdução só por esses dois marcadores faz
  a questão inteira ser absorvida pela caixa de introdução. A terceira pista — a
  primeira alternativa, recuando até a última frase pedagógica — é obrigatória.
- Cuidado ao criar arquivos de teste: um `inspect.py` no diretório de trabalho sombreia
  o módulo `inspect` da biblioteca padrão e quebra `lxml` e `pymupdf` com erros
  enganosos (`ImportError: cannot import name getfullargspec`).

## O que já foi apurado sobre o template de saída

O PDF de referência foi gerado pelo Chromium, não por um editor:

```
producer: Skia/PDF m152
creator:  Chrome/152.0.0.0
```

**Consequência: o Electron já embute o motor que gera esse PDF.** Use
`webContents.printToPDF()`. Não instale WeasyPrint, Playwright, LibreOffice nem
wkhtmltopdf — nenhum está na máquina e nenhum é necessário.

O fonte é `Apostila Recomposicao.dc.html` dentro do zip. É um `.dc.html` do Claude
Design: **todo o estilo é inline, não há classes CSS.** Converter isso em componentes
Jinja2 com folha de estilo própria é trabalho real, não um copiar e colar.

O arquivo depende de `doc-page.js` e `support.js`, que são o runtime do canvas do Claude
Design. O renderizador não precisa deles — substitua `<doc-page margin="0.55in">` por
`@page { size: A4; margin: 0.55in }`.

### Tokens de design extraídos

```
Fontes    Baloo 2 (500/700/800) títulos · Nunito (400/600/700/800) corpo
          Ambas do Google Fonts. Empacotar localmente — o app roda offline.

Cores     #1B56C4  azul primário
          #123E8F  azul escuro (títulos)
          #E63946  vermelho (destaque, chips)
          #F4C430  amarelo
          #3FA34D  verde
          #232323  texto
          #5B5B5B  texto secundário
          #EAF1FD  fundo de caixa azul
          #F5F5F3  fundo de caixa neutra
          #DADADA  bordas e réguas

Página    A4 210×297mm, margem 0.55in
Corpo     15px / line-height 1.65
Escala    52 capa · 34 h1 · 24 · 20 h2 · 18 · 16 · 15 corpo · 14 · 13 · 12 · 11 legenda
```

Componentes presentes no template que o banco de questões vai consumir: chip de seção,
régua de quatro cores, caixa dupla SAEB/BNCC, callout de leitura, bloco de questão
numerada com alternativas A–D, grade de imagens numeradas.

## Fontes

Baloo 2 e Nunito não estão instaladas nas máquinas do setor. Sem tratar isso, o Word
substitui por conta própria e o `.docx` não tem nada a ver com o PDF — foi a primeira
reclamação sobre a saída em Word.

Instâncias estáticas geradas com `fontTools.varLib.instancer` a partir das variáveis do
Google Fonts vivem em `backend/smedocs/fonts/` (licença OFL, incluída). Elas são:

- **embutidas no `.docx`** por `docx_fonts.py`. O formato exige ofuscar cada arquivo —
  os 32 primeiros bytes em XOR com uma chave derivada de um GUID, ECMA-376 §15.2.13.
  A chave vem do GUID sem chaves nem hífens, lido como 16 bytes **em ordem inversa**.
  Também é preciso `<w:embedTrueTypeFonts/>` em `settings.xml`, entre `w:zoom` e
  `w:proofState` para respeitar a ordem do esquema.
- **servidas localmente no HTML** via `@font-face`, em vez do CDN do Google. O PDF
  precisa sair igual mesmo sem internet.

Baloo 2 tem entrelinha nativa muito alta. Nos títulos do `.docx`, `line_spacing` como
múltiplo não resolve — use valor exato em `Pt`.

## Gabarito preenchido à mão

219 questões não têm marcação vermelha na origem. Isso não é falha de leitura — é
ausência no documento.

Como não há orçamento de API, nada é adivinhado em tempo de execução. O ciclo é
`smedocs pendencias` para exportar o lote, uma sessão do Claude Code para resolver, e
`smedocs gabarito` para trazer de volta. O resultado fica em `gabarito/respostas.json`,
versionado — o trabalho é feito uma vez.

`answers.apply` roda dentro de `pipeline.load`, depois da segmentação. Ele **só marca
onde nenhuma alternativa estava marcada**: a sobreposição nunca contradiz o documento.
A alternativa preenchida assim carrega `from_overlay=True`, para que os relatórios
saibam separar o que veio do Word do que veio da revisão.

Ao resolver um lote, olhe a figura antes de responder. Duas armadilhas já vistas:

- A planificação do cubo: a opção com uma fileira de 5 quadrados tem 7 faces no total e
  não fecha cubo. É preciso contar os quadrados, não olhar o formato.
- Ângulo de escada apoiada: o número que aparece no desenho costuma ser o ângulo com o
  **chão**, e o enunciado pede o ângulo com o **muro**. A alternativa que repete o
  número do desenho é a pegadinha.

## Convenções

- Cada estágio do pipeline grava seu artefato em disco antes de passar adiante. Depurar
  significa abrir o JSON intermediário, não recolocar `print` no meio do código.
- Toda contagem que entrar em documentação vem de medição sobre os arquivos de
  `reference/`. Não estimar.
- Teste de regressão obrigatório: `imagens_no_bloco == imagens_no_HTML` para as 864
  questões. É o alarme contra dessincronização de assets, que é a falha mais provável
  e a mais difícil de enxergar a olho nu.
