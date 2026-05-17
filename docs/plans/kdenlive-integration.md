# Plano: Integração Kdenlive ↔ Kiro (Chat + Observação)

## Objetivo

Permitir que o Claudio converse com o Kiro de dentro do Kdenlive e que o Kiro
observe o estado da timeline em tempo real.

## Arquitetura

```
┌─────────────────────────────────────────────────────┐
│ Kdenlive (fork com RPC)                             │
│                                                     │
│  ┌──────────────┐    ┌──────────────────────────┐  │
│  │ Widget QML   │    │ RPC Server (porta 9876)   │  │
│  │ (chat panel) │    │ 86 métodos JSON-RPC       │  │
│  │              │    │ + notifications push      │  │
│  └──────┬───────┘    └──────────┬───────────────┘  │
│         │ WebSocket             │ WebSocket         │
└─────────┼───────────────────────┼──────────────────┘
          │                       │
          ▼                       ▼
┌─────────────────────────────────────────────────────┐
│ kdenlive-bridge (FastAPI + WebSocket)  porta 8765   │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ Chat WS    │  │ RPC Client │  │ State Cache  │ │
│  │ (widget)   │  │ (→ 9876)   │  │ (timeline)   │ │
│  └────────────┘  └────────────┘  └──────────────┘ │
│                                                     │
│  ┌────────────────────────────────────────────────┐ │
│  │ MCP Server (stdio ou HTTP)                     │ │
│  │ Tools: get_timeline, seek, insert_clip, etc.   │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────┐
│ Kiro CLI            │
│ (usa MCP tools)     │
└─────────────────────┘
```

## Fases

### Fase 1: Bridge Python (HOJE — sem recompilar Kdenlive)

Backend que conecta ao RPC existente (porta 9876) e expõe como MCP.

**Entregáveis:**
- `kdenlive-bridge/` — pacote Python
- Conecta ao WebSocket RPC do Kdenlive (porta 9876)
- Expõe MCP tools para o Kiro:
  - `kdenlive_get_state` — timeline, playhead, tracks, clips
  - `kdenlive_seek` — mover playhead
  - `kdenlive_get_clip_at` — info do clip na posição atual
  - `kdenlive_add_marker` — adicionar guide
  - `kdenlive_render_zone` — renderizar zona selecionada
- Polling de estado (a cada 1s): playhead position, selected clip, zoom

**Resultado:** Kiro pode observar e controlar o Kdenlive via MCP.

### Fase 2: Widget QML (AMANHÃ — requer rebuild mínimo)

Painel lateral no Kdenlive com chat.

**Entregáveis:**
- `src/chat/ChatWidget.qml` — UI do chat (input + mensagens)
- `src/chat/ChatBridge.cpp/h` — C++ bridge WebSocket → QML
- Conecta ao bridge (porta 8765)
- Envia mensagens do usuário → bridge → Kiro
- Recebe respostas do Kiro → exibe no painel

**Resultado:** Claudio conversa com Kiro sem sair do Kdenlive.

### Fase 3: Eventos push (DEPOIS)

Kdenlive notifica o bridge quando algo muda.

**Entregáveis:**
- RPC notifications: `timeline.changed`, `playhead.moved`, `clip.selected`
- Bridge recebe e atualiza state cache
- Kiro reage a eventos (ex: "vi que tu selecionou o clip 3, quer ajustar?")

## Fase 1 — Implementação Detalhada

### Estrutura

```
kdenlive-bridge/
├── pyproject.toml
├── src/
│   └── kdenlive_bridge/
│       ├── __init__.py
│       ├── rpc_client.py      # WebSocket client → Kdenlive RPC
│       ├── mcp_server.py      # MCP tools expostos ao Kiro
│       └── state.py           # Cache de estado (timeline, playhead)
└── tests/
```

### Dependências

- `websockets` — client WebSocket para RPC
- `mcp` — MCP SDK Python
- `fastapi` + `uvicorn` — HTTP/WS server (para widget QML na fase 2)

### MCP Tools (Fase 1)

| Tool | Descrição | RPC Method |
|------|-----------|------------|
| `kdenlive_ping` | Verifica conexão | `rpc.ping` |
| `kdenlive_get_project` | Info do projeto aberto | `project.getInfo` |
| `kdenlive_get_timeline` | Estado da timeline (tracks, clips) | `timeline.getState` |
| `kdenlive_seek` | Mover playhead | `timeline.seek` |
| `kdenlive_get_markers` | Listar guides/markers | `markers.getAll` |
| `kdenlive_add_marker` | Adicionar guide | `markers.add` |
| `kdenlive_render` | Renderizar projeto/zona | `render.start` |
| `kdenlive_save` | Salvar projeto | `project.save` |

### Teste

1. Abrir Kdenlive (fork com RPC)
2. Rodar bridge: `python -m kdenlive_bridge`
3. Kiro usa tools: `kdenlive_ping` → `{"pong": true}`

## Pré-requisitos

- [x] Fork Kdenlive com RPC buildado (`~/git/kdenlive/obj-x86_64-linux-gnu/bin/kdenlive`)
- [x] RPC funcional na porta 9876 (testado 12/mai)
- [ ] Instalar fork em vez do pacote distro (ou rodar do build dir)
- [ ] Bridge implementado e registrado no mcp.json

## Riscos

- Fork desatualizado vs upstream (26.04.1 lançado com fix de segurança)
- Widget QML pode conflitar com layouts existentes
- RPC notifications podem não cobrir todos os eventos necessários
