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

## Integração Kdenlive (decisões 16/mai/2026)

### Modelo de Operação

O reframe-one é um **pipeline externo** que se comunica com o Kdenlive via RPC.
NÃO é um plugin embutido no Kdenlive.

```
reframe-one (Python, standalone)
    │
    ├── Modo offline: gera .kdenlive XML sem Kdenlive aberto
    │
    └── Modo interativo: controla Kdenlive via JSON-RPC (porta 9876)
            │
            └── Chat QML (widget lateral no Kdenlive)
                    → WebSocket → FastAPI backend → RPC 9876
```

### Chat QML no Kdenlive

Widget dock (painel lateral) para o usuário conversar com o agente IA
de dentro do Kdenlive, sem alternar janelas.

Arquitetura:
- **Widget QML** no fork Kdenlive (dock widget, como monitor de projeto)
- **C++ bridge** → WebSocket client conecta ao backend
- **Backend FastAPI** (Python) → interpreta linguagem natural → executa via RPC
- **Bidirecional**: agente notifica o usuário (render terminou, corte sugerido)

Referência: D-Ogi/kdenlive (fork com D-Bus scripting + widget chat QML).

### Ecossistema Externo

| Projeto | Autor | Abordagem |
|---------|-------|-----------|
| D-Ogi/kdenlive | D-Ogi | Fork com D-Bus scripting API |
| D-Ogi/kdenlive-api | D-Ogi | Python client (PyPI 0.2.1), JSON-RPC WebSocket |
| D-Ogi/mcp-kdenlive | D-Ogi | MCP server (wrapa kdenlive-api) |
| Nosso fork | Galdério | JSON-RPC porta 9876, 86 métodos, glue code C++ |

### Decisões

- **Pipeline externo > plugin embutido**: mais flexível, atualiza sem recompilar
- **Fork próprio > upstream**: upstream não tem scripting API (mid-term no roadmap)
- **RPC porta 9876**: já funcional, 86 métodos disponíveis
- **Propor upstream**: só quando tivermos caso de uso sólido funcionando
  (dev principal pediu exemplos concretos — discuss.kde.org/t/10055)

### Upstream Status (mai/2026)

- Roadmap: "Scripting support (Python API)" = **mid term**
- Interfaces existentes: frei0r/MLT (efeitos), C++ (tudo). Nenhuma scripting pública.
- Comunidade pede plugins desde jan/2024, dev resiste sem caso de uso concreto.
