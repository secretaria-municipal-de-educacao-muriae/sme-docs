# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: technical diagrammers + pedagogical reviewers at Secretaria Municipal de Educação de Muriaé, working together.

Situation: the pedagogical sector sends high-frequency, unstandardized `.docx` question banks. Diagramming today is manual. Users are non-technical operators doing repetitive layout work, not developers.

Job: upload the Word → confirm only what the machine was unsure about → export the finished PDF (and DOCX working version when manual tweaks remain). A question extracted today must stay reusable — filterable by descritor, ano and origem to assemble a prova tomorrow.

Other audiences (classroom teachers assembling directly) are out of v1 scope.

## Product Purpose

SMEDocs converts disorganized Word documents into diagrammed material (provas, apostilas, relatórios, material didático).

V1 scope is **apostila de banco de questões only** — the hardest case and the one with real reference material. Provas, relatórios and material didático reuse the same pipeline later; only the output template changes.

Success means reducing manual diagramming to three steps: subir o Word, conferir, exportar PDF. The extracted bank is an asset, not discarded after one PDF.

## Positioning

A neighboring product could not truthfully copy this combination:

- Deterministic OOXML parsing that preserves the 539 inline math formulas (Equation 3.0 OLE rendered via Word) other converters silently drop.
- Answer key read from the Word's own red marking (`FF0000`/`EE0000` on matching alternative paragraphs), never guessed; gaps go to explicit human review with overlay that never contradicts the document.
- Offline Windows desktop whose Chromium renderer (`printToPDF`) is the same engine that produced the official reference PDF.

## Operating Context

- Windows-only machines with Microsoft Word (math fidelity) and Chrome/Edge (PDF printing). App runs offline; nothing is downloaded at runtime.
- Input: `.docx` banks with no headings — structure inferred from `*`-separator lines plus alternative-letter restart, descritor headers (4 formats), `ATIVIDADES DO DESCRITOR N` markers, `(ORIGEM).` prefixes.
- Current workflow is CLI (`smedocs.py listar/gerar/conferir/analisar/pendencias/gabarito/dev`); F4/F5 move this to Electron window (1200×800) spawning a local FastAPI sidecar on 127.0.0.1 with `/health` handshake. Electron holds no DB or business logic — window, upload, review, export.
- State lives in Python; each pipeline stage writes its artifact to disk (`ir.json`, assets, HTML) before passing on. Debugging means opening the intermediate JSON.
- Future store: SQLite file in `userData` (single user, heavy read / light write); Postgres 17 only for development via SQLModel abstraction.
- Distribution: PyInstaller onedir + electron-builder NSIS for machines without Python.

## Capabilities and Constraints

Confirmed:

- 100% deterministic parsing; zero LLM calls at runtime (no API budget). Ambiguity → `needs_review` review screen, never a guess. AI assistance happens only offline in Claude Code sessions, in batch.
- Math formulas are rasterized images from OLE binary (MTEF), not MathML/LaTeX — printed output is correct but not screen-reader accessible nor reflowable (recorded debt).
- Fonts Baloo 2 + Nunito ship locally and embed inside DOCX (XOR-obfuscated per ECMA-376); no CDN dependency.
- DOCX output uses named Word styles (e.g. `SME Enunciado`) for whole-document reformatting.
- Answer overlay (`gabarito/respostas.json`, versioned) fills only where no alternative was red-marked; filled items carry `from_overlay=True`.
- Regression gate: `imagens_no_bloco == imagens_no_HTML` across all questions; asset desync is the most likely and hardest-to-see failure.
- Terminology: descritor, atividades do descritor, origem, alternativa (A–E), gabarito, pendência, needs_review.

Explicitly undecided: shared network acervo (would switch connection string to Postgres); full prova-assembly UX beyond reusing the bank.

## Brand Commitments

Name: SMEDocs, Secretaria Municipal de Educação de Muriaé. Existing template assets (Baloo 2 / Nunito static instances in `backend/smedocs/fonts/`, OFL licensed) must ship embedded and render identically offline. No invented voice or identity beyond this.

## Evidence on Hand

- `APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx` (real worst-case input, repo root) — 31 descritores, 868 questões, 647 auto gabarito.
- `Proposta Muriaé 2026.pdf` — proposal context.
- `CLAUDE.md` / `PLANO.md` — measured DOCX findings and phased plan (F0/F0.5/F0.6 concluded).
- `backend/smedocs/fonts/` — Baloo 2 + Nunito statics + OFL license.
- `gabarito/respostas.json` — versioned hand-filled answers (first batch of 8, descritores 2–3).
- `profiles/banco-muriae.json` — versioned ingestion preset; `tests/fixtures/` + `tests/check_regression.py` (23 checks).
- No testimonials, customers, benchmarks, pricing or deployment claims on hand — future work must not fabricate them.

## Product Principles

1. Never guess — surface uncertainty for human decision instead of hallucinating structure, answers or layout.
2. Preserve the math — a dropped or corrupted formula invalidates the whole question; fidelity outranks elegance.
3. Offline and reproducible — same input plus same versioned overlay yields the same output, without network.
4. Bank over document — every extraction enriches a durable, filterable acervo, not a one-off PDF.
5. Inspectable pipeline — each stage's artifact on disk beats hidden magic; counts come from measurement, not estimates.
