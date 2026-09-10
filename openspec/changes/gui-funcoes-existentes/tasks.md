## 1. Forma visual

- [x] 1.1 Rodar `/impeccable shape gui-operacao` e aplicar o brief resultante aos tokens existentes, verificando que a decisão sidebar + seções está confirmada sem mudar os requisitos dos specs
- [x] 1.2 Extrair o CSS inline do renderer para stylesheet com variáveis dos tokens (`#1B56C4`, `#123E8F`, `#E63946`, `#3FA34D`, `#EAF1FD`, `#DADADA`) e `@font-face` local (Baloo 2 / Nunito de `backend/smedocs/fonts/`), verificando que `npm start` sem rede renderiza as fontes e não mostra erro no console

## 2. Ponte main/preload (estende `runCli`, sem tocar o backend)

- [x] 2.1 Implementar `smedocs:conferir-docx` (subprocesso `conferir` + parse tolerante com fallback "ver detalhes") e expor no preload, verificando que conferir o descritor 10 mostra o painel de resultado e a tabela de problemas
- [x] 2.2 Implementar `smedocs:analisar-novo` (subprocesso `analisar` completo: descritores + diagnóstico por regra + validação cruzada + `--copiar`) e expor no preload, verificando que um `.docx` válido mostra o diagnóstico e a adoção copia para `reference/`
- [x] 2.3 Implementar `smedocs:exportar-pendencias` e `smedocs:importar-gabarito` e expor no preload, verificando que exportar mostra lote com links de abertura e importar mostra respostas novas + antes/depois
- [x] 2.4 Adicionar busy-state por seção (botões desabilitados, estado "trabalhando…") com cancelamento via handle do child em `main.js`, verificando que gerar desabilita a seção e cancelar encerra o subprocesso sem travar a janela

## 3. Renderer (JS puro, sem framework)

- [x] 3.1 Construir o shell (sidebar Início/Gerar/Conferir/Gabarito + documento corrente no topo), verificando que a navegação troca de seção preservando o `.docx` selecionado
- [x] 3.2 Construir Início (painel do acervo + a fazer + tabela de descritores a partir de `listar -f json`), verificando que os números batem com `python smedocs.py listar`
- [x] 3.3 Construir Gerar (multi-descritores, todos, PDF/DOCX, com/sem gabarito, abrir saídas), verificando que gera o descritor 10 em PDF e abre o arquivo via `open-path`
- [x] 3.4 Construir Conferir (relatório + analisar novo + adotar) e Gabarito (exportar lote + importar), verificando cada cenário dos specs contra o banco real

## 4. Verificação

- [ ] 4.1 Percorrer o checklist manual das 4 seções sobre o banco Muriaé (incluindo primeira análise longa e falha simulada), verificando janela responsiva, erros legíveis e paridade com o CLI
- [x] 4.2 Rodar `openspec validate` do change e `npm start` limpo, verificando zero erro de validação e janela 1200×800 sem erro de módulo
