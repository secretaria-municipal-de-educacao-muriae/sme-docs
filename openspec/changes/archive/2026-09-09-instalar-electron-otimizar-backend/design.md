## Context

Estado atual (ver proposal.md para motivação): `segment.py:28-35` e `extract.py:35-37` usam `RE_*` globais; `pipeline.load/build` não recebem perfil; CLI sem `--perfil`; `electron/main.js` tem sidecar placeholder e `printToPDF()` pronto; backend sem cache além de `eqcache` e sem diagnóstico por regra. Sem specs prévias. Restrições: Windows-only (GDI/Word COM), offline, sem LLM em runtime.

## Goals / Non-Goals

**Goals:**
- Parametrizar parsing sem quebrar preset Muriaé; diagnóstico acionável; Electron instalável; cache + DX.

**Non-Goals:**
- Montagem custom do miolo, editor de template/CSS, banco SQLite/Postgres, SSE `/jobs`, tela de revisão dos 219 sem gabarito, empacotamento NSIS final (F6 original).

## Decisions

- **`IngestionProfile` Pydantic em `backend/smedocs/profile.py` + `profiles/banco-muriae.json`**: reaproveita padrão `models.py`; validação compila regex no load. Alternativa (YAML solto) descartada por perder validação automática.
- **Injeção por parâmetro, não global mutável**: `segment/extract/pipeline` recebem `profile`; default `PRESET_MURIAE` mantém compat. Alternativa (singleton) descartada por dificultar preview com dois perfis.
- **CLI `--perfil` + `analisar` diagnóstico**: menor superfície que API nova; serve de contrato para a UI futura.
- **Electron mantém `contextIsolation` + preload mínimo**: `getApi/printToPdf/analyzeWithProfile`; sidecar só spawna bin empacotado, em dev não trava sem API.
- **Cache por `nome|tamanho|mtime` (padrão `wordmath._source_key`)** estendido a assets: simples, sem migração; SQLite seria excesso agora.

## Risks / Trade-offs

- [Regex genérico quebra coincidência `864 A`] → Mitigação: validação cruzada `A == questões` + `imagens_no_bloco == imagens_no_HTML` como gate.
- [Python 3.14 vs 3.13 + `pywin32`/Word COM] → Mitigação: teste `wordmath.is_available()` + fallback GDI documentado.
- [Electron 33 + `electron-builder` pesado] → Mitigação: `node_modules` ignorado, `files` restrito a `main/preload/renderer`.
- [Cache stale se docx troca sem mtime] → Mitigação: chave inclui tamanho; comando `--sem-cache` para forçar.

## Migration Plan

1. Adicionar `profile.py` + preset sem trocar chamadas (default aplicado).
2. Migrar `extract/segment/pipeline/CLI` para aceitar `profile`.
3. Ativar diagnóstico e cache; rodar regressão do preset.
4. Rollback: apagar `--perfil` volta ao comportamento atual, pois defaults são os valores fixos antigos.

## Open Questions

- Nenhum bloqueante; formato final do JSON de diagnóstico será definido nos testes com docx real em `reference/`.
