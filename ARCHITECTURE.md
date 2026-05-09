# ARCHITECTURE: reframe-one

## Stack

- Python 3.13
- FFmpeg (scene detection, frame extraction)
- OpenCV (face detection via DNN — res10 caffe model)
- pysubs2 (geração de legendas ASS)
- xml.etree.ElementTree (geração de XML Kdenlive/MLT)

## Componentes

```
reframe-one/src/reframe_one/
├── cli.py              # Entry point — orquestra o pipeline
├── parse_kdenlive.py   # Lê .kdenlive, extrai vídeo bruto + segmentos + guides
├── scene_detect.py     # ffmpeg scene detect + classificação de câmera (face count)
├── subtitles.py        # Whisper JSON → ASS karaoke (word-highlight)
└── kdenlive_gen.py     # Gera XML .kdenlive vertical com qtblend keyframes
```

## Fluxo de Dados

```
nome.kdenlive (input)
    │
    ├── parse_kdenlive.py → ProjectInfo (video_path, segments, guides)
    │
    ├── scene_detect.py
    │   ├── detect_scenes(video) → [SceneChange(timestamp, score)]
    │   └── classify_cameras(video, scenes) → [{start, end, camera, face_count}]
    │
    ├── subtitles.py
    │   └── generate_karaoke_ass(whisper_json) → .ass
    │
    └── kdenlive_gen.py
        └── generate_vertical_project(video, closing, segments, cameras) → .kdenlive

nome-cortes.kdenlive (output)
```

## Modelo de Câmeras

Vídeo bruto 1920×1080 com 3 ângulos (cortes no próprio vídeo):
- **Central**: todos os participantes visíveis
- **Entrevistadores**: enquadra quem pergunta (lado esquerdo)
- **Entrevistada**: enquadra a convidada (lado direito)

Classificação por face count no frame:
- 3+ faces → central
- 2 faces → entrevistadores
- 1 face → entrevistada
- 0 faces → fallback entrevistadores

## Reframe Vertical

Canvas: 1080×1920. Vídeo escalado 320% (3456×6144). Pan via qtblend rect:

| Câmera | X | Y | W | H |
|--------|---|---|---|---|
| central | 0 | 0 | 1080 | 1920 |
| entrevistadores | -1400 | -2112 | 3456 | 6144 |
| entrevistada | -1900 | -2112 | 3456 | 6144 |

## Formato XML de Saída

MLT 7.38.0 compatível com Kdenlive 25.12+:
- Profile vertical 1080×1920 30fps
- Chains com kdenlive:id + kdenlive:control_uuid consistentes
- Playlists de áudio (A1, A2) e vídeo (V1)
- Filtros qtblend com múltiplos keyframes (semicolon-separated rect)
- Fechamento Instagram entre segmentos
- Fades from/to black nas transições

## Dependências Externas

- Modelo face detection: `res10_300x300_ssd_iter_140000.caffemodel` (OpenCV samples)
- Fechamento Instagram: `00 Comum/fechamento papo podcast Insta.mp4`
- Abertura YouTube: `00 Comum/abertura papo podcast YT.mp4` (removida nos cortes)
