# ECHO // MULTI-MIND

> A local, privacy-first interface for multi-model AI conversations — powered by Ollama and a lightweight Flask proxy with dual RAG engines (keyword + semantic embeddings), persistent knowledge bases, custom awareness injection, real-time token monitoring, Multi-AI System presets, and full flow control (skip, pause, inject, resume).

```
 ╔══════════════════════════════════════════════════╗
 ║   MODEL A  ↔  MODEL B  ↔  MODEL C  ↔  MODEL D  ║
 ║        Auto conversation or group reply          ║
 ╚══════════════════════════════════════════════════╝
```

---

## What Is Echo Multi-Mind?

Echo Multi-Mind is a self-hosted, multi-model chat environment. Instead of talking to one AI at a time, you can:

- **Run up to four models simultaneously** — each with its own name, personality, system prompt, and inference parameters.
- **Watch models talk to each other** autonomously for N turns, seeded by your message.
- **Control the flow** — stop the entire turn, skip a single model, pause mid-sequence and inject your own message, then resume.
- **Feed long-term memory** via two RAG engines: a fast keyword scorer (no dependencies) or semantic Ollama embeddings.
- **Save knowledge bases** to disk — load your embeddings instantly in any future session without re-processing.
- **Save and reload every conversation** from a persistent sidebar with folder organisation.
- **Save multi-agent configurations** as named Systems presets — load a full Trialogue, Debate, or any custom layout in one click.

