## 1. Perfil de ingestão (backend primeiro)

- [x] 1.1 Criar `backend/smedocs/profile.py` (Pydantic) com os 14 campos + `PRESET_MURIAE`, verificando que `python -c "from smedocs.profile import PRESET_MURIAE; PRESET_MURIAE.validate_regexes()"` passa
- [x] 1.2 Criar `profiles/banco-muriae.json` espelhando os defaults e verificar que carrega igual ao preset em código
- [x] 1.3 Refatorar `extract.py`/`segment.py` para receber `profile` (sem global `RE_*`), verificando que `listar` sem `--perfil` mantém saída
- [x] 1.4 Propagar `profile` em `pipeline.load/build` + flag `--perfil` na CLI, verificando `smedocs.py gerar 10 --perfil profiles/banco-muriae.json` gera o mesmo PDF

## 2. Diagnóstico e regressão

- [x] 2.1 Estender `analisar` com contagens por regra (separador, descritor, A–E, cores), verificando saída legível em docx sintético mínimo
- [x] 2.2 Rodar regressão do preset (31 descritores, 868 questões, 647 gabaritos, `A == questões`, `imagens_no_bloco == imagens_no_HTML`), verificando relatório `conferir`
- [x] 2.3 Criar 2 fixtures mínimas (separador `---`, alternativa `1)`) e verificar que só o perfil alternativo as segmenta

## 3. Electron instalado

- [x] 3.1 Fixar `electron/package.json` + `npm install` reprodutível, verificando `npm start` abre a janela sem erro
- [x] 3.2 Validar `printToPDF()` A4 0.55in com fundo, verificando PDF salvo via diálogo
- [x] 3.3 Validar handshake porta livre + `getApi`/`onApiReady` com sidecar ausente, verificando mensagem de API indisponível sem travar

## 4. Otimização inicial + higiene

- [x] 4.1 Estender cache (Word + assets por `nome|tamanho|mtime`) + `--sem-cache`, verificando segunda execução pula render (~12s → <1s)
- [x] 4.2 Atualizar `.gitignore` (`electron/node_modules`, `out/`, `reference/`, `.venv/`) mantendo `profiles/*.json`, verificando `git status` limpo
- [x] 4.3 Atualizar `README`/`PLANO` (instalar, `--perfil`, `npm start`), verificando instruções executáveis do zero
