# MEMORY: reframe-one

## Estado Atual

- **Versão**: 0.2.0-dev (não publicado)
- **Status**: pipeline funcional com 7 features novas, testado com ep 04
- **Último teste**: ep 04 (Silvana e Melissa) — 128 segments, estilo papo-saude
- **Commits**: 20 (main)
- **Testes**: 34 passando
- **Issues**: 15 (13 fechadas, 2 abertas)

## Sessão 10/mai/2026 (sirdata)

### Feito (6 PRs mergeados)
- PR #4: Smart subtitles — 3 estilos (karaoke, hormozi, word-pop) + LLM cleanup + line breaking
- PR #6: Integrar ASS no .kdenlive (avfilter.subtitles)
- PR #8: Clip selection (manual time ranges + LLM scoring)
- PR #10: Per-episode config (cameras, closing, subtitle_style via JSON/YAML)
- PR #12: Fix progress display (percentage durante classify + speaker detect)
- PR #14: Timeline guides (verde=início, vermelho=fim) + 5s gap entre clips consecutivos
- PR #16: Selective step execution (--steps 1,5,6 usa cache, evita re-rodar 7min)

### Fixes não commitados (em andamento)
- Estilo "papo-saude": highlight com fundo verde por palavra (per-word events)
- Offset de legendas: subtrair in-point do segmento (começa em 0:00:00)
- Sync offset: -50ms para compensar atraso do Whisper
- Primeiro entry começa no in-point do projeto fonte (não na 1ª scene change)
- DEFAULT_CLOSING restaurado (estava vazio após fix do Gemini)

### Bugs encontrados durante teste
- Closing path vazio → "arquivo faltante" ao abrir no Kdenlive
- Legendas começavam em 4.7s em vez de 0:00:00 (faltava subtrair offset)
- Primeiro entry começava em 19.5s (faltava scene artificial no in-point)
- Estilo karaoke simples não faz highlight de fundo por palavra

### Próximo
- Commitar fixes pendentes + PR
- Testar visualmente no Kdenlive (estilo papo-saude com fundo verde)
- Ajustar sync_offset_ms se necessário (-50 pode não ser suficiente)
- Verificar posições de câmera (X=0 para entrevistadora à esquerda)

## Sessão 09/mai/2026 (sirdata)

### Feito
- Repo criado e pipeline base implementado em 1 sessão
- Scene detection + camera classification + speaker detection
- Karaoke subtitles + Kdenlive XML generation
- CI: GitHub Actions + Gemini Code Assist
- 12 commits, 21 testes

## Decisões

- **Gerar XML direto** (não usar kdenlive-api)
- **Face count para classificar câmera** (3+ = central, 2 = entrevistadores, 1 = entrevistada)
- **Per-word events para highlight com fundo** (não \k tags — \k só muda cor do texto)
- **Cache intermediário** (scenes + cameras + speakers em JSON, evita re-rodar 7min)
- **LLM configurável** (ollama/groq/openai, fallback local sem LLM)
- **Offset de legendas** = in-point do segmento fonte (timestamps relativos à timeline)
- **Sync offset -50ms** (Whisper tende a reportar timestamps atrasados)

## Contexto

- **Papo Saúde**: videocast UNISUL, esposa Mari Tânia
- **Pasta**: /home/claudio/Insync/ssd/papo-saude/
- **Episódios**: 01-07 (01-02 completos, 03-07 em progresso)
- **Cor do projeto**: #85a95f (verde Papo Saúde)
