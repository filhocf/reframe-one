# reframe-one — Especificação Técnica v0.1

## Objetivo

Comando único que transforma `nome.kdenlive` (episódio longo horizontal) em `nome-cortes.kdenlive` (projeto vertical pronto para renderizar cortes).

## Uso

```bash
reframe-one generate leticia.kdenlive --transcript leticia-transcricao.json
```

**Output:** `leticia-cortes.kdenlive` + `leticia-cortes.kdenlive.ass`

## Input

- `nome.kdenlive` — projeto Kdenlive do episódio longo (1920×1080, 29.97fps)
  - Contém: abertura YT + vídeo bruto + SVGs de nomes
- `nome-transcricao.json` — transcrição Whisper com word-level timestamps

## Output

- `nome-cortes.kdenlive` — projeto Kdenlive vertical (1080×1920, 30fps) com:
  - Vídeo bruto (sem abertura, sem SVGs)
  - Zoom 320% (qtblend rect 3456×6144)
  - Keyframes de pan no eixo X (baseado em scene detection)
  - Fechamento Instagram entre cada corte (guide-based)
- `nome-cortes.kdenlive.ass` — legendas karaoke (word-highlight)

## Pipeline Interno

```
1. Parsear nome.kdenlive (XML)
   → Extrair: path do vídeo bruto, path da abertura, duração
   → Identificar segmentos usados (in/out points do bruto na timeline)

2. Detectar cenas no vídeo bruto (ffmpeg scene detect)
   → Lista de timestamps de troca de câmera

3. Classificar câmeras (face count por segmento)
   → Cada segmento: "central" | "entrevistadores" | "entrevistada"

4. Gerar keyframes de pan
   → Mapear câmera → posição X:
     central → X=0, Y=0, W=1080, H=1920 (sem zoom)
     entrevistadores → X=-1400, Y=-2112, W=3456, H=6144
     entrevistada → X=-1900, Y=-2112, W=3456, H=6144

5. Gerar legendas karaoke ASS
   → Whisper JSON → ASS com tags \k por palavra

6. Montar XML do projeto vertical
   → Perfil: 1080×1920, 30fps
   → Playlist: segmentos do bruto (mesmos in/out do projeto longo, sem abertura)
   → Filtros: qtblend com keyframes de pan
   → Subtítulo: referência ao .ass
   → Fechamento: inserir entre cortes (usando guides como separadores)

7. Salvar nome-cortes.kdenlive
```

## Estrutura do XML de Saída

```xml
<mlt version="7.38.0">
  <profile width="1080" height="1920" frame_rate_num="30" .../>
  
  <!-- Clip: vídeo bruto -->
  <chain id="chain0">
    <property name="resource">video-bruto.mp4</property>
  </chain>
  
  <!-- Clip: fechamento Instagram -->
  <chain id="chain1">
    <property name="resource">fechamento papo podcast Insta.mp4</property>
  </chain>
  
  <!-- Timeline: segmentos com qtblend -->
  <playlist id="playlist0">
    <entry in="00:00:02.867" out="00:02:19.133" producer="chain0">
      <filter>
        <property name="mlt_service">qtblend</property>
        <property name="rect">00:00:02.867=-1464 -2112 3456 6144 1.0</property>
      </filter>
    </entry>
    <entry producer="chain1"/>  <!-- fechamento -->
    <entry in="00:02:46.567" out="00:05:27.567" producer="chain0">
      ...
    </entry>
  </playlist>
</mlt>
```

## Configuração

Arquivo `reframe.toml` (opcional, na pasta do episódio):

```toml
[positions]
central = { x = 0, y = 0, w = 1080, h = 1920 }
entrevistadores = { x = -1400, y = -2112, w = 3456, h = 6144 }
entrevistada = { x = -1900, y = -2112, w = 3456, h = 6144 }

[paths]
closing = "../../00 Comum/fechamento papo podcast Insta.mp4"
opening = "../../00 Comum/abertura papo podcast YT.mp4"

[subtitles]
style = "karaoke"  # karaoke | simple
font = "Arial"
fontsize = 80
color = "&H0000FFFF"
```

## Simplificações v0.1

Para o primeiro corte funcional:
- [ ] Scene detection → classificação por face count (OpenCV DNN)
- [ ] Pan: corte seco entre posições (sem interpolação suave)
- [ ] Sem seleção automática de "melhores momentos" — usa todos os segmentos do projeto longo
- [ ] Guides manuais definem onde cada corte começa/termina (preservar do projeto original se existirem)
