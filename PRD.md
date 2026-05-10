# PRD: reframe-one

## Problema

Editar cortes verticais (1080×1920) de um podcast gravado em horizontal (1920×1080) com 3 câmeras é um processo manual demorado: requer assistir o episódio inteiro, identificar trocas de câmera, criar keyframes de pan, gerar legendas sincronizadas, e selecionar os melhores momentos. Cada episódio leva ~2h de trabalho manual no Kdenlive.

## Personas

- **Editor (Claudio)**: recebe o vídeo bruto, edita o episódio longo, precisa gerar os cortes verticais com mínimo esforço manual
- **Produtora (Mari Tânia)**: define quais trechos viram cortes, valida qualidade final, publica nas plataformas

## Features

### Pipeline Core
- [x] F01: Parsear projeto .kdenlive existente (episódio longo editado)
- [x] F02: Detectar trocas de cena no vídeo bruto (ffmpeg scene detection)
- [x] F03: Classificar câmeras por face count (OpenCV DNN)
- [x] F04: Detectar falante por lip movement (MediaPipe)
- [x] F05: Gerar projeto .kdenlive vertical completo (pronto para render)

### Legendas
- [x] F06: Legendas karaoke ASS (word-highlight via tags \k)
- [x] F07: Múltiplos estilos visuais (karaoke, hormozi, word-pop, papo-saude)
- [x] F08: Highlight com fundo colorido por palavra (estilo papo-saude)
- [x] F09: Limpeza de texto (fillers, gaguejos) — local + LLM
- [x] F10: Line breaking inteligente (~50 chars)
- [x] F11: Sync offset configurável (compensar atraso Whisper)

### Seleção e Configuração
- [x] F12: Seleção manual de clips (--clips time ranges)
- [x] F13: Seleção por LLM (--auto-select, score por engajamento)
- [x] F14: Config por episódio (cameras, closing, style via JSON/YAML)

### UX Pipeline
- [x] F15: Timeline guides (marcadores início/fim de cada corte)
- [x] F16: Gap automático (5s blank entre clips consecutivos)
- [x] F17: Selective steps (--steps para pular recomputação)
- [x] F18: Cache intermediário (scenes + cameras + speakers)
- [x] F19: Progress display com percentagem

### Pendentes
- [ ] F20: Ajuste fino de posição X por falante (não só por câmera)
- [ ] F21: Interface LLM via Kiro subagent
- [ ] F22: Renderização automática dos cortes

## Critérios de Aceite

- [x] `reframe-one generate nome.kdenlive` gera `nome-cortes.kdenlive` sem erros
- [x] Projeto abre no Kdenlive sem warnings
- [x] Keyframes de pan correspondem às trocas de câmera reais
- [x] Legendas ASS sincronizadas com word-level timing
- [ ] Cortes renderizados são publicáveis (vertical 1080×1920, qualidade alta)
- [ ] Estilo papo-saude visualmente correto (fundo verde na palavra ativa)

## Fora de Escopo (v0.2)

- Renderização automática (o editor revisa antes de renderizar)
- Upload para plataformas (YouTube, TikTok, Instagram)
- Edição do episódio longo (só os cortes verticais)
- Transcrição (usa JSON Whisper pré-existente)
- UI gráfica (CLI only)
