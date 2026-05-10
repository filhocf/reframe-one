# MEMORY: reframe-one

## Estado Atual

- **Versão**: 0.1.0-dev (não publicado)
- **Status**: pipeline funcional, testado com ep 04, abre no Kdenlive sem erros
- **Último teste**: ep 04 (Silvana e Melissa) — 127 cortes, 91 com speaker detection, 4 trilhas OK
- **Commits**: 12 (main)
- **Testes**: 21 passando

## Sessão 09/mai/2026 (sirdata)

### Feito
- Repo criado e pipeline completo implementado em 1 sessão
- Scene detection (ffmpeg) + camera classification (OpenCV face count)
- Speaker detection (MediaPipe FaceLandmarker lip movement)
- Karaoke subtitles (ASS com tags \k)
- Kdenlive XML generation (vertical 1080x1920, hard cuts)
- CI: GitHub Actions (ruff + pytest), Gemini Code Assist
- Docs: README, PRD, ARCHITECTURE, MEMORY, CHANGELOG

### Bugs corrigidos
- UUIDs inconsistentes entre chains → mesmo UUID por clip
- Keyframes interpolados → 1 entry por corte (hard cut)
- A2 com entries → A2 vazio, A1 espelha V1
- Falta V2 → adicionada trilha V2 vazia
- Central sem zoom → central com zoom (X=-1200)

### Próximo
- Legendas: ~50 chars, remover fillers, quebra inteligente
- Integrar ASS no .kdenlive
- Seleção de cortes, config por episódio

## Decisões

- **Gerar XML direto** (não usar kdenlive-api) — zero dependências extras, mais portável
- **Face count para classificar câmera** — simples e funciona para 3 ângulos fixos
- **Legendas karaoke via tags \k** — ASS nativo, Kdenlive renderiza sem plugins
- **Podcli descartado para reframe** — bom para seleção de momentos, mas faz crop estático

## Contexto do Projeto

- **Papo Saúde**: videocast UNISUL, esposa Mari Tânia
- **Pasta de trabalho**: /home/claudio/Insync/ssd/papo-saude/
- **Episódios**: 01-07, cada um com vídeo bruto + .kdenlive + transcrição JSON
- **Workflow**: bruto → episódio longo (horizontal) → cortes (vertical) → publicação multi-plataforma