Everything runs locally. No API keys. No data sent anywhere except to your own Ollama instance.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Feature List](#feature-list)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Technical Deep Dive](#technical-deep-dive)
  - [Backend — echo_server.py](#backend--echo_serverpy)
  - [RAG System — Keyword Mode](#rag-system--keyword-mode)
  - [RAG System — Embedding Mode](#rag-system--embedding-mode)
  - [Knowledge Base Persistence](#knowledge-base-persistence)
  - [RAG Template System](#rag-template-system)
  - [AI Awareness Injection](#ai-awareness-injection)
  - [Chat Persistence & Duplication](#chat-persistence--duplication)
  - [Multi-AI Systems Presets](#multi-ai-systems-presets)
  - [Frontend — index.html](#frontend--indexhtml)
  - [Streaming Protocol & Token Counters](#streaming-protocol--token-counters)
  - [Flow Control — Stop, Skip, Pause, Resume](#flow-control--stop-skip-pause-resume)
  - [Thinking Tag Renderer](#thinking-tag-renderer)
  - [Conversation History & Role Mapping](#conversation-history--role-mapping)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Usage Guide](#usage-guide)
- [FAQ](#faq)
- [Changelog](#changelog)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                      Browser (UI)                         │
│                  echo_ui/index.html                       │
│  Fetch → /api/chat  /api/tags  /api/rag/*                 │
│          /api/chats/*  /api/knowledge/*                   │
│          /api/profiles/*  /api/systems/*                  │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP (port 8080)
┌───────────────────────────▼──────────────────────────────┐
│               Flask Server (echo_server.py)               │
│                                                           │
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Keyword RAG │  │ Embedding   │  │   Chat Store    │  │
│  │  (in-memory) │  │ RAG (cosine)│  │   echo_chats/   │  │
│  └──────┬───────┘  └──────┬──────┘  └─────────────────┘  │
│         │                 │                               │
│  ┌──────┴─────────────────┴──────┐  ┌─────────────────┐  │
│  │       CORS Proxy /api/chat    │  │  Knowledge Base │  │
│  │       RAG injection           │  │  echo_knowledge/│  │
│  └──────────────┬────────────────┘  └─────────────────┘  │
│                                                           │
│  ┌─────────────────────┐  ┌──────────────────────────┐   │
│  │  Profiles           │  │  Systems Presets         │   │
│  │  echo_profiles/     │  │  echo_systems/           │   │
│  └─────────────────────┘  └──────────────────────────┘   │
└─────────────────┼─────────────────────────────────────────┘
                  │ HTTP (port 11434)
        ┌─────────▼──────────┐
        │     Ollama API     │
        │  Model A / B / C / D  │
        └────────────────────┘
```

The Flask server has six jobs:

1. **Solve CORS** — browsers block direct `fetch()` to `localhost:11434`. The proxy removes that restriction without touching Ollama's config.
2. **Inject RAG context** — before forwarding a chat request, the server retrieves relevant chunks and prepends them to the system prompt using a configurable template.
3. **Persist chats** — saves, loads, moves, and deep-copies conversations as JSON files in `echo_chats/`.
4. **Persist knowledge bases** — saves and loads chunked + embedded knowledge to `echo_knowledge/` so you never have to re-process files between sessions.
5. **Persist systems** — saves and loads multi-agent configuration presets to `echo_systems/systems.json`.
6. **Serve the UI** — the single `index.html` is served as a static asset, so the entire app runs from one `python echo_server.py` command.

---

## Feature List

| Feature | Details |
|---|---|
| **Multi-Model (up to 4)** | Slots A, B, C, D — each with its own display name, system prompt, and inference parameters |
| **Auto Mode** | Fully autonomous AI ↔ AI conversation for N configurable turns across all active slots |
| **Turn Countdown** | Live header pill showing current turn / total (e.g. `TURN 3 / 10`) during AUTO |
| **Manual / Inject Mode** | Send your own message; all active models respond sequentially |
| **Global Stop** | ■ STOP terminates the **entire turn** — all remaining models in the sequence are cancelled, not just the active stream |
| **Skip Model** | ⏭ SKIP aborts only the current model's stream and moves immediately to the next slot in the sequence |
| **Pause / Inject / Resume** | ⏸ PAUSE freezes the turn; type a message and press INJECT & RESUME to insert it mid-sequence, or just RESUME to continue |
| **Per-Model Parameters** | Temperature, Top-P, Top-K, Max Tokens, Repeat Penalty, Context Length — set independently per slot |
| **Display Names** | Each slot has a custom display name used in chat bubbles, exports, and awareness injection |
| **AI Awareness Injection** | Optionally prepend identity text to each slot's system prompt; Standard mode (auto-generated) or Custom mode (your own template with `{name}` and `{others}` placeholders) |
| **Multi-AI Systems Presets** | Save complete multi-agent configurations (slots, names, prompts, params, awareness, turns) as named Systems; load in one click |
| **Built-in System Templates** | Two expert-tuned presets: **Trialogue** (Teacher ↔ Student ↔ Mediator) and **Devil's Advocate Debate** (Proposer ↔ Challenger ↔ Judge) |
| **Fork Built-in Systems** | Copy any built-in system as your own editable preset via the ⊕ FORK button |
| **Save Current as System** | ⬡ SAVE SYS button captures your live slot configuration as a new System in one click |
| **Chat Duplication** | Right-click any saved chat → Duplicate; creates a deep copy with all settings, prompts, parameters, and history intact |
| **Keyword RAG** | Load a folder of `.txt` files; keyword-overlap retrieval with `√` normalisation — no dependencies |
| **Embedding RAG** | Semantic retrieval via Ollama embedding models (cosine similarity); supports both new `/api/embed` and legacy `/api/embeddings` Ollama APIs automatically |
| **Auto-Truncation** | Chunks that exceed the embedding model's context window are automatically halved and retried — embedding never silently fails due to input length |
| **Chunk Size Warning** | UI warns when chunk size exceeds 350 words, the safe limit for small embedding models with 512-token context windows |
| **RAG Template** | Fully customisable injection template — write any text around `{context}` to control how retrieved chunks are presented to the model |
| **Knowledge Base Persistence** | Save chunked + embedded knowledge to disk; load instantly in any future session with settings restored (chunk size, overlap, model all restored automatically) |
| **Graceful Partial KB Load** | KBs with a small number of failed chunks load successfully — empty-embedding chunks are silently skipped during retrieval rather than blocking the whole load |
| **Broken KB Detection** | Detects knowledge bases where all embeddings are empty; shows ⚠ BROKEN badge with one-click repair that pre-fills all settings |
| **Auto-Enable RAG on Load** | Loading a knowledge base automatically activates the correct RAG mode — no extra toggle click needed |
| **RAG Chunk Controls** | Chunk size, overlap, and retrieve top-K all configurable from the UI without restarting |
| **RAG Chunk Estimator** | Enter a file character count; UI instantly shows estimated words, chunks produced, and chunks retrieved |
| **Embedding Progress** | Live progress bar showing chunks embedded / total during background embedding |
| **Re-embed Warning** | Banner warns if chunk size or model changed since last embed — prevents accidental use of stale vectors |
| **RAG Retrieval Log** | Per-query log showing which file and text chunk was retrieved, with timestamps — separate views for keyword and embedding mode |
| **Embed Model Unload** | Dedicated ⏏ button to evict the embedding model from VRAM via the correct Ollama endpoint |
| **Token Counters** | Per-message `↑ ctx · ↓ gen` badge + persistent header pills showing prompt tokens in and response tokens out |
| **Context Length Control** | Set `num_ctx` per model — controls the KV cache / context window Ollama allocates |
| **Custom Model Profiles** | Save a model + system prompt + all parameters as a named profile; apply to any slot in one click; stored in `echo_profiles/` folder |
| **Chat Sidebar** | Collapsible left panel listing all saved chats; updates instantly when a session ends — no page refresh needed |
| **Chat Auto-Save** | Every session saves automatically to `echo_chats/` as JSON the moment generation completes |
| **Chat Folders** | Create named folders; right-click any chat to move it or duplicate it |
| **Full State Restore** | Loading a chat restores models, display names, system prompts, all parameters, awareness settings, and RAG settings |
| **Streaming** | Responses stream token-by-token using NDJSON; UI updates in real time |
| **Smart Scroll** | Auto-scroll follows new tokens only when near the bottom — scrolling up to read pauses it |
| **Thinking Tag Support** | Detects `<think>...</think>` blocks (native field or embedded) and renders them in a collapsible panel |
| **VRAM Management** | ⏏ button per slot unloads model weights from GPU via `keep_alive: 0` |
| **Chat Export** | Download the full conversation including thinking blocks as `.txt`; separate FT export strips awareness injection |
| **Zero Dependencies UI** | Pure HTML/CSS/JS — no build step, no npm |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ | Tested on 3.10 and 3.11 |
| Ollama | Running locally at `http://localhost:11434` |
| At least one Ollama model pulled | e.g. `ollama pull qwen3:1.7b` |
| pip packages | `flask`, `requests`, `flask-cors` |

```bash
pip install flask requests flask-cors
```

For embedding RAG, pull a dedicated embedding model (optional but faster than using a chat model):

```bash
ollama pull znbang/bge:small-en-v1.5-q8_0   # fast, small (512-token context — keep chunks ≤ 350 words)
ollama pull nomic-embed-text                  # popular general-purpose
ollama pull mxbai-embed-large                 # higher quality
```

> **Note on chunk size:** Small embedding models like `bge-small` have a 512-token context window (~350 words). Echo will auto-truncate chunks that exceed this limit, but smaller chunks give cleaner semantic retrieval. The UI shows a warning banner when your chunk size setting exceeds 350 words.

Ollama installation: https://ollama.com

---

## Installation

```bash
# 1. Clone or download the repo
git clone https://github.com/yourname/echo-multi-mind.git
cd echo-multi-mind

# 2. Make sure Ollama is running and you have at least one model
ollama pull lfm2.5-thinking:1.2b    # slot A suggestion
ollama pull qwen3:1.7b              # slot B suggestion

# 3. Install dependencies
pip install flask requests flask-cors

# 4. Run the server
python echo_server.py

# 5. Open the UI
# http://localhost:8080
```

The terminal will show:

```
══════════════════════════════════════════════════════════
  ECHO // MULTI-MIND  v1.8
══════════════════════════════════════════════════════════
  UI:        http://localhost:8080
  Ollama:    http://localhost:11434
  Chats:     ./echo_chats/
  Knowledge: ./echo_knowledge/
  Profiles:  ./echo_profiles/
  Systems:   ./echo_systems/
══════════════════════════════════════════════════════════
```

---

## Project Structure

```
echo-multi-mind/
├── echo_server.py        ← Flask backend (proxy + RAG + persistence)
├── echo_chats/           ← Auto-created; stores saved chats as JSON
│   ├── 2026-03-01T...json
│   └── my-folder/
│       └── 2026-03-02T...json
├── echo_knowledge/       ← Auto-created; stores saved knowledge bases as JSON
│   └── my_notes.json
├── echo_profiles/        ← Auto-created; stores custom model profiles
│   └── profiles.json
├── echo_systems/         ← Auto-created; stores multi-AI system presets
│   └── systems.json
└── echo_ui/
    └── index.html        ← Complete frontend (HTML + CSS + JS, single file)
```

> **Upgrading from v1.7:** Drop in the new `echo_server.py` and `index.html`. The new `echo_systems/` directory is created automatically on first run. All existing chats, knowledge bases, and profiles are fully compatible.

> **Upgrading from v1.6:** The old `echo_models.json` file is automatically migrated to `echo_profiles/profiles.json` on first run. The original is renamed to `echo_models.json.bak` as a safety backup.

---

## Technical Deep Dive

### Backend — echo_server.py

The server is a single-file Flask application with no database, no ORM, no task queue. All state is held in memory at the process level, except for chats, knowledge bases, profiles, and systems which are written to disk as JSON.

`flask-cors` adds `Access-Control-Allow-Origin: *` to every response. For streaming responses, Flask uses Python generators to forward chunks as they arrive without buffering:

```python
def generate():
    for chunk in r.iter_content(chunk_size=None):
        yield chunk
return Response(generate(), content_type='application/x-ndjson')
```

---

### RAG System — Keyword Mode

Fast, dependency-free retrieval using keyword overlap with `√` normalisation.

**Chunking:**

```python
def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
```

**Scoring:**

```python
def simple_score(query, text):
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words  = set(re.findall(r'\w+', text.lower()))
    # stop words removed
    overlap = query_words & text_words
    return len(overlap) / math.sqrt(len(query_words) * max(len(text_words), 1))
```

Functionally similar to BM25 without a pre-built index. Best for personal logs and structured notes where exact terminology is consistent.

---

### RAG System — Embedding Mode

Semantic retrieval via Ollama embedding models and cosine similarity. Embedding runs in a background thread so the UI stays responsive.

**Ollama API compatibility** — automatically tries the new API first, falls back to the legacy endpoint:

```python
def get_embedding(text, model):
    # New API: POST /api/embed  { model, input }  → { embeddings: [[...]] }
    # Legacy:  POST /api/embeddings  { model, prompt }  → { embedding: [...] }
    # Auto-truncates on context-length errors by halving the text and retrying
```

**Auto-truncation** — if a chunk is too long for the embedding model's context window, `get_embedding()` detects the error response and automatically halves the text, retrying until it fits.

```
[EMBED] Context too long (3200 chars) — truncating to 1600 (trunc #1)
[EMBED] OK after 1 truncation(s) — 1600 chars
```

**Cosine similarity retrieval:**

```python
def cosine_sim(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na  = math.sqrt(sum(x*x for x in a))
    nb  = math.sqrt(sum(x*x for x in b))
    return dot / (na * nb) if na and nb else 0.0
```

Scores below `0.01` are discarded as near-zero noise.

**Trade-offs:**

| | Keyword (Local) | Embedding (Ollama) |
|---|---|---|
| Dependencies | None | Ollama embed model |
| Semantic matching | No — exact words only | Yes — meaning-aware |
| Speed | Instant | Seconds (background) |
| Works offline | Yes | Yes (local Ollama) |
| Best for | Structured notes, logs | Natural language, diverse topics |

---

### Knowledge Base Persistence

After embedding files you can save the result as a named knowledge base. The JSON file stores the text chunks, their computed embedding vectors, and all settings used to produce them.

**Save** — blocks only if every chunk has an empty embedding (fully broken). A small number of failed chunks is allowed and those chunks are noted in the server log.

**Load** — restores `chunk_size`, `overlap`, and `embed_model` back to the UI fields automatically. Chunks with empty embeddings are filtered out silently rather than blocking the load. The KB is immediately activated (RAG toggled on automatically).

**Broken KB detection** — a KB is flagged ⚠ BROKEN only when **all** of its embedding vectors are empty `[]`. Clicking **⟳ REPAIR** pre-fills the Embedding tab with the original folder, chunk size, overlap, and model.

---

### RAG Template System

The injection template controls exactly how retrieved chunks are presented to the model. Write any text; use `{context}` as the placeholder — it is replaced at request time with the top-K results formatted as `[filename] chunk text` for each result.

**Example templates:**

```
### Relevant Notes:
{context}
```

```
Use these excerpts only if directly relevant: {context}
```

```
Background knowledge (do not repeat verbatim, use to inform your answer):
{context}

If the context doesn't answer the question, say so.
```

---

### AI Awareness Injection

When enabled per slot, a short identity line is prepended to that slot's system prompt before each request.

> **Important:** Injection only provides identity. Always write a system prompt to define behavior. Without one, thinking models will spend their reasoning budget trying to invent their own purpose.

**Standard mode** (auto-generated):

```
You are Echo1. This is a multi-participant session also including Echo2.
```

**Custom mode** — write your own template with two optional placeholders:

| Placeholder | Resolves to |
|---|---|
| `{name}` | This slot's display name |
| `{others}` | Comma-separated list of other participants' display names |

---

### Chat Persistence & Duplication

Chats are saved as JSON files in `echo_chats/` next to `echo_server.py`. The sidebar updates **instantly** when a session ends.

**Auto-save logic** uses a `chatDirty` flag that becomes `true` only when new messages are generated, preventing re-saves of chats loaded from disk.

**Chat Duplication (v1.8)** — right-click any chat in the sidebar and choose **📋 Duplicate**. This performs a true deep copy via `POST /api/chats/duplicate/<id>`: the full JSON is cloned (all settings, system prompts, inference parameters, awareness state, RAG settings, and the complete message log) and saved with a new timestamped ID and a `(copy)` suffix on the title. The original is completely unaffected.

Each saved file contains:

```json
{
  "id": "2026-03-03T17-38-00",
  "title": "03/03/2026 17:38",
  "models": ["lfm2.5-thinking:1.2b", "qwen3:1.7b"],
  "settings": {
    "nameA": "Echo1", "sysA": "You are Echo1...",
    "tempA": "0.7",   "ctxA": "4096",
    "awareFlagA": true, "awareModeA": "custom", "awareCustomA": "You are {name}...",
    "ragPath": "C:/notes", "useRag": true,
    "ragChunkSize": "780", "ragOverlap": "50"
  },
  "log": [...]
}
```

---

### Multi-AI Systems Presets

**Systems** are named, reusable multi-agent configurations stored in `echo_systems/systems.json`. A System captures everything needed to launch a specific type of multi-model conversation:

- Participant slot assignments (A/B/C/D), display names, and system prompts
- Inference parameters per slot (temperature, top-P, top-K, max tokens, repeat penalty, context length)
- Awareness injection on/off per slot
- Default number of turns

**Loading a System** applies all slot settings in one click: the correct slots are activated, display names are set, system prompts are filled in, parameters are applied, awareness is toggled, and the turns counter is set. Your previous slot configuration is replaced.

**Built-in templates** ship with v1.8 and are read-only but forkable:

| System | Participants | Description |
|---|---|---|
| **Trialogue** | Teacher · Student · Mediator | Socratic learning dialogue. Teacher guides with questions, Student explores with honest uncertainty, Mediator summarises and surfaces gaps. |
| **Devil's Advocate Debate** | Proposer · Challenger · Judge | Structured two-sided argument. Proposer builds the case, Challenger stress-tests it, Judge scores each exchange and poses follow-up questions. |

**Creating your own Systems:**

- Click **⬡ SYSTEMS** → **+ NEW SYSTEM** to open the editor
- Add any number of slots; configure name, system prompt, and awareness per slot
- Click ⊕ **FORK** on any built-in to copy it as a starting point for customisation
- Click **⬡ SAVE SYS** in the config bar to instantly save your current live slot configuration as a new System

Systems are stored in `echo_systems/systems.json` and managed via the `/api/systems` endpoints.

---

### Frontend — index.html

The entire UI is a self-contained HTML file with inline `<style>` and `<script>`. No framework, no build tools, no npm.

**Layout** — a flex row: a collapsible `#sidebar` (255px) on the left and the main `#app` taking the rest. The sidebar collapses to a 44px strip.

**Key state variables (v1.8):**

```js
let running         = false;   // generation in progress
let stop            = false;   // global stop flag — terminates entire turn
let skipCurrent     = false;   // skip flag — skips current model only
let paused          = false;   // pause flag — freezes loop until resume
let _pauseResolve   = null;    // resolves the pause Promise on resume
let chatDirty       = false;   // new messages since last save/load
let activeChatId    = null;    // ID of currently loaded chat
let activeSlots     = ['A'];   // which slots are enabled
let convHistory     = [];      // messages sent to Ollama each request
let chatLog         = [];      // full log for export and auto-save
let ragMode         = 'keyword'; // 'keyword' | 'embedding'
let awarenessFlags  = {A:false, B:false, C:false, D:false};
let awarenessMode   = {A:'standard', B:'standard', C:'standard', D:'standard'};
let awarenessCustom = {A:'', B:'', C:'', D:''};
let editingSystemId = null;    // ID of system being edited in modal
```

**CSS custom properties** define the entire colour palette:

```css
:root {
  --a:   #818cf8;   /* Slot A — indigo  */
  --b:   #34d399;   /* Slot B — emerald */
  --c:   #fb923c;   /* Slot C — orange  */
  --d:   #f472b6;   /* Slot D — pink    */
  --u:   #94a3b8;   /* User — slate     */
  --rag: #22d3ee;   /* RAG / system — cyan */
}
```

---

### Streaming Protocol & Token Counters

Ollama's streaming endpoint returns NDJSON. The final chunk (`done: true`) carries token usage:

```js
if (j.done) {
  promptTokens = j.prompt_eval_count || 0;  // tokens sent into model
  evalTokens   = j.eval_count        || 0;  // tokens generated
}
```

**Reading the counters:**

- **↑ ctx** — tokens sent *up* to the model: system prompt + full conversation history + RAG chunks + awareness injection. This number grows each turn.
- **↓ gen** — tokens generated *down* by the model in its response.

---

### Flow Control — Stop, Skip, Pause, Resume

All four controls are available during any running turn (AUTO or manual Send):

**■ STOP (Global)**
Sets `stop=true`, aborts the active stream via `AbortController`, and resolves the pause Promise if the session is currently paused. The loop checks `stop` before every slot, so the entire remaining sequence is cancelled — not just the current model. This is a fix from v1.7, where stop only cancelled the active stream and could allow subsequent models to begin.

```js
async function stopAll() {
  stop = true;
  if (_abort) { _abort.abort(); _abort = null; }
  if (_pauseResolve) { _pauseResolve(null); _pauseResolve = null; }
  await endSession();
}
```

**⏭ SKIP**
Sets `skipCurrent=true` and aborts only the current stream. The loop detects this, renders `[skipped]` in the bubble, adds a system notice, and **continues** to the next slot without exiting. The skipped model's turn is not added to `convHistory`.

**⏸ PAUSE / ▶ RESUME**
Pausing aborts the current stream and suspends the loop by `await`-ing a Promise whose resolver is stored in `_pauseResolve`. The orange PAUSED notice bar appears above the input. When the user clicks **▶ RESUME**, `_pauseResolve` is called and the loop continues from where it left off.

**INJECT & RESUME**
While paused, type a message in the input and press **INJECT & RESUME**. The message is added to both `chatLog` and `convHistory` immediately (as a user turn), then `resumeSession()` is called. The next model in the sequence will see the injected message as fresh context.

---

### Thinking Tag Renderer

`parseThink()` handles three states because the stream is processed incrementally:

```js
function parseThink(raw) {
  // Complete tag — already closed
  var m = raw.match(/<think>([\s\S]*?)<\/think>/);
  if (m) { /* render think + response separately */ }

  // Partial tag — still streaming inside <think>
  var oi = raw.indexOf('<think>');
  if (oi !== -1) { /* render "THINKING…" panel */ }

  // No tags — plain response
  return { thinkHtml: '', responseHtml: renderMd(raw.trim()) };
}
```

Two sources are supported: a native `message.thinking` JSON field (used by LFM2.5-thinking and some Qwen variants) and inline `<think>` tags embedded in the content string.

---

### Conversation History & Role Mapping

Ollama expects roles `system`, `user`, `assistant`. In a multi-slot conversation each model needs to see its own prior turns as `assistant` and all other slots' turns as `user`.

**v1.8 fix:** `buildMsgsN()` now uses the **`slot` field stored on each history entry** rather than a positional `aiTurn` counter. The old counter-based approach broke whenever a turn was cut short by stop or skip, or when slots changed between sessions — causing role assignments to drift and corrupt context across long conversations.

```js
function buildMsgsN(history, slotIndex, allSlots, sysPrompt) {
  const s = allSlots[slotIndex];
  const awareness = buildAwarenessNote(s);
  const fullSys = awareness + (sysPrompt || '');
  const msgs = [];
  if (fullSys.trim()) msgs.push({ role: 'system', content: fullSys });

  for (const h of history) {
    if (h.role === 'user') {
      msgs.push({ role: 'user', content: h.content });
    } else {
      // Uses stored slot field — accurate even after stops, skips, or slot changes
      const speakerSlot = h.slot || allSlots[0];
      const isMe = speakerSlot === s;
      let content = h.content;
      if (awarenessFlags[s] && !isMe) {
        const speakerName = allSlots.includes(speakerSlot)
          ? getSlotName(speakerSlot) : (speakerSlot || 'Other');
        content = `${speakerName}: ${h.content}`;
      }
      msgs.push({ role: isMe ? 'assistant' : 'user', content });
    }
  }
  return msgs;
}
```

---

## Configuration Reference

**Server** (`echo_server.py`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| Flask port | `8080` | Set in `app.run(port=8080)` |
| `CHATS_DIR` | `./echo_chats/` | Chat save directory |
| `KNOWLEDGE_DIR` | `./echo_knowledge/` | Knowledge base directory |
| `PROFILES_DIR` | `./echo_profiles/` | Custom model profiles directory |
| `SYSTEMS_DIR` | `./echo_systems/` | Multi-AI system presets directory |
| `MODELS_FILE` | `./echo_profiles/profiles.json` | Custom model profiles file |
| `SYSTEMS_FILE` | `./echo_systems/systems.json` | System presets file |

**UI per-slot parameters** (saved with each chat and each System):

| Parameter | Default | Ollama field | Effect |
|---|---|---|---|
| Temperature | 0.7 | `temperature` | Randomness of sampling |
| Top P | 0.9 | `top_p` | Nucleus sampling threshold |
| Top K | 40 | `top_k` | Vocabulary top-K cutoff |
| Max Tokens | 2048 | `num_predict` | Maximum tokens per response |
| Repeat Penalty | 1.1 | `repeat_penalty` | Penalises repeated n-grams |
| Context Length | 4096 | `num_ctx` | KV cache size / context window |

**RAG parameters** (saved with each chat):

| Parameter | Default | Effect |
|---|---|---|
| Chunk Size | 500 words | Words per chunk. Keep ≤ 350 for small embed models (bge-small, etc.) |
| Overlap | 50 words | Shared words between adjacent chunks |
| Retrieve Top-K | 5 | Chunks injected per query |
| RAG Template | `### Memory Context:\n{context}` | Injection wrapper sent to model |

---

## API Reference

All routes served on port `8080`.

| Method | Route | Description |
|---|---|---|
| GET | `/api/tags` | Proxy Ollama model list |
| POST | `/api/chat` | Proxy chat with optional RAG injection |
| POST | `/api/generate` | Proxy Ollama generate |
| POST | `/api/rag/load` | Load `.txt` files for keyword RAG |
| GET | `/api/rag/status` | RAG index status (chunks, embed_chunks, embed_valid) |
| POST | `/api/rag/embed_load` | Start background embedding of a folder |
| GET | `/api/rag/embed_status` | Embedding progress (done/total/running/error) |
| POST | `/api/rag/embed_unload` | Unload embedding model from VRAM |
| GET | `/api/rag/log` | Retrieval log (last 100 queries, with mode field) |
| POST | `/api/rag/log/clear` | Clear retrieval log |
| GET | `/api/knowledge/list` | List all saved knowledge bases (includes `broken` flag) |
| POST | `/api/knowledge/save` | Save current chunks/embeddings as a named KB |
| POST | `/api/knowledge/load/<id>` | Load a KB; returns chunk_size, overlap, model, folder |
| DELETE | `/api/knowledge/delete/<id>` | Delete a knowledge base |
| GET | `/api/chats/list` | List all saved chats and folders |
| POST | `/api/chats/save` | Save a chat session |
| GET | `/api/chats/load/<id>` | Load a chat by ID |
| DELETE | `/api/chats/delete/<id>` | Delete a chat |
| POST | `/api/chats/folder` | Create a folder |
| POST | `/api/chats/move` | Move a chat to a folder |
| POST | `/api/chats/duplicate/<id>` | Deep-copy a chat with new ID and `(copy)` title suffix |
| GET | `/api/profiles` | List custom model profiles |
| POST | `/api/profiles/save` | Save a model profile |
| DELETE | `/api/profiles/delete/<id>` | Delete a profile |
| GET | `/api/systems` | List all saved system presets |
| POST | `/api/systems/save` | Save or update a system preset |
| DELETE | `/api/systems/delete/<id>` | Delete a system preset |

**`/api/chat` accepts these extra fields** (stripped before forwarding to Ollama):

| Field | Type | Description |
|---|---|---|
| `use_rag` | bool | Enable RAG injection for this request |
| `rag_mode` | string | `"keyword"` or `"embedding"` |
| `rag_top_k` | int | Number of chunks to inject |
| `embed_model` | string | Ollama model name for query embedding |
| `rag_template` | string | Injection template with `{context}` placeholder |

---

## Usage Guide

### Auto Mode — AI ↔ AI Conversation

1. Select models from the dropdowns. Add slots B, C, D with the **+B / +C / +D** buttons.
2. Open **⚙ Settings** to set display names, system prompts, and parameters per slot.
3. Set the number of **Turns**.
4. Optionally type a **seed message**.
5. Press **▶ AUTO**.

A **TURN X / N** pill counts up in the header. The session auto-saves and the sidebar updates the moment generation ends.

### Flow Control During AUTO

| Button | What it does |
|---|---|
| **■ STOP** | Cancels the active stream AND all remaining models in the turn |
| **⏭ SKIP** | Cancels only the current model; continues to the next slot |
| **⏸ PAUSE** | Suspends the turn after aborting the current stream |
| **▶ RESUME** | Continues the paused turn from where it stopped |
| **INJECT & RESUME** | Adds your typed message into the conversation, then resumes |

### Manual Mode — You Talk to All

Type your message and press **SEND**. Slot A responds first, then each additional active slot responds in sequence with awareness of prior responses. Skip, Pause, and Stop all work the same as in AUTO mode.

### Multi-AI Systems

1. Click **⬡ SYSTEMS** in the config bar to open the Systems panel.
2. Click **▶ LOAD** on any built-in or saved system to apply it instantly.
3. To create your own: click **+ NEW SYSTEM**, configure each slot's name and system prompt, set the default turns, and click **Save System**.
4. To fork a built-in: click **⊕ FORK** — the editor opens pre-filled with all the built-in's settings for you to modify and save as your own.
5. To save your live config: click **⬡ SAVE SYS** in the config bar.

### Chat Duplication

Right-click any chat in the sidebar and choose **📋 Duplicate**. A deep copy appears immediately in the sidebar with `(copy)` appended to the title. All settings, prompts, parameters, and the full message log are copied. From there you can load it, edit settings, and continue the conversation independently.

### AI Awareness Injection

1. Open **⚙ Settings** for a slot.
2. Toggle **AI Awareness injection** on.
3. Choose **Standard** (auto-generated sentence) or **Custom** (write your own with `{name}` / `{others}` placeholders).
4. Always also write a **System Prompt** — the injection only provides the identity line.

### Token Monitoring

Every response bubble shows `↑ ctx · ↓ gen` after it finishes. Watch `↑ ctx` grow across turns — when it approaches your Context Length setting the model will begin losing early history.

### RAG — Keyword Mode

1. Open the **◈ RAG** panel → **Keyword (Local)** tab.
2. Enter the folder path containing your `.txt` files.
3. Use the **Estimator** to preview chunking results.
4. Click **LOAD FILES**, then toggle **USE RAG** on.
5. Click **◈ VIEW LOG** after a query to see exactly which chunks were injected.

### RAG — Embedding Mode

1. Open **◈ RAG** → **Ollama Embeddings** tab.
2. Enter the folder path and select an **Embedding Model** (⭐ models are dedicated embed models).
3. Click **EMBED FILES** — a progress bar shows embedding progress.
4. Toggle **USE RAG** on.
5. Optionally click **SAVE AS KNOWLEDGE BASE** to persist to disk.

### Knowledge Bases

1. After embedding, type a name and click **SAVE AS KNOWLEDGE BASE**.
2. In future sessions, open **◈ RAG** → **Knowledge Base** tab and click **LOAD**.
3. KBs with all-broken embeddings (⚠ BROKEN) show a **⟳ REPAIR** button that pre-fills the Embedding tab for one-click re-embedding.

### Chat History

Click any chat in the left sidebar to reload it. All settings are restored. Right-click for options: **Move to folder**, **Duplicate**.

### Export

- **↓ TXT** — full conversation including thinking blocks.
- **↓ FT** — fine-tuning export with awareness injection lines stripped from system prompts.

---

## FAQ

**Q: What exactly are ↑ ctx and ↓ gen?**
`↑ ctx` is the total tokens sent into the model — system prompt + awareness injection + conversation history + RAG chunks. `↓ gen` is the tokens the model generated. Compare `↑ ctx` against your Context Length setting to track remaining budget.

**Q: Does STOP cancel all models or just the current one?**
In v1.8, **STOP cancels the entire turn** — the active stream is aborted and the loop exits before any further models run. If you only want to cancel the current model and continue to the next one, use **⏭ SKIP** instead.

**Q: How does PAUSE differ from STOP?**
PAUSE suspends the turn at the current position without discarding it. You can inject a message and then resume exactly where you left off. STOP permanently ends the turn and triggers auto-save.

**Q: Can I inject a message without pausing first?**
Not directly in AUTO mode — pause first, type your message, then click INJECT & RESUME. In manual Send mode you can simply send a new message after the current sequence finishes.

**Q: How does Chat Duplication work?**
It's a full deep copy on the server: the source JSON file is read, all fields are copied (settings, prompts, parameters, awareness state, RAG settings, and the complete message log), a new timestamped ID is assigned, `(copy)` is appended to the title, and the result is saved as a new file. No data is shared with the original.

**Q: What's stored in a System preset?**
Slot assignments (A/B/C/D), display names, system prompts, all six inference parameters per slot, awareness on/off per slot, and the default number of turns. Base model selections are not stored in Systems (they depend on what you have pulled in Ollama) — apply a System first, then set models from the dropdowns.

**Q: Can I modify a built-in System like Trialogue?**
Built-ins are read-only in the UI but click **⊕ FORK** to copy one into your own editable System. The fork is immediately saved and editable.

**Q: Why did context tokens drop between turns?**
This was a role-mapping bug in v1.7 and earlier. `buildMsgsN()` used a positional counter (`aiTurn % slots`) to assign `assistant`/`user` roles, which drifted whenever a turn was cut short. v1.8 fixes this by storing the originating `slot` field on each history entry and using that directly for role assignment.

**Q: The keyword RAG log button wasn't working.**
Fixed in v1.8. The `toggleRagLog()` function was referenced in the HTML but was never defined — only its embedding-mode counterpart existed. Both log toggles now work independently.

**Q: The model ignores the RAG context.**
Check the Retrieval Log to confirm chunks were actually injected. For keyword mode, the scorer only matches exact words. For embedding mode, check the server terminal for score output; very low scores usually mean a model mismatch — re-embed with the same model you query with.

**Q: Can I use the same model for both/all slots?**
Yes. The role mapping in `buildMsgsN()` uses the stored slot field, not the model name, so identical models in multiple slots work correctly.

**Q: What happens if Ollama is offline?**
The header shows `OLLAMA OFFLINE`. Model dropdowns show "Cannot reach server". The sidebar, settings, Systems panel, and all RAG/knowledge controls remain usable.

**Q: Can I share this on a network?**
Yes — `app.run(host='0.0.0.0', port=8080)` is the default. Access via `http://your-server-ip:8080`. For internet exposure use nginx or ngrok with authentication.

**Q: Where are my files stored?**
All files are stored next to `echo_server.py`: `echo_chats/` for conversations, `echo_knowledge/` for knowledge bases, `echo_profiles/` for model profiles, `echo_systems/` for system presets. No data leaves your machine.

---

## Changelog

| Version | Changes |
|---|---|
| **v1.8** | **Global Stop fix** — STOP now terminates the entire turn (all remaining models), not just the active stream. **Skip** — new ⏭ SKIP button aborts the current model only and advances to the next slot. **Pause / Inject / Resume** — new ⏸ PAUSE freezes the turn mid-sequence; user can inject a message (INJECT & RESUME) or simply resume without injecting. **Chat Duplication** — right-click any saved chat to deep-copy it including all settings, prompts, parameters, and history. **Multi-AI Systems Presets** — new ⬡ SYSTEMS panel with save/load/edit/fork/delete; two built-in expert-tuned templates: Trialogue (Teacher↔Student↔Mediator) and Devil's Advocate Debate (Proposer↔Challenger↔Judge). **Context role-mapping fix** — `buildMsgsN()` now uses the stored `slot` field on each history entry instead of a positional counter, fixing context drift after stops, skips, or slot changes. **RAG log fix** — `toggleRagLog()` was referenced but never defined; keyword retrieval log button now works correctly. New `/api/chats/duplicate` and `/api/systems` CRUD endpoints on the backend. New `echo_systems/` directory auto-created on first run. |
| **v1.7** | Embedding auto-truncation. Profiles folder. Graceful KB load. Broken KB detection. Auto-enable RAG on KB load. Chunk size warning banner. |
| **v1.6** | Sidebar auto-updates instantly when a session ends. Full async save chain. |
| **v1.5** | Fixed missing `@app.route` decorator for `/api/rag/status`. Broken KB detection with ⚠ badge and ⟳ REPAIR. |
| **v1.4** | Loading a KB restores chunk size, overlap, and embedding model to UI fields. |
| **v1.3** | Dual Ollama embed API support (`/api/embed` + `/api/embeddings`). Embed VRAM unload endpoint. Natural-language awareness injection. Embedding retrieval log auto-open. |
| **v1.2** | AI Awareness injection: Standard vs Custom mode. `{name}` / `{others}` placeholders. Awareness state saved and restored. |
| **v1.1** | Ollama Embeddings RAG. Knowledge Base persistence. Custom Model Profiles. Up to 4 model slots. Display names. RAG mutual exclusion. Embedding progress bar. Re-embed warning. RAG prompt template. Embed model unload. Separate retrieval logs. AbortController stop. |

---

## Credits

- [Ollama](https://ollama.com) — local model serving
- [Flask](https://flask.palletsprojects.com) — Python web framework
- [JetBrains Mono](https://www.jetbrains.com/legalnotice/fonts/) + [Inter](https://rsms.me/inter/) — fonts used in the UI
