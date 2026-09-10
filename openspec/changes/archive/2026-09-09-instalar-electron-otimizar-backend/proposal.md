## Why

O SMEDocs hoje só diagramada um único `.docx` (banco Muriaé): separador `^\*{3,}$`, cabeçalhos `Descritor/D`, alternativas `A)`/`(A)` e gabarito vermelho estão fixos em `segment.py`/`extract.py`. Qualquer docx novo exige editar código. Ao mesmo tempo a casca Electron existe mas não está instalada de forma reprodutível nem ligada ao backend, e o backend repete extração/render sem cache nem diagnóstico.

## What Changes

- **Perfil de ingestão configurável**: trocar `RE_*` globais por `IngestionProfile` (Pydantic) com preset `banco-muriae` 100% compatível; `pipeline.load/build` passam a receber `profile`; CLI ganha `--perfil`.
- **Diagnóstico de ingestão**: `analisar` informa contagens por regra (separadores, descritores, A/B/C/D) e o que cairia em `needs_review`.
- **Electron instalado e funcional**: `electron/` com `npm install` reprodutível, `npm start` abrindo janela, `printToPDF()` A4 funcional, handshake `/health` + porta livre prontos para o sidecar FastAPI (F4).
- **Otimização inicial do backend**: cache de fórmulas Word + assets por hash, evitar re-extração desnecessária, logs/progresso claros, `.venv` + dependências pinadas, `reference/`/`out/` ignorados e `profiles/*.json` versionados.

## Capabilities

### New Capabilities
- `ingestion-profile`: parsing parametrizado do `.docx` (delimitador, cabeçalho, alternativas, cor gabarito, origem, limpeza) com preset Muriaé e validação de regex.
- `electron-shell`: casca desktop instalável (janela, preload seguro, printToPDF, sidecar placeholder).
- `backend-optimization`: otimização inicial do pipeline (cache, diagnóstico, deps, DX) sem mudar saída do preset padrão.

### Modified Capabilities
- Nenhuma (sem specs prévias em `openspec/specs/`).

## Impact

- Afetados: `backend/smedocs/segment.py`, `extract.py`, `pipeline.py`, `cli.py`, `models.py` (novo `profile.py`), `electron/main.js`, `preload.js`, `renderer/*`, `package.json`, `.gitignore`, `README`/`PLANO`.
- Sem breaking change quando sem `--perfil`: saída idêntica (868 questões / 647 gabaritos no doc atual).
- Novos artefatos versionados: `profiles/banco-muriae.json`; gerados continuam em `out/` (ignorado).
- Dependências: Node 24 + Electron 33, Python 3.13/3.14 + `pywin32`, Word para fórmulas (fallback GDI).
