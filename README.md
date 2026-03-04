# ECHO // MULTI-MIND

> A local, privacy-first interface for multi-model AI conversations — powered by Ollama and a lightweight Flask proxy with dual RAG engines (keyword + semantic embeddings), persistent knowledge bases, custom awareness injection, and real-time token monitoring.

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
- **Inject yourself** into the conversation at any point.
- **Feed long-term memory** via two RAG engines: a fast keyword scorer (no dependencies) or semantic Ollama embeddings.
- **Save knowledge bases** to disk — load your embeddings instantly in any future session without re-processing.
- **Save and reload every conversation** from a persistent sidebar with folder organisation.

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
  - [Chat Persistence](#chat-persistence)
  - [Frontend — index.html](#frontend--indexhtml)
  - [Streaming Protocol & Token Counters](#streaming-protocol--token-counters)
  - [Thinking Tag Renderer](#thinking-tag-renderer)
  - [Conversation History & Role Mapping](#conversation-history--role-mapping)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Usage Guide](#usage-guide)
- [FAQ](#faq)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                      Browser (UI)                         │
│                  echo_ui/index.html                       │
│  Fetch → /api/chat  /api/tags  /api/rag/*                 │
│          /api/chats/*  /api/knowledge/*  /api/profiles/*  │
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
└─────────────────┼─────────────────────────────────────────┘
                  │ HTTP (port 11434)
        ┌─────────▼──────────┐
        │     Ollama API     │
        │  Model A / B / C / D  │
        └────────────────────┘
```

The Flask server has five jobs:

1. **Solve CORS** — browsers block direct `fetch()` to `localhost:11434`. The proxy removes that restriction without touching Ollama's config.
2. **Inject RAG context** — before forwarding a chat request, the server retrieves relevant chunks and prepends them to the system prompt using a configurable template.
3. **Persist chats** — saves and loads conversations as JSON files in `echo_chats/`.
4. **Persist knowledge bases** — saves and loads chunked + embedded knowledge to `echo_knowledge/` so you never have to re-process files between sessions.
5. **Serve the UI** — the single `index.html` is served as a static asset, so the entire app runs from one `python echo_server.py` command.

---

## Feature List

| Feature | Details |
|---|---|
| **Multi-Model (up to 4)** | Slots A, B, C, D — each with its own display name, system prompt, and inference parameters |
| **Auto Mode** | Fully autonomous AI ↔ AI conversation for N configurable turns across all active slots |
| **Turn Countdown** | Live header pill showing current turn / total (e.g. `TURN 3 / 10`) during AUTO |
| **Manual / Inject Mode** | Send your own message; all active models respond sequentially |
| **Per-Model Parameters** | Temperature, Top-P, Top-K, Max Tokens, Repeat Penalty, Context Length — set independently per slot |
| **Display Names** | Each slot has a custom display name used in chat bubbles, exports, and awareness injection |
| **AI Awareness Injection** | Optionally prepend identity text to each slot's system prompt; Standard mode (auto-generated) or Custom mode (your own template with `{name}` and `{others}` placeholders) |
| **Keyword RAG** | Load a folder of `.txt` files; keyword-overlap retrieval with `√` normalisation — no dependencies |
| **Embedding RAG** | Semantic retrieval via Ollama embedding models (cosine similarity); supports both new `/api/embed` and legacy `/api/embeddings` Ollama APIs automatically |
| **RAG Template** | Fully customisable injection template — write any text around `{context}` to control how retrieved chunks are presented to the model |
| **Knowledge Base Persistence** | Save chunked + embedded knowledge to disk; load instantly in any future session with settings restored (chunk size, overlap, model all restored automatically) |
| **Broken KB Detection** | Detects knowledge bases saved with empty embeddings (from older versions); shows ⚠ BROKEN badge with one-click repair that pre-fills all settings |
| **RAG Chunk Controls** | Chunk size, overlap, and retrieve top-K all configurable from the UI without restarting |
| **RAG Chunk Estimator** | Enter a file character count; UI instantly shows estimated words, chunks produced, and chunks retrieved |
| **Embedding Progress** | Live progress bar showing chunks embedded / total during background embedding |
| **Re-embed Warning** | Banner warns if chunk size or model changed since last embed — prevents accidental use of stale vectors |
| **RAG Retrieval Log** | Per-query log showing which file and text chunk was retrieved, with timestamps — separate views for keyword and embedding mode |
| **Embed Model Unload** | Dedicated ⏏ button to evict the embedding model from VRAM via the correct Ollama endpoint |
| **Token Counters** | Per-message `↑ ctx · ↓ gen` badge + persistent header pills showing prompt tokens in and response tokens out |
| **Context Length Control** | Set `num_ctx` per model — controls the KV cache / context window Ollama allocates |
| **Custom Model Profiles** | Save a model + system prompt + all parameters as a named profile; apply to any slot in one click |
| **Chat Sidebar** | Collapsible left panel listing all saved chats; updates instantly when a session ends — no page refresh needed |
| **Chat Auto-Save** | Every session saves automatically to `echo_chats/` as JSON the moment generation completes |
| **Chat Folders** | Create named folders; right-click any chat to move it |
| **Full State Restore** | Loading a chat restores models, display names, system prompts, all parameters, awareness settings, and RAG settings |
| **Streaming** | Responses stream token-by-token using NDJSON; UI updates in real time |
| **Stop (AbortController)** | Stop button cancels the active `fetch()` mid-stream immediately — no waiting for the current chunk to finish |
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
ollama pull znbang/bge:small-en-v1.5-q8_0   # fast, small
ollama pull nomic-embed-text                  # popular general-purpose
ollama pull mxbai-embed-large                 # higher quality
```

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
  ECHO // MULTI-MIND  v1.6
══════════════════════════════════════════════════════════
  UI:        http://localhost:8080
  Ollama:    http://localhost:11434
  Chats:     ./echo_chats/
  Knowledge: ./echo_knowledge/
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
├── echo_models.json      ← Auto-created; stores custom model profiles
└── echo_ui/
    └── index.html        ← Complete frontend (HTML + CSS + JS, single file)
```

---

## Technical Deep Dive

### Backend — echo_server.py

The server is a single-file Flask application with no database, no ORM, no task queue. All state is held in memory at the process level, except for chats, knowledge bases, and profiles which are written to disk as JSON.

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
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embed",
                          json={"model": model, "input": text}, timeout=60)
        if r.ok:
            embs = r.json().get('embeddings', [])
            if embs and embs[0]:
                return embs[0]
    except Exception:
        pass
    # Legacy API: POST /api/embeddings  { model, prompt }  → { embedding: [...] }
    r = requests.post(f"{OLLAMA_URL}/api/embeddings",
                      json={"model": model, "prompt": text}, timeout=60)
    return r.json().get('embedding', [])
```

**Cosine similarity retrieval:**

```python
def cosine_sim(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na  = math.sqrt(sum(x*x for x in a))
    nb  = math.sqrt(sum(x*x for x in b))
    return dot / (na * nb) if na and nb else 0.0
```

Scores below `0.01` are discarded as near-zero noise. The server logs top scores to the terminal so you can diagnose retrieval quality at a glance.

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

**Save** — refuses to save if any embedding vectors are empty (prevents silently saving a broken KB):

```python
if kb_type == 'embedding':
    empty = sum(1 for c in chunks if not c.get('embedding'))
    if empty:
        return jsonify({'error': f'{empty}/{len(chunks)} chunks have empty embeddings.'}), 400
```

**Load** — restores `chunk_size`, `overlap`, and `embed_model` back to the UI fields automatically, so the displayed settings always match what is actually in memory. Also restores the source folder path so repair is one click.

**Broken KB detection** — if a KB was saved before the embedding API fix (v1.3), all its embedding vectors will be empty `[]`. These are flagged with a ⚠ BROKEN badge in the Knowledge Base tab. Clicking **⟳ REPAIR** pre-fills the Embedding tab with the original folder, chunk size, overlap, and model — click EMBED FILES then SAVE AS KNOWLEDGE BASE with the same name to overwrite.

---

### RAG Template System

The injection template controls exactly how retrieved chunks are presented to the model. Write any text; use `{context}` as the placeholder — it is replaced at request time with the top-K results formatted as `[filename] chunk text` for each result.

The template is appended to the model's system prompt before the request is forwarded to Ollama.

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

The template is saved with the chat session and restored on load.

---

### AI Awareness Injection

When enabled per slot, a short identity line is prepended to that slot's system prompt before each request. This tells the model its own name and who the other participants are — without adding behavioral instructions that compete with your actual system prompt.

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

Placeholders are optional — you can hardcode any names, use only one placeholder, or use neither. All combinations work:

```
You are {name}, an expert debater. Your opponent is {others}.
You are Echo1, debating with {others}.
You are {name}, debating with Echo2.
You are Echo1, debating with Echo2.
```

The display name used in injection — and in chat bubbles and exports — is whatever you type in the **Display Name** field in Settings for that slot. If left blank it falls back to the base model name. The display name has no effect on the model itself; the model only knows its name if the injection or system prompt tells it.

Awareness state (on/off, mode, custom text) is saved with the chat and restored on load.

---

### Chat Persistence

Chats are saved as JSON files in `echo_chats/` next to `echo_server.py`. The directory is created automatically on first run.

The sidebar updates **instantly** when a session ends — no page refresh needed. The save chain is fully awaited: `endSession()` → `autoSaveChat()` → `loadChatList()`, so the new chat appears in the sidebar the moment generation completes.

**Auto-save logic** uses a `chatDirty` flag that becomes `true` only when new messages are generated. `endSession()` only saves when `chatDirty` is true, which prevents re-saving a chat that was just loaded from disk.

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

Loading restores everything: models, display names, system prompts, all inference parameters, awareness settings (on/off, mode, custom template), and RAG settings.

**Folders** are physical subdirectories inside `echo_chats/`. Right-click any chat in the sidebar to move it into a folder.

---

### Frontend — index.html

The entire UI is a self-contained HTML file with inline `<style>` and `<script>`. No framework, no build tools, no npm.

**Layout** — a flex row: a collapsible `#sidebar` (255px) on the left and the main `#app` taking the rest. The sidebar collapses to a 44px strip.

**Key state variables:**

```js
let running         = false;   // generation in progress
let stop            = false;   // user hit stop
let chatDirty       = false;   // new messages since last save/load
let activeChatId    = null;    // ID of currently loaded chat
let activeSlots     = ['A'];   // which slots are enabled
let convHistory     = [];      // messages sent to Ollama each request
let chatLog         = [];      // full log for export and auto-save
let ragMode         = 'keyword'; // 'keyword' | 'embedding'
let awarenessFlags  = {A:false, B:false, C:false, D:false};
let awarenessMode   = {A:'standard', B:'standard', C:'standard', D:'standard'};
let awarenessCustom = {A:'', B:'', C:'', D:''};
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

- **↑ ctx** — tokens sent *up* to the model: system prompt + full conversation history + RAG chunks + awareness injection. This number grows each turn. Compare it to your Context Length setting to know how much budget remains.
- **↓ gen** — tokens generated *down* by the model in its response.

These appear as a badge under each bubble (`↑ 947 ctx · ↓ 400 gen`) and as persistent header pills.

**Stop** uses an `AbortController` that cancels the active `fetch()` immediately:

```js
_abort = new AbortController();
res = await fetch('/api/chat', { ..., signal: _abort.signal });
// On stop:
_abort.abort();
```

**Smart scroll** — `scrollBottom()` only auto-scrolls when within 80px of the bottom. Scrolling up pauses it; scrolling back down resumes.

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

Ollama expects roles `system`, `user`, `assistant`. In a multi-slot conversation each model needs to see its own prior turns as `assistant` and all other slots' turns as `user`. `buildMsgsN()` handles this correctly for any number of slots, including when multiple slots use the same model:

```js
function buildMsgsN(history, slotIndex, allSlots, sysPrompt) {
  const awareness = buildAwarenessNote(allSlots[slotIndex]);
  const fullSys   = awareness + (sysPrompt || '');
  // ...
  for (const h of history) {
    if (h.role === 'user') {
      msgs.push({ role: 'user', content: h.content });
    } else {
      const speakerIdx = aiTurn % allSlots.length;
      const isMe       = speakerIdx === slotIndex;
      msgs.push({ role: isMe ? 'assistant' : 'user', content });
      aiTurn++;
    }
  }
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
| `MODELS_FILE` | `./echo_models.json` | Custom model profiles |

**UI per-slot parameters** (saved with each chat):

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
| Chunk Size | 500 words | Words per chunk |
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
| GET | `/api/rag/embed_status` | Embedding progress (done/total/running) |
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
| GET | `/api/profiles` | List custom model profiles |
| POST | `/api/profiles/save` | Save a model profile |
| DELETE | `/api/profiles/delete/<id>` | Delete a profile |

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

A **TURN X / N** pill counts up in the header. Press **■ STOP** at any time — the stream is cancelled immediately. The session auto-saves and the sidebar updates the moment generation ends.

### Manual Mode — You Talk to All

Type your message and press **SEND**. Slot A responds first, then each additional active slot responds in sequence with awareness of prior responses.

### AI Awareness Injection

1. Open **⚙ Settings** for a slot.
2. Toggle **AI Awareness injection** on.
3. Choose **Standard** (auto-generated sentence) or **Custom** (write your own with `{name}` / `{others}` placeholders).
4. Make sure to also write a **System Prompt** — the injection only provides the identity line; the system prompt defines behavior.

### Token Monitoring

Every response bubble shows `↑ ctx · ↓ gen` after it finishes. Watch `↑ ctx` grow across turns — when it approaches your Context Length setting the model will begin losing early history. Increase Context Length (and ensure VRAM) to extend the window.

### RAG — Keyword Mode

1. Open the **◈ RAG** panel → **Keyword (Local)** tab.
2. Enter the folder path containing your `.txt` files.
3. Use the **Estimator** to preview chunking results.
4. Tune **Chunk Size**, **Overlap**, **Top-K**.
5. Click **LOAD FILES**, then toggle **USE RAG** on.
6. Click **◈ VIEW LOG** after a query to see exactly which chunks were injected.

### RAG — Embedding Mode

1. Open **◈ RAG** → **Ollama Embeddings** tab.
2. Enter the folder path and select an **Embedding Model** (⭐ models are dedicated embed models).
3. Set chunk size and overlap.
4. Click **EMBED FILES** — a progress bar shows embedding progress.
5. Toggle **USE RAG** on.
6. Optionally click **SAVE AS KNOWLEDGE BASE** to persist to disk.

### Knowledge Bases

1. After embedding, type a name and click **SAVE AS KNOWLEDGE BASE**.
2. In future sessions, open **◈ RAG** → **Knowledge Base** tab and click **LOAD** — chunk size, overlap, and model are all restored automatically.
3. KBs with broken embeddings (⚠ BROKEN) show a **⟳ REPAIR** button that pre-fills the Embedding tab for one-click re-embedding.

### Custom RAG Template

In the Embedding tab, edit the **RAG Prompt Template** field. Use `{context}` as the placeholder for injected chunks. The template is saved with the chat session.

### Chat History

Click any chat in the left sidebar to reload it. All settings are restored. Right-click to move chats into folders. Hover over a chat to reveal the ✕ delete button.

### VRAM Management

Use the **⏏** button next to each slot's model dropdown to unload that model from GPU memory. Use **⏏ UNLOAD MODEL** in the Embedding tab to unload the embedding model specifically (uses the correct Ollama embed endpoint).

### Model Profiles

Open **MY MODELS** in the sidebar bottom. Create a profile with a name, avatar, base model, system prompt, and all parameters. Click any profile to apply it to a slot.

### Export

- **↓ TXT** — full conversation including thinking blocks.
- **↓ FT** — fine-tuning export with awareness injection lines stripped from system prompts.

---

## FAQ

**Q: What exactly are ↑ ctx and ↓ gen?**
`↑ ctx` is the total tokens sent into the model — system prompt + awareness injection + conversation history + RAG chunks. `↓ gen` is the tokens the model generated. Compare `↑ ctx` against your Context Length setting to track remaining budget.

**Q: The model ignores the RAG context.**
Check the Retrieval Log to confirm chunks were actually injected. For keyword mode, the scorer only matches exact words — try more specific terms or increase chunk size. For embedding mode, check the server terminal for score output; very low scores mean the query embedding is mismatched with the stored embeddings (usually a model mismatch — re-embed with the same model you query with).

**Q: Embedding scores are all 0.0.**
This usually means the embedding model name doesn't match what was used during embedding, or the KB was saved before the Ollama API fix (v1.3). In that case the KB will show ⚠ BROKEN — use the Repair flow.

**Q: The model seems confused about its identity / who it's talking to.**
Awareness injection only provides the name. Add a **System Prompt** for that slot with behavioral instructions (e.g. `You are Echo1. Debate thoughtfully with Echo2. Respond only for yourself.`). Without a system prompt, thinking models will spend their reasoning budget trying to invent their own purpose.

**Q: Can I use the same model for both/all slots?**
Yes. The role mapping in `buildMsgsN()` handles this correctly — each slot sees its own prior turns as `assistant` and all others as `user`, regardless of whether they share a model name.

**Q: Can I write my own RAG injection text?**
Yes. Edit the **RAG Prompt Template** field in the Embedding tab. Use `{context}` as the placeholder — everything else is your own text. The template can be as long and specific as you want.

**Q: What happens if Ollama is offline?**
The header shows `OLLAMA OFFLINE`. Model dropdowns show "Cannot reach server". The sidebar, settings, and all RAG/knowledge controls remain usable.

**Q: Can I share this on a network?**
Yes — `app.run(host='0.0.0.0', port=8080)` is the default. Access via `http://your-server-ip:8080`. For internet exposure use nginx or ngrok with authentication.

**Q: Where are my files stored?**
All files are stored next to `echo_server.py`: `echo_chats/` for conversation history, `echo_knowledge/` for knowledge bases, `echo_models.json` for model profiles. No data leaves your machine.

---

## Changelog

| Version | Changes |
|---|---|
| **v1.6** | Sidebar auto-updates instantly when a session ends — no page refresh needed. Full async save chain. |
| **v1.5** | Fixed missing `@app.route` decorator for `/api/rag/status` (was 404). Broken KB detection with ⚠ badge and ⟳ REPAIR button. Source folder saved with KB for repair pre-fill. Save blocked for empty embeddings. |
| **v1.4** | Loading a KB now restores chunk size, overlap, and embedding model to UI fields. Server returns `chunk_size`/`overlap` in knowledge load response. |
| **v1.3** | `get_embedding()` updated to support both new Ollama `/api/embed` API (v0.5+) and legacy `/api/embeddings` automatically. Dedicated `/api/rag/embed_unload` endpoint uses correct embed endpoint for VRAM unload. Natural-language awareness injection replaces bracket syntax. Embedding retrieval log auto-opens on first hit. |
| **v1.2** | AI Awareness injection: Standard vs Custom mode per slot. `{name}` / `{others}` placeholders. Awareness state saved and restored with chats. System prompt hint in awareness UI. |
| **v1.1** | Ollama Embeddings RAG tab. Knowledge Base persistence (`echo_knowledge/`). Custom Model Profiles. Up to 4 model slots (A/B/C/D). Display names per slot. RAG mutual exclusion (keyword and embedding cannot both be active). Embedding progress bar. Re-embed warning banner. RAG prompt template field. Embed model unload button. Separate retrieval logs per mode. AbortController stop button. |

---

## Credits

- [Ollama](https://ollama.com) — local model serving
- [Flask](https://flask.palletsprojects.com) — Python web framework
- [JetBrains Mono](https://www.jetbrains.com/legalnotice/fonts/) + [Inter](https://rsms.me/inter/) — fonts used in the UI
