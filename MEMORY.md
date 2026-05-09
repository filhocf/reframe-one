# MEMORY: reframe-one

## Estado Atual

- **Versão**: 0.1.0-dev (não publicado)
- **Status**: primeiro teste funcional gerado, com bugs de XML sendo corrigidos
- **Último teste**: ep 04 (Silvana e Melissa) — .kdenlive gerado com 127 keyframes de pan

## Sessão Atual (09/mai/2026 sirdata)

### Feito
- Repo criado: https://github.com/filhocf/reframe-one
- Pipeline completo implementado: parse → scenes → classify → subs → kdenlive
- Testado com ep 04: gera .kdenlive + .ass
- Fix: UUIDs consistentes entre chains (eliminava erros de bin no Kdenlive)
- Fix: múltiplos keyframes por segmento (antes era 1 só por segmento inteiro)

### Problemas Conhecidos
- Kdenlive abriu com warnings "Clipe inválido recuperado" (fix de UUID aplicado, retestar)
- Classificação de câmera pode ter falsos positivos (face detection nem sempre acerta)
- Posições X são fixas (-1400/-1900) — no manual, Claudio ajusta ±100px por episódio

### Próximo
- Validar que o .kdenlive abre sem erros após fix de UUID
- Verificar se os keyframes de pan estão nos momentos corretos
- Testar render de 1 corte no Kdenlive
- Implementar lip movement detection (fase 2)

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
