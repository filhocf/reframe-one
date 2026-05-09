# PRD: reframe-one

## Problema

Editar cortes verticais (1080×1920) de um podcast gravado em horizontal (1920×1080) com 3 câmeras é um processo manual demorado: requer assistir o episódio inteiro, identificar trocas de câmera, criar keyframes de pan (zoom 320% + posição X) para enquadrar quem fala, e gerar legendas sincronizadas. Cada episódio leva ~2h de trabalho manual no Kdenlive.

## Personas

- **Editor (Claudio)**: recebe o vídeo bruto, edita o episódio longo, precisa gerar os cortes verticais com mínimo esforço manual
- **Produtora (Mari Tânia)**: define quais trechos viram cortes, valida qualidade final, publica nas plataformas

## Features

- [x] Parsear projeto .kdenlive existente (episódio longo editado)
- [x] Detectar trocas de cena no vídeo bruto (ffmpeg scene detection)
- [x] Classificar câmeras por face count (OpenCV DNN)
- [x] Gerar keyframes de pan automáticos (câmera → posição X)
- [x] Gerar legendas karaoke ASS (word-highlight via tags \k)
- [x] Gerar projeto .kdenlive vertical completo (pronto para render)
- [ ] Detecção de falante por lip movement (MediaPipe)
- [ ] Seleção automática de melhores momentos (LLM ou heurística)
- [ ] Ajuste fino de posição X por falante (não só por câmera)

## Critérios de Aceite

- [ ] Comando `reframe-one generate nome.kdenlive` gera `nome-cortes.kdenlive` sem erros
- [ ] Projeto abre no Kdenlive sem warnings
- [ ] Keyframes de pan correspondem às trocas de câmera reais
- [ ] Legendas ASS sincronizadas com word-level timing
- [ ] Cortes renderizados são publicáveis (vertical 1080×1920, qualidade alta)

## Fora de Escopo (v0.1)

- Renderização automática (o editor revisa antes de renderizar)
- Upload para plataformas (YouTube, TikTok, Instagram)
- Edição do episódio longo (só os cortes verticais)
- Seleção de trechos (por enquanto usa todos os segmentos do projeto longo)
- Transcrição (usa JSON Whisper pré-existente)
