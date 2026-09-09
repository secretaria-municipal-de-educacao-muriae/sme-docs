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

## Requisitos

- Windows (o pipeline usa GDI e automação COM do Word)
- Python 3.13 ou 3.14
- Microsoft Word — renderiza as fórmulas de matemática com fidelidade
- Google Chrome ou Microsoft Edge — imprime o PDF
- Node 24 — casca Electron (`electron/`)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd electron && npm install
```

As fontes do template (Baloo 2 e Nunito, licença OFL) ficam em
`backend/smedocs/fonts/`. Nada é baixado em tempo de execução — o programa roda offline.

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

### Perfil de ingestão (`--perfil`)

As regras de parsing (separador, cabeçalho de descritor, alternativas, cor de
gabarito) vivem num `IngestionProfile` (`backend/smedocs/profile.py`), não mais
fixas no código. Sem `--perfil`, vale o preset `profiles/banco-muriae.json`,
com saída idêntica à de antes:

```bash
python smedocs.py listar --perfil profiles/banco-muriae.json
python smedocs.py gerar 10 --perfil profiles/banco-muriae.json
python smedocs.py analisar outro.docx --perfil meu-perfil.json
```

O `analisar` mostra o diagnóstico por regra — quantos blocos casaram cada padrão
e a validação cruzada (nº de `A` vs nº de questões). Um perfil com regex inválido
é rejeitado com o nome do campo. Fixtures mínimas em `tests/fixtures/` +
`tests/check_regression.py` (23 verificações sobre o banco real) mostram como
criar um perfil novo.

### Cache (`--sem-cache`)

Na primeira execução o Word é chamado uma vez para renderizar as 547 fórmulas; leva
cerca de 12 segundos e fica em cache em `out/eqcache` (chave nome|tamanho|mtime do
`.docx`). As mídias ficam em `out/assets` por digest do conteúdo. Execuções seguintes
pulam a renderização (~12s → <1s no passo do Word). Com `--sem-cache`, tudo é refeito:

```bash
python smedocs.py gerar 10 --sem-cache
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
cerca de 12 segundos e fica em cache. As execuções seguintes levam menos de 1 segundo
no passo do Word. Ver "Cache (`--sem-cache`)" acima.

### A casca Electron

```bash
cd electron && npm install && npm start
```

Abre a janela SMEDocs (1200×800). Sem o sidecar FastAPI (fase F4), ela indica API
indisponível em vez de travar. O botão de exportar usa `webContents.printToPDF()`
A4 com margens de 0.55in — o mesmo motor Chromium do template de referência.

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
| `backend/smedocs/profile.py`     | Perfil de ingestão (Pydantic) + preset `banco-muriae` |
| `backend/smedocs/diagnose.py`    | Diagnóstico por regra (`analisar`) e validação cruzada |
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

## Duas decisões que não são óbvias

**A docling não é usada para `.docx`.** Ela converte o arquivo em 15 segundos, mas o
backend DOCX dela não percorre `w:object` nem `v:imagedata` e descarta em silêncio as
539 fórmulas de matemática, deixando 369 parágrafos com buraco no meio da frase. Por
isso o extrator é próprio.

**As fórmulas são renderizadas pelo Word, não pelo Windows.** O `.docx` guarda uma
prévia em WMF de cada fórmula, e rasterizar essa prévia com o GDI empilha os glifos de
toda fórmula que tenha parênteses. O Word desenha a partir do objeto OLE e acerta.

Os detalhes de ambas, com as medições, estão em [CLAUDE.md](CLAUDE.md).
