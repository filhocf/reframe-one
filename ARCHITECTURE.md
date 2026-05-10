# ARCHITECTURE: reframe-one

## Stack

- Python 3.12+
- FFmpeg (scene detection, frame extraction)
- OpenCV (face detection via DNN — res10 caffe model)
- MediaPipe (speaker detection via lip movement)
- pysubs2 (geração de legendas ASS)
- httpx (chamadas LLM)
- xml.etree.ElementTree (geração de XML Kdenlive/MLT)

## Componentes

```
reframe-one/src/reframe_one/
├── cli.py              # Entry point — orquestra pipeline, --steps, cache
├── config.py           # EpisodeConfig dataclass + JSON/YAML loader
├── parse_kdenlive.py   # Lê .kdenlive, extrai vídeo bruto + segmentos
├── scene_detect.py     # ffmpeg scene detect + classificação de câmera
├── speaker_detect.py   # MediaPipe FaceLandmarker lip movement analysis
├── clip_selector.py    # Seleção de clips (manual time ranges + LLM scoring)
├── subtitles.py        # Whisper JSON → ASS (4 estilos + cleanup + line break)
├── llm.py              # Interface LLM configurável (ollama/groq/openai)
└── kdenlive_gen.py     # Gera XML .kdenlive vertical com pan + guides + gap
```

## Fluxo de Dados

```
nome.kdenlive (input) + transcricao.json + episode.json (config)
    │
    ├─[1] parse_kdenlive.py → ProjectInfo (video_path, segments)
    │
    ├─[2] scene_detect.py → [SceneChange(timestamp, score)]
    │
    ├─[3] scene_detect.classify_cameras() → [{start, end, camera}]
    │
    ├─[4] speaker_detect.py → pan_x por segmento (lip movement)
    │
    ├─[5] clip_selector.py → filtra segmentos (manual ou LLM)
    │     subtitles.py → .ass (estilo configurável + cleanup)
    │
    └─[6] kdenlive_gen.py → .kdenlive vertical (pan + subs + guides + gap)

Cache: nome-cache.json (scenes + camera_segments + speaker data)
```

## Estilos de Legenda

| Estilo | Técnica | Visual |
|--------|---------|--------|
| karaoke | `\k` tags | Amarelo ativo, branco inativo |
| hormozi | `\k` tags | Cinza→branco, Montserrat Bold |
| word-pop | `\kf` tags | Fill progressivo, centro da tela |
| papo-saude | Per-word events | Cinza inativo, branco + fundo verde #85a95f ativo |

## Modelo de Câmeras

Classificação por face count:
- 3+ faces → central (todos)
- 2 faces → entrevistadores (esquerda)
- 1 face → entrevistada (direita)
- 0 faces → fallback entrevistadores

Posições (configuráveis via episode.json):

| Câmera | X | Y | W | H |
|--------|---|---|---|---|
| central | -1200 | -2112 | 3456 | 6144 |
| entrevistadores | -1400 | -2112 | 3456 | 6144 |
| entrevistada | -1900 | -2112 | 3456 | 6144 |

## Cache e Steps

Pipeline completo: ~7min (scene detect + classify + speaker detect).
Com `--steps 1,5,6`: ~0.1s (usa cache para steps 2-4).

Cache salvo em `{base}-cache.json` após steps 2-4.

## Dependências Externas

- Modelo face detection: `res10_300x300_ssd_iter_140000.caffemodel`
- Modelo lip detection: `~/.mediapipe/face_landmarker.task` (3.6MB)
- Fechamento Instagram: configurável via episode.json (default: `00 Comum/fechamento papo podcast Insta.mp4`)
- LLM (opcional): Ollama local, Groq, ou OpenAI
